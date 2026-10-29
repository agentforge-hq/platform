"""Append redacted public probes without claiming private operating evidence."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from evaluation.core import EvaluationError, HttpBudget, search_case, utc_now, validate_url

PROBE_QUERY = 'Inspect permission checks in an application change.'


def catalog_summary(body: dict, now: datetime) -> dict:
    rows = body['rows']
    if not isinstance(rows, list) or not isinstance(body['skill_count'], int) or not isinstance(body['source_count'], int):
        raise EvaluationError('Invalid public catalog response.')
    checked = []
    unknown = 0
    for row in rows:
        stamp = row.get('source', {}).get('checked_at')
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if parsed.tzinfo is None or parsed > now:
                raise ValueError('Invalid source timestamp.')
            checked.append(parsed)
        except (AttributeError, TypeError, ValueError):
            unknown += 1
    return {'skill_count': body['skill_count'], 'source_count': body['source_count'],
            'sampled_rows': len(rows), 'publication_updated_at': safe_timestamp(body.get('updated_at')),
            'source_checks': {'observed': len(checked), 'unknown': unknown,
                              'oldest': min(checked).isoformat() if checked else None,
                              'newest': max(checked).isoformat() if checked else None,
                              'oldest_age_seconds': round((now - min(checked)).total_seconds(), 2) if checked else None},
            'catalog_sample_only': body.get('next_offset') is not None}


def safe_timestamp(value: object) -> str | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def probe(origin: str, budget: HttpBudget) -> dict:
    validate_url(origin)
    if urlsplit(origin).path not in {'', '/'}:
        raise EvaluationError('Observation requires an origin without a route.')
    origin = origin.rstrip('/')
    available = budget.request(origin + '/', json_response=False)
    catalog = budget.request(origin + '/api/v1/catalog')
    search = search_case('operating-probe', budget.request(origin + '/api/v1/search',
                         {'query': PROBE_QUERY, 'harness': 'codex', 'limit': 3}))
    fields = ('outcome', 'http_status', 'attempts', 'elapsed_ms', 'attempt_events')
    record = {'schema_version': 1, 'observed_at': utc_now(), 'public_origin': origin,
              'availability': {key: available[key] for key in fields},
              'catalog': {key: catalog[key] for key in fields},
              'search': {key: search[key] for key in fields},
              'probe_query_sha256': hashlib.sha256(PROBE_QUERY.encode()).hexdigest(),
              'private_evidence': {'refresh_job_failures': 'unavailable_from_public_endpoint',
                                   'provider_spend': 'unavailable_from_public_endpoint'},
              'observation_48h_complete': False}
    if catalog['outcome'] == 'ok':
        try:
            record['catalog'].update(catalog_summary(catalog['data'], datetime.now(timezone.utc)))
        except (EvaluationError, TypeError, KeyError, AttributeError):
            record['catalog']['outcome'] = 'invalid_response'
    if search['outcome'] == 'ok':
        record['search'].update(search['meta'])
        record['search']['returned_count'] = len(search['rows'])
    return record


def append_sample(path: Path, sample: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(sample, separators=(',', ':')) + '\n')
        stream.flush()


def collect(origin: str, output: Path, samples: int, interval: float, budget: HttpBudget) -> None:
    started = time.monotonic()
    for index in range(samples):
        time.sleep(max(0, started + index * interval - time.monotonic()))
        sample = probe(origin, budget)
        sample['sample_number'] = index + 1
        sample['session_elapsed_seconds'] = round(time.monotonic() - started, 2)
        append_sample(output, sample)
        print(json.dumps({'sample': index + 1, 'observed_at': sample['observed_at'],
                          'availability': sample['availability']['outcome'],
                          'catalog': sample['catalog']['outcome'], 'search': sample['search']['outcome']}), flush=True)
        if budget.remaining == 0:
            break
