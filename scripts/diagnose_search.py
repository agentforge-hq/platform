"""Compare a semantic-only admission candidate with the frozen local ranker."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentforge_backend.models import SearchRequest, Skill
from agentforge_backend.retrieval import (
    RANKING_VERSION,
    SEMANTIC_FLOOR,
    catalog_revision,
    eligible,
    fuse,
    lexical_candidates,
    terms,
)
from evaluation.core import EvaluationError, load_corpus, load_json, normalized, utc_now

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_VERSION = 'semantic-admission-dev-v1'


def development_requests(path: Path) -> list[tuple[str, SearchRequest]]:
    data = load_json(path)
    prompts = data.get('prompts') if isinstance(data, dict) else None
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 20:
        raise EvaluationError('Use between one and twenty separate development tasks.')
    requests = []
    for prompt in prompts:
        if (
            not isinstance(prompt, dict)
            or not isinstance(prompt.get('id'), str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', prompt['id'])
            or not isinstance(prompt.get('text'), str)
        ):
            raise EvaluationError('Each development task needs a bounded ID and text.')
        try:
            request = SearchRequest(query=prompt['text'], harness='codex', limit=3)
        except ValueError:
            raise EvaluationError('Each development task needs a valid bounded search query.') from None
        requests.append((prompt['id'], request))
    if len({ident for ident, _ in requests}) != len(requests):
        raise EvaluationError('Development task IDs must be unique.')
    if len({normalized(request.query) for _, request in requests}) != len(requests):
        raise EvaluationError('Development task text must be distinct.')
    load_corpus(ROOT / 'evaluation', development=path)
    return requests


def validated_candidates(scores: list[dict], by_id: dict[str, Skill]) -> list[tuple[Skill, float]]:
    seen = set()
    for row in scores:
        ident, score = row.get('skill_id'), row.get('score')
        if (
            ident not in by_id
            or ident in seen
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
        ):
            raise EvaluationError('Candidate capture contains an invalid identity or score.')
        seen.add(ident)
    if len(scores) > 50:
        raise EvaluationError('Candidate capture must retain at most fifty results.')
    # Preserve backend rank order, including approximate-search near ties.
    return [(by_id[row['skill_id']], float(row['score'])) for row in scores]


def compare_candidates(
    rows: list[Skill],
    request: SearchRequest,
    scores: list[dict],
    *,
    lexical_scores: list[dict] | None = None,
) -> dict:
    allowed = [row for row in rows if eligible(row, request)]
    if scores and (not allowed or not terms(request.query)):
        raise EvaluationError('Captured semantic results contradict the frozen retrieval condition.')
    by_id = {row.skill_id: row for row in allowed}
    lexical = (
        lexical_candidates(allowed, request.query)
        if lexical_scores is None
        else validated_candidates(lexical_scores, by_id)
    )
    semantic = [(skill, score) for skill, score in validated_candidates(scores, by_id) if score >= SEMANTIC_FLOOR]
    supported = {skill.skill_id for skill, _ in semantic}
    baseline = fuse(lexical=lexical, semantic=semantic, limit=request.limit)
    candidate = fuse(
        lexical=[(skill, score) for skill, score in lexical if skill.skill_id in supported],
        semantic=semantic,
        limit=request.limit,
    )
    return {
        'semantic_candidates': scores,
        'lexical_candidates': [{'skill_id': skill.skill_id, 'score': score} for skill, score in lexical],
        'semantic_above_floor': len(semantic),
        'baseline': [skill.skill_id for skill in baseline],
        'candidate': [skill.skill_id for skill in candidate],
        'baseline_lexical_only': [skill.skill_id for skill in baseline if skill.skill_id not in supported],
        'human_decision': None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompts', required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--target', help='Existing local Pixeltable catalog; no schema or service changes.')
    source.add_argument('--replay', type=Path, help='Saved report; makes no Pixeltable or model requests.')
    parser.add_argument('--output', required=True, type=Path, help='New private evidence directory.')
    args = parser.parse_args()
    requests = development_requests(args.prompts)
    prompt_digest = hashlib.sha256(args.prompts.read_bytes()).hexdigest()
    retrieval_digest = hashlib.sha256((ROOT / 'agentforge_backend/retrieval.py').read_bytes()).hexdigest()
    if args.output.exists():
        raise EvaluationError('Choose a new output directory; existing evidence is preserved.')
    if args.replay:
        saved = load_json(args.replay)
        if (
            saved.get('complete') is not True
            or saved.get('baseline_version') != RANKING_VERSION
            or saved.get('semantic_floor') != SEMANTIC_FLOOR
        ):
            raise EvaluationError('Replay requires a complete capture with the same baseline and semantic floor.')
        if saved['prompt_sha256'] != prompt_digest or saved['retrieval_sha256'] != retrieval_digest:
            raise EvaluationError('Replay requires the same development tasks and frozen retrieval implementation.')
        rows = [Skill.model_validate(row) for row in saved['catalog']]
        if saved['catalog_revision'] != catalog_revision(rows):
            raise EvaluationError('Replay catalog revision does not match its rows.')
        saved_cases = {case['id']: case for case in saved['cases']}
        if len(saved_cases) != len(saved['cases']) or set(saved_cases) != {ident for ident, _ in requests}:
            raise EvaluationError('Replay must retain exactly the captured development task IDs.')
    else:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*', args.target):
            raise EvaluationError('Use an existing local catalog directory, not a Cloud database.')
        import app

        app.TableModel.bind_all(args.target)
        pointers = app.published_versions()
        rows = app.current_rows(pointers)
        if not rows:
            raise EvaluationError('The local catalog must already contain published rows.')
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        'captured_at': utc_now(),
        'mode': 'replay' if args.replay else 'local_capture',
        'baseline_version': RANKING_VERSION,
        'candidate_version': CANDIDATE_VERSION,
        'retrieval_sha256': retrieval_digest,
        'prompt_sha256': prompt_digest,
        'catalog_revision': catalog_revision(rows),
        'semantic_floor': SEMANTIC_FLOOR,
        'scope': 'Development comparison only; no human relevance or release gate is established.',
        'catalog': [row.model_dump() for row in rows],
        'cases': [],
        'complete': False,
    }
    with (args.output / 'progress.jsonl').open('x') as progress:
        for ident, request in requests:
            try:
                if args.replay:
                    scores = saved_cases[ident]['semantic_candidates']
                    lexical_scores = saved_cases[ident]['lexical_candidates']
                else:
                    allowed_ids = [row.skill_id for row in rows if eligible(row, request)]
                    scores = (
                        list(
                            app.semantic_candidates_query(
                                app.Versions.table, request.query, pointers, allowed_ids
                            ).collect()
                        )
                        if allowed_ids and terms(request.query)
                        else []
                    )
                    lexical_scores = None
                comparison = compare_candidates(rows, request, scores, lexical_scores=lexical_scores)
                if args.replay and comparison['baseline'] != saved_cases[ident]['baseline']:
                    raise EvaluationError('The frozen baseline could not be reproduced.')
                case = {'id': ident, **comparison}
                report['cases'].append(case)
                progress.write(json.dumps(case) + '\n')
                progress.flush()
                print(f'{ident}: baseline {len(case["baseline"])}; candidate {len(case["candidate"])}', flush=True)
            except Exception as exc:
                progress.write(json.dumps({'id': ident, 'outcome': 'failed', 'error_type': type(exc).__name__}) + '\n')
                raise
    report['complete'] = True
    with (args.output / 'report.json').open('x') as destination:
        json.dump(report, destination, indent=2)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (EvaluationError, FileExistsError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
    except Exception as error:
        print(f'Diagnostic failed ({type(error).__name__}). Check any retained output directory.', file=sys.stderr)
        raise SystemExit(1)
