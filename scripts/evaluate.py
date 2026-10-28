"""Run a bounded retrieval probe or replay redacted captured responses."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.core import (
    EvaluationError, HttpBudget, digest_file, load_corpus, load_json, search_case,
    summarize, utc_now, validate_capture, validate_url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--endpoint', help='Exact public search URL. Sends synthetic prompt text only.')
    source.add_argument('--responses', type=Path, help='Captured JSON with corpus_sha256 and cases.')
    parser.add_argument('--corpus', type=Path, default=Path(__file__).resolve().parents[1] / 'evaluation')
    parser.add_argument('--development-prompts', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Report path. Captures and failed cases are written beside it.')
    parser.add_argument('--limit-cases', type=int, default=5, help='Live default is a five-case smoke probe; use 100 explicitly for a full run.')
    parser.add_argument('--max-requests', type=int, default=100, help='Total HTTP attempts including retries.')
    parser.add_argument('--timeout-seconds', type=float, default=15)
    parser.add_argument('--retries', type=int, default=1)
    parser.add_argument('--interval-seconds', type=float, default=4, help='Minimum between attempts. Default stays below 20 per minute.')
    parser.add_argument('--harness', default='codex',
                        choices=['codex', 'claude-code', 'cursor', 'gemini', 'opencode', 'devin', 'portable'])
    parser.add_argument('--harness-version', default='not_measured')
    parser.add_argument('--model', default='not_measured')
    parser.add_argument('--settings-sha256', default='not_recorded')
    parser.add_argument('--instructions-sha256', default='not_recorded')
    args = parser.parse_args()
    if not (1 <= args.limit_cases <= 100 and 1 <= args.max_requests <= 300 and 0 <= args.retries <= 2
            and 0 < args.timeout_seconds <= 60 and math.isfinite(args.interval_seconds)
            and args.interval_seconds >= 3.1):
        parser.error('Bounds: cases 1..100, attempts 1..300, retries 0..2, timeout <=60s, interval >=3.1s.')
    prompts, labels, manifest = load_corpus(args.corpus, args.development_prompts)
    outputs = [args.output, args.output.with_suffix('.cases.json'), args.output.with_suffix('.failed.json')]
    frozen = {(args.corpus / name).resolve() for name in ('prompts.json', 'labels.json', 'freeze.json')}
    if any(path.resolve() in frozen for path in outputs):
        parser.error('Reports cannot replace frozen corpus files.')
    if args.responses:
        cases = validate_capture(load_json(args.responses), set(prompts), manifest['corpus_sha256'])
        mode = 'captured'
    else:
        endpoint = validate_url(args.endpoint)
        budget = HttpBudget(args.max_requests, args.timeout_seconds, args.retries, args.interval_seconds)
        cases = []
        for ident, text in list(prompts.items())[:args.limit_cases]:
            payload = {'query': text, 'harness': args.harness, 'limit': 3}
            cases.append(search_case(ident, budget.request(endpoint, payload)))
        mode = 'http'
    report = summarize(labels, cases, manifest['corpus_sha256'])
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = 'unknown'
    report['execution'] = {'mode': mode, 'tooling_revision': revision, 'harness': args.harness,
                           'harness_version': args.harness_version, 'model': args.model,
                           'settings_sha256': args.settings_sha256, 'instructions_sha256': args.instructions_sha256}
    if args.responses:
        report['execution']['input_capture_sha256'] = digest_file(args.responses)
    else:
        report['execution']['endpoint'] = endpoint
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    args.output.with_suffix('.cases.json').write_text(json.dumps({'schema_version': 1,
        'corpus_sha256': manifest['corpus_sha256'], 'captured_at': utc_now(),
        'execution': report['execution'], 'cases': cases}, indent=2) + '\n')
    args.output.with_suffix('.failed.json').write_text(json.dumps(report['failed_cases'], indent=2) + '\n')
    print(json.dumps({'report': str(args.output), 'complete': report['complete'],
                      'human_review_status': 'pending', 'error_counts': report['counts']['errors']}))
    return 0 if report['complete'] and report['consistent_revisions'] else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Evaluation input or execution failed ({type(error).__name__}). No release gate is established.', file=sys.stderr)
        raise SystemExit(1)
