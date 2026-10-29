"""Prepare a blind local worksheet and validate a separately attested successor."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentforge_backend.publish import VersionInput
from agentforge_backend.retrieval import catalog_revision
from evaluation.core import EvaluationError, digest_file, load_corpus, load_json, normalized, utc_now

DOMAINS = {'writing', 'design', 'engineering', 'research', 'operations'}
ROOT = Path(__file__).resolve().parents[1]


def encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def make_packet(corpus: Path, catalog: Path) -> dict:
    prompts, _, freeze = load_corpus(corpus)
    raw = load_json(catalog)
    if not isinstance(raw, list) or not 1 <= len(raw) <= 2000:
        raise EvaluationError('Use a complete catalog snapshot containing 1 to 2000 immutable rows.')
    versions = [VersionInput.model_validate(row) for row in raw]
    if len({row.skill_id for row in versions}) != len(versions):
        raise EvaluationError('The review catalog contains duplicate skill identities.')
    identity = {'schema_version': 1, 'corpus_sha256': freeze['corpus_sha256'], 'catalog_sha256': digest_file(catalog)}
    packet_id = hashlib.sha256(encoded(identity).encode()).hexdigest()
    task_order = sorted(prompts, key=lambda ident: hashlib.sha256((packet_id + ident).encode()).digest())
    skills = []
    for row in sorted(versions, key=lambda row: (row.name.casefold(), row.skill_id)):
        payload = row.payload.model_dump(
            include={
                'skill_id',
                'name',
                'summary',
                'category',
                'requirements',
                'exclusions',
                'license',
                'source',
                'profile',
                'harness_support',
                'adoption_status',
            }
        )
        skills.append({**payload, 'version_id': row.version_id, 'body': row.body})
    return {
        **identity,
        'packet_id': packet_id,
        'created_at': utc_now(),
        'catalog_revision': catalog_revision([row.payload for row in versions]),
        'prompts': [{'id': ident, 'text': prompts[ident]} for ident in task_order],
        'skills': skills,
    }


def render_packet(packet: dict) -> str:
    font_dir = ROOT / 'node_modules/geist'
    font = font_dir / 'dist/fonts/geist-sans/Geist-Regular.woff2'
    license_file = font_dir / 'LICENSE.txt'
    if not font.exists() or not license_file.exists():
        raise EvaluationError('Install the existing website dependencies with npm ci before preparing the worksheet.')
    template = (ROOT / 'evaluation/review.html').read_text()
    template = template.replace('__FONT_DATA__', base64.b64encode(font.read_bytes()).decode())
    template = template.replace('__FONT_LICENSE__', license_file.read_text().replace('--', '- -'))
    data = encoded(packet).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return template.replace('__PACKET_DATA__', data)


def reviewed_rows(packet: dict, annotations: dict) -> list[dict]:
    expected = {'schema_version', 'packet_id', 'reviewer', 'attestation', 'annotations'}
    if not isinstance(annotations, dict) or set(annotations) != expected:
        raise EvaluationError('The review file has an unexpected shape. Export it from the worksheet.')
    if annotations['schema_version'] != 1 or annotations['packet_id'] != packet['packet_id']:
        raise EvaluationError('The review file belongs to a different corpus or catalog snapshot.')
    reviewer = annotations['reviewer']
    if not isinstance(reviewer, str) or not 2 <= len(reviewer.strip()) <= 120 or annotations['attestation'] is not True:
        raise EvaluationError('A named reviewer must attest to personally reviewing every task.')
    rows = annotations['annotations']
    if not isinstance(rows, list) or len(rows) != len(packet['prompts']):
        raise EvaluationError('Every task needs one completed review.')
    prompts = {row['id'] for row in packet['prompts']}
    skills = {row['skill_id']: row for row in packet['skills']}
    seen_ids, seen_texts = set(), set()
    result = []
    fields = {'id', 'text', 'stratum', 'domain', 'approved_skill_ids', 'rationale', 'reviewed_at'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise EvaluationError('A task review has unexpected or missing fields.')
        ident, text = row['id'], row['text']
        if not isinstance(ident, str) or ident not in prompts or ident in seen_ids:
            raise EvaluationError('Task identities must match the worksheet exactly once.')
        seen_ids.add(ident)
        if not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 2048:
            raise EvaluationError('Each task needs 1 to 2048 UTF-8 bytes of text.')
        clean_text = normalized(text)
        if not clean_text or clean_text in seen_texts:
            raise EvaluationError('Reviewed tasks must have distinct nonempty normalized text.')
        seen_texts.add(clean_text)
        stratum = row['stratum']
        if not isinstance(stratum, str) or stratum not in {'relevant', 'no_match', 'trivial'}:
            raise EvaluationError('Classify every task as relevant, no match, or trivial.')
        domain = row['domain']
        if not isinstance(domain, str) or domain not in (DOMAINS if stratum == 'relevant' else {'none'}):
            raise EvaluationError('Relevant tasks need a task family; other tasks use none.')
        approved = row['approved_skill_ids']
        if (
            not isinstance(approved, list)
            or any(not isinstance(item, str) for item in approved)
            or len(set(approved)) != len(approved)
            or not set(approved) <= skills.keys()
            or bool(approved) != (stratum == 'relevant')
        ):
            raise EvaluationError('Choose catalog identities for relevant tasks only, without duplicates.')
        rationale = row['rationale']
        if not isinstance(rationale, str) or not 5 <= len(rationale.strip()) <= 2000:
            raise EvaluationError('Record a reason of 5 to 2000 characters for every decision.')
        try:
            at = datetime.fromisoformat(row['reviewed_at'])
            if at.tzinfo is None or at > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError()
        except (TypeError, ValueError):
            raise EvaluationError('Every task must be marked reviewed with a valid timestamp.') from None
        result.append({**row, 'text': text.strip(), 'rationale': rationale.strip()})
    if Counter(row['stratum'] for row in result) != {'relevant': 50, 'no_match': 25, 'trivial': 25}:
        raise EvaluationError('The reviewed successor must retain 50 relevant, 25 no-match and 25 trivial tasks.')
    if Counter(row['domain'] for row in result if row['stratum'] == 'relevant') != dict.fromkeys(DOMAINS, 10):
        raise EvaluationError('Each of the five relevant task families needs ten reviewed tasks.')
    return result


def write_successor(packet: dict, annotations: dict, destination: Path) -> dict:
    reviews = reviewed_rows(packet, annotations)
    skills = {row['skill_id']: row for row in packet['skills']}
    prompts = {'prompts': [{'id': row['id'], 'text': row['text']} for row in reviews]}
    labels = {
        'labels': [
            {
                'id': row['id'],
                'stratum': row['stratum'],
                'domain': row['domain'],
                'approved_skill_ids': row['approved_skill_ids'],
                'rationale': row['rationale'],
                'source_evidence': [
                    {
                        'skill_id': ident,
                        'version_id': skills[ident]['version_id'],
                        'source_url': skills[ident]['source']['url'],
                        'revision': skills[ident]['source']['revision'],
                        'manifest_sha256': skills[ident]['source']['manifest_sha256'],
                        'quote': skills[ident]['summary'][:480],
                        'location': 'frontmatter.description',
                    }
                    for ident in row['approved_skill_ids']
                ],
            }
            for row in reviews
        ]
    }
    files = {
        name: json.dumps(value, indent=2, ensure_ascii=False) + '\n'
        for name, value in [('prompts.json', prompts), ('labels.json', labels)]
    }
    hashes = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in files.items()}
    freeze = {
        'schema_version': 1,
        'created_at': utc_now(),
        'files': hashes,
        'corpus_sha256': hashlib.sha256(encoded(hashes).encode()).hexdigest(),
        'human_review_status': 'attested_not_independently_verified',
        'reviewer': annotations['reviewer'].strip(),
        'annotations_sha256': hashlib.sha256(encoded(annotations).encode()).hexdigest(),
        'reviewed_from_corpus_sha256': packet['corpus_sha256'],
        'catalog_sha256': packet['catalog_sha256'],
        'catalog_revision': packet['catalog_revision'],
        'release_gates_established': False,
        'limitation': 'A local reviewer attestation is not authentication or a retroactive pre-tuning review gate.',
    }
    files['freeze.json'] = json.dumps(freeze, indent=2) + '\n'
    destination.mkdir(parents=False, exist_ok=False)
    for name, value in files.items():
        with (destination / name).open('x', encoding='utf-8') as output:
            output.write(value)
    load_corpus(destination)
    return freeze
