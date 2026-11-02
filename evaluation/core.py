"""Validate frozen cases, bound HTTP calls, and score retrieval independently."""
from __future__ import annotations

import hashlib
import json
import math
import re
import socket
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class EvaluationError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def load_json(path: Path) -> Any:
    if path.stat().st_size > 10_000_000:
        raise EvaluationError('Input exceeds the 10 MB evaluation limit.')
    return json.loads(path.read_text())


def load_corpus(directory: Path, development: Path | None = None) -> tuple[dict, dict, dict]:
    manifest = load_json(directory / 'freeze.json')
    hashes = manifest['files']
    if set(hashes) != {'prompts.json', 'labels.json'}:
        raise EvaluationError('The freeze must name exactly the prompt and label files.')
    for name, expected in hashes.items():
        if digest_file(directory / name) != expected:
            raise EvaluationError(f'Frozen file digest changed: {name}.')
    combined = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if combined != manifest['corpus_sha256']:
        raise EvaluationError('The corpus digest does not match the frozen files.')
    prompt_rows = load_json(directory / 'prompts.json')['prompts']
    label_rows = load_json(directory / 'labels.json')['labels']
    if any(set(row) != {'id', 'text'} or not isinstance(row['text'], str) or not row['text'].strip()
           for row in prompt_rows):
        raise EvaluationError('Harness prompts must contain only an ID and nonempty text.')
    prompts = {row['id']: row['text'] for row in prompt_rows}
    labels = {row['id']: row for row in label_rows}
    if len(prompts) != len(prompt_rows) or len(labels) != len(label_rows) or set(prompts) != set(labels):
        raise EvaluationError('Prompt and label IDs must be unique and equal.')
    if len({normalized(text) for text in prompts.values()}) != len(prompts):
        raise EvaluationError('The corpus contains duplicate prompt text.')
    counts = Counter(row['stratum'] for row in labels.values())
    if counts != {'relevant': 50, 'no_match': 25, 'trivial': 25}:
        raise EvaluationError('The frozen corpus must retain its 50/25/25 split.')
    if any(bool(row['approved_skill_ids']) != (row['stratum'] == 'relevant') for row in labels.values()):
        raise EvaluationError('Relevant labels require approved IDs; other strata must abstain.')
    if development is not None:
        rows = load_json(development)['prompts']
        dev = {normalized(row['text']) for row in rows}
        if dev & {normalized(text) for text in prompts.values()}:
            raise EvaluationError('Development prompts overlap the held-out corpus.')
    return prompts, labels, manifest


def validate_url(url: str) -> str:
    parts = urlsplit(url)
    if (parts.scheme not in {'http', 'https'} or not parts.netloc or parts.username or parts.password
            or parts.query or parts.fragment):
        raise EvaluationError('Use a public HTTP endpoint without credentials, query strings, or fragments.')
    return url


@dataclass
class HttpBudget:
    remaining: int = 100
    timeout: float = 15
    retries: int = 1
    interval: float = 4
    max_retry_wait: float = 30
    next_request: float = 0

    def request(self, url: str, payload: dict | None = None, *, json_response: bool = True) -> dict:
        validate_url(url)
        started = time.monotonic()
        attempts = 0
        events = []
        outcome, status, data = 'budget_exhausted', None, None
        while attempts <= self.retries and self.remaining > 0:
            time.sleep(max(0, self.next_request - time.monotonic()))
            self.remaining -= 1
            attempts += 1
            self.next_request = time.monotonic() + self.interval
            request = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                                             headers={'Accept': 'application/json' if json_response else 'text/html',
                                                      'Content-Type': 'application/json',
                                                      'User-Agent': 'AgentForge-pilot-evaluation/1'})
            retry_wait = 0.0
            status = None
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status = response.status
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    outcome = 'response_too_large'
                elif json_response:
                    try:
                        data = json.loads(raw)
                        outcome = 'ok'
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        outcome = 'invalid_json'
                else:
                    outcome = 'ok'
            except urllib.error.HTTPError as error:
                status = error.code
                outcome = 'rate_limited' if status == 429 else 'http_error'
                if status == 429:
                    header = error.headers.get('Retry-After', '')
                    try:
                        retry_wait = max(0.0, float(header))
                    except ValueError:
                        try:
                            retry_wait = max(0.0, parsedate_to_datetime(header).timestamp() - time.time())
                        except (TypeError, ValueError, OverflowError):
                            retry_wait = 0.0
                error.close()
            except (TimeoutError, socket.timeout):
                outcome = 'timeout'
            except urllib.error.URLError as error:
                outcome = 'timeout' if isinstance(error.reason, (TimeoutError, socket.timeout)) else 'network_error'
            except OSError:
                outcome = 'network_error'
            events.append({'outcome': outcome, 'http_status': status})
            retryable = outcome in {'rate_limited', 'timeout', 'network_error'} or (status is not None and status >= 500)
            if not retryable or attempts > self.retries or self.remaining <= 0:
                break
            if retry_wait > self.max_retry_wait:
                break
            self.next_request = max(self.next_request, time.monotonic() + max(retry_wait, min(2 ** attempts, 8)))
        return {'outcome': outcome, 'http_status': status, 'attempts': attempts, 'attempt_events': events,
                'elapsed_ms': round((time.monotonic() - started) * 1000, 2), 'data': data}


def search_case(ident: str, transport: dict) -> dict:
    record = {key: transport.get(key) for key in ('outcome', 'http_status', 'attempts', 'elapsed_ms')}
    record['id'] = ident
    record['attempt_events'] = [{'outcome': event['outcome'], 'http_status': event['http_status']}
                                for event in transport.get('attempt_events', [])]
    if record['outcome'] != 'ok':
        return record
    try:
        if record['http_status'] != 200:
            raise EvaluationError('Successful search capture requires HTTP 200.')
        body = transport['data']
        rows, meta = body['rows'], body['meta']
        if (not isinstance(rows, list) or meta['status'] not in {'matches', 'no_match'}
                or meta['retrieval_mode'] not in {'hybrid', 'lexical_only'}
                or bool(rows) != (meta['status'] == 'matches')):
            raise EvaluationError('Invalid search response.')
        for key in ('catalog_revision', 'ranking_version'):
            if not isinstance(meta[key], str) or not meta[key]:
                raise EvaluationError('Missing response revision.')
        normalized_rows = []
        for row in rows[:20]:
            if not isinstance(row['skill_id'], str) or not row['skill_id']:
                raise EvaluationError('Missing skill identity.')
            revision = row['source']['revision']
            if not isinstance(revision, str) or not revision:
                raise EvaluationError('Missing source revision.')
            normalized_rows.append({'skill_id': row['skill_id'], 'source_revision': revision})
        record.update({'rows': normalized_rows, 'meta': {key: meta[key] for key in
                       ('status', 'retrieval_mode', 'catalog_revision', 'ranking_version')}})
    except (KeyError, TypeError, EvaluationError):
        record['outcome'] = 'invalid_response'
    return record


def validate_capture(raw: dict, prompt_ids: set[str], corpus_sha256: str) -> list[dict]:
    if raw.get('corpus_sha256') != corpus_sha256:
        raise EvaluationError('Captured responses belong to a different frozen corpus.')
    cases = raw.get('cases')
    if not isinstance(cases, list):
        raise EvaluationError('A capture requires a cases array.')
    ids = [case['id'] for case in cases]
    if len(set(ids)) != len(ids) or not set(ids) <= prompt_ids:
        raise EvaluationError('Captured IDs must be unique members of the frozen corpus.')
    allowed = {'ok', 'rate_limited', 'http_error', 'timeout', 'network_error', 'invalid_json',
               'response_too_large', 'invalid_response', 'budget_exhausted'}
    output = []
    for case in cases:
        attempts = case.get('attempts')
        elapsed = case.get('elapsed_ms')
        if (type(attempts) is not int or attempts < 0 or type(elapsed) not in {int, float}
                or not math.isfinite(elapsed) or elapsed < 0):
            raise EvaluationError('Captured attempts and elapsed time must be nonnegative numbers.')
        if case.get('outcome') not in allowed:
            raise EvaluationError('Unrecognized captured outcome.')
        transport = {key: case.get(key) for key in ('outcome', 'http_status', 'attempts', 'elapsed_ms')}
        events = case.get('attempt_events', [])
        if (not isinstance(events, list) or len(events) > 3 or any(
                not isinstance(event, dict) or event.get('outcome') not in allowed
                or (event.get('http_status') is not None and type(event['http_status']) is not int)
                for event in events)):
            raise EvaluationError('Invalid captured attempt events.')
        transport['attempt_events'] = events
        if case['outcome'] == 'ok':
            transport['data'] = case.get('response', {'rows': [
                {'skill_id': row['skill_id'], 'source': {'revision': row['source_revision']}}
                for row in case.get('rows', [])], 'meta': case.get('meta')})
        output.append(search_case(case['id'], transport))
    return output


def summarize(labels: dict, cases: list[dict], corpus_sha256: str) -> dict:
    observed = {case['id']: case for case in cases}
    counts = Counter(row['stratum'] for row in labels.values())
    successful = Counter()
    relevant_hits = no_match_false_positives = trivial_matches = 0
    failures = []
    revisions, rankings, modes = set(), set(), Counter()
    for ident, label in labels.items():
        case = observed.get(ident)
        reason = None
        if case is None or case['outcome'] != 'ok':
            reason = 'not_run' if case is None else case['outcome']
        else:
            successful[label['stratum']] += 1
            revisions.add(case['meta']['catalog_revision'])
            rankings.add(case['meta']['ranking_version'])
            modes[case['meta']['retrieval_mode']] += 1
            top_three = [row['skill_id'] for row in case['rows'][:3]]
            if label['stratum'] == 'relevant':
                if set(top_three) & set(label['approved_skill_ids']):
                    relevant_hits += 1
                else:
                    reason = 'no_approved_result_in_top_three'
            elif case['rows']:
                if label['stratum'] == 'no_match':
                    no_match_false_positives += 1
                else:
                    trivial_matches += 1
                reason = 'retrieval_returned_unapproved_match'
        if reason:
            failures.append({'id': ident, 'stratum': label['stratum'], 'reason': reason,
                             'returned_skill_ids': [row['skill_id'] for row in (case or {}).get('rows', [])[:3]],
                             'approved_skill_ids': label['approved_skill_ids']})
    complete = set(observed) == set(labels) and sum(successful.values()) == len(labels)
    consistent = len(revisions) == 1 and len(rankings) == 1
    errors = Counter(case['outcome'] for case in cases if case['outcome'] != 'ok')
    attempt_errors = Counter(event['outcome'] for case in cases for event in case.get('attempt_events', [])
                             if event['outcome'] != 'ok')
    return {'schema_version': 1, 'generated_at': utc_now(), 'corpus_sha256': corpus_sha256,
            'human_review_status': 'pending', 'release_gates_established': False,
            'scope': 'Direct retrieval only. Invocation, visible suggestions, adoption, and task lift are not measured.',
            'catalog_revisions': sorted(revisions), 'ranking_versions': sorted(rankings),
            'consistent_revisions': consistent, 'complete': complete,
            'counts': {'expected': len(labels), 'attempted_cases': len(cases), 'successful_cases': sum(successful.values()),
                       'not_run': len(labels) - len(observed), 'errors': dict(errors),
                       'attempt_errors': dict(attempt_errors),
                       'http_attempts': sum(case.get('attempts') or 0 for case in cases),
                       'error_rate_over_attempted_cases': sum(errors.values()) / len(cases) if cases else None},
            'retrieval_modes': dict(modes),
            'relevant': {'total': counts['relevant'], 'successful': successful['relevant'],
                         'approved_top_three': relevant_hits,
                         'rate_over_all_relevant': relevant_hits / counts['relevant'] if counts['relevant'] else None,
                         'candidate_ac03_threshold_met': complete and consistent and relevant_hits >= 40},
            'no_match': {'total': counts['no_match'], 'successful': successful['no_match'],
                         'retrieval_false_positives': no_match_false_positives,
                         'false_positive_rate_over_successful': no_match_false_positives / successful['no_match']
                         if successful['no_match'] else None},
            'trivial': {'total': counts['trivial'], 'successful': successful['trivial'],
                        'retrieval_matches': trivial_matches, 'harness_network_searches': 'not_measured'},
            'ac04': 'not_measured_fresh_harness_sessions_required', 'task_lift': 'not_measured',
            'failed_cases': failures}
