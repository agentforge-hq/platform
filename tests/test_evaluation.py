import json
import socket
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from evaluation.core import EvaluationError, HttpBudget, load_corpus, search_case, summarize, validate_capture
from evaluation.observation import append_sample, catalog_summary, probe

ROOT = Path(__file__).resolve().parents[1]


def result(ident, skills=(), status='matches', revision='catalog-1', ranking='rank-1'):
    return search_case(ident, {'outcome': 'ok', 'http_status': 200, 'attempts': 1, 'elapsed_ms': 2,
        'data': {'rows': [{'skill_id': skill, 'source': {'revision': 'upstream-1'}} for skill in skills],
                 'meta': {'status': status, 'retrieval_mode': 'hybrid',
                          'catalog_revision': revision, 'ranking_version': ranking}}})


def test_frozen_corpus_counts_labels_and_harness_separation():
    prompts, labels, manifest = load_corpus(ROOT / 'evaluation')
    assert len(prompts) == 100
    assert Counter(row['stratum'] for row in labels.values()) == {'relevant': 50, 'no_match': 25, 'trivial': 25}
    assert Counter(row['domain'] for row in labels.values() if row['stratum'] == 'relevant') == {
        'writing': 10, 'design': 10, 'engineering': 10, 'research': 10, 'operations': 10}
    assert manifest['human_review_status'] == 'pending'
    assert all('agentforge' not in text.lower() for text in prompts.values())
    assert all(label['source_evidence'] for label in labels.values() if label['stratum'] == 'relevant')


def test_modified_corpus_and_development_overlap_are_rejected(tmp_path):
    for name in ('freeze.json', 'prompts.json', 'labels.json'):
        (tmp_path / name).write_bytes((ROOT / 'evaluation' / name).read_bytes())
    prompts, _, _ = load_corpus(tmp_path)
    development = tmp_path / 'development.json'
    development.write_text(json.dumps({'prompts': [{'text': next(iter(prompts.values())).upper()}]}))
    with pytest.raises(EvaluationError, match='overlap'):
        load_corpus(tmp_path, development)
    with (tmp_path / 'prompts.json').open('a') as stream:
        stream.write(' ')
    with pytest.raises(EvaluationError, match='digest changed'):
        load_corpus(tmp_path)


def test_top_three_approval_no_match_and_errors_remain_separate():
    labels = {'a': {'stratum': 'relevant', 'approved_skill_ids': ['good']},
              'b': {'stratum': 'relevant', 'approved_skill_ids': ['good']},
              'c': {'stratum': 'no_match', 'approved_skill_ids': []},
              'd': {'stratum': 'no_match', 'approved_skill_ids': []},
              'e': {'stratum': 'trivial', 'approved_skill_ids': []}}
    cases = [result('a', ['other', 'good']), result('b', ['x', 'y', 'z', 'good']),
             result('c', ['irrelevant']), {'id': 'd', 'outcome': 'timeout', 'attempts': 1},
             result('e', [], 'no_match')]
    report = summarize(labels, cases, 'frozen')
    assert report['relevant']['approved_top_three'] == 1
    assert report['relevant']['rate_over_all_relevant'] == .5
    assert report['no_match']['retrieval_false_positives'] == 1
    assert report['no_match']['successful'] == 1
    assert report['counts']['errors'] == {'timeout': 1}
    assert report['complete'] is False
    assert report['release_gates_established'] is False
    assert report['human_review_status'] == 'pending'
    assert report['trivial']['harness_network_searches'] == 'not_measured'
    assert report['ac04'].startswith('not_measured')


def test_no_match_requires_empty_rows_and_revisions_must_be_consistent():
    assert result('x', ['bad'], 'no_match')['outcome'] == 'invalid_response'
    labels = {key: {'stratum': 'relevant', 'approved_skill_ids': ['good']} for key in ('a', 'b')}
    report = summarize(labels, [result('a', ['good']), result('b', ['good'], revision='different')], 'frozen')
    assert report['complete'] is True
    assert report['consistent_revisions'] is False
    assert report['relevant']['candidate_ac03_threshold_met'] is False


def test_capture_rejects_duplicate_unknown_or_wrong_corpus_ids():
    row = result('a', ['good'])
    assert validate_capture({'corpus_sha256': 'frozen', 'cases': [row]}, {'a'}, 'frozen') == [row]
    for capture in ({'corpus_sha256': 'wrong', 'cases': [row]},
                    {'corpus_sha256': 'frozen', 'cases': [row, row]},
                    {'corpus_sha256': 'frozen', 'cases': [dict(row, id='unknown')]}):
        with pytest.raises(EvaluationError):
            validate_capture(capture, {'a'}, 'frozen')


def test_http_retries_are_bounded_and_error_bodies_are_not_captured(monkeypatch):
    import urllib.error
    calls = []

    def limited(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError('http://localhost/search', 429, 'private query', {'Retry-After': '0'}, None)

    monkeypatch.setattr('urllib.request.urlopen', limited)
    monkeypatch.setattr('evaluation.core.time.sleep', lambda seconds: None)
    limited_result = HttpBudget(2, retries=2, interval=0).request('http://localhost/search', {'query': 'private'})
    assert len(calls) == 2
    assert limited_result['outcome'] == 'rate_limited'
    assert limited_result['attempts'] == 2
    assert [event['outcome'] for event in limited_result['attempt_events']] == ['rate_limited', 'rate_limited']
    assert limited_result['data'] is None
    assert 'private' not in json.dumps(limited_result)
    exhausted = HttpBudget(0, interval=0).request('http://localhost/search')
    assert exhausted['outcome'] == 'budget_exhausted' and exhausted['attempts'] == 0


def test_timeouts_and_invalid_json_have_explicit_outcomes(monkeypatch):
    import io

    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: (_ for _ in ()).throw(socket.timeout()))
    assert HttpBudget(1, retries=0, interval=0).request('http://localhost/search')['outcome'] == 'timeout'
    response = io.BytesIO(b'invalid JSON with private content')
    response.status = 200
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: response)
    invalid = HttpBudget(1, retries=0, interval=0).request('http://localhost/search')
    assert invalid['outcome'] == 'invalid_json'
    assert invalid['data'] is None


def test_public_observation_uses_actual_http_and_retains_no_body_or_query(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = {'rows': [{'source': {'checked_at': '2026-10-26T00:00:00Z'}, 'summary': 'private body'}],
                    'skill_count': 90, 'source_count': 6, 'updated_at': '2026-10-27T00:00:00Z', 'next_offset': 100}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode() if self.path.endswith('catalog') else b'private HTML')

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert set(payload) == {'query', 'harness', 'limit'}
            self.send_response(200)
            self.end_headers()
            row = result('probe', ['good'])
            self.wfile.write(json.dumps({'rows': [{'skill_id': 'good', 'source': {'revision': 'upstream'}}],
                                        'meta': row['meta']}).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        sample = probe(f'http://127.0.0.1:{server.server_port}', HttpBudget(3, interval=0, retries=0))
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert sample['availability']['outcome'] == 'ok'
    assert sample['catalog']['skill_count'] == 90
    assert sample['catalog']['catalog_sample_only'] is True
    assert sample['search']['catalog_revision'] == 'catalog-1'
    assert sample['observation_48h_complete'] is False
    path = tmp_path / 'observation.jsonl'
    append_sample(path, sample)
    append_sample(path, sample)
    assert len(path.read_text().splitlines()) == 2
    assert 'private' not in path.read_text().replace('private_evidence', '')
    assert 'Inspect permission' not in path.read_text()


def test_source_freshness_is_sampled_and_unknown_is_not_fresh():
    now = datetime(2026, 10, 27, tzinfo=timezone.utc)
    summary = catalog_summary({'rows': [{'source': {'checked_at': '2026-10-26T00:00:00Z'}}, {}],
                               'skill_count': 500, 'source_count': 8, 'next_offset': 100}, now)
    assert summary['source_checks']['oldest_age_seconds'] == 86400
    assert summary['source_checks']['unknown'] == 1
    assert summary['sampled_rows'] == 2
    assert summary['catalog_sample_only'] is True


def test_capture_cli_writes_redacted_incomplete_report(tmp_path):
    import subprocess
    import sys

    _, _, manifest = load_corpus(ROOT / 'evaluation')
    capture = tmp_path / 'input.json'
    capture.write_text(json.dumps({'corpus_sha256': manifest['corpus_sha256'],
                                   'cases': [result('p001', [], 'no_match')]}))
    report_path = tmp_path / 'report.json'
    completed = subprocess.run([sys.executable, str(ROOT / 'scripts/evaluate.py'),
                                '--responses', str(capture), '--output', str(report_path)],
                               capture_output=True, text=True)
    assert completed.returncode == 2
    report = json.loads(report_path.read_text())
    assert report['counts']['not_run'] == 99
    assert report['failed_cases'][0]['reason'] == 'no_approved_result_in_top_three'
    assert report['human_review_status'] == 'pending'
    assert report_path.with_suffix('.cases.json').exists()
    assert report_path.with_suffix('.failed.json').exists()
    serialized = report_path.read_text()
    assert 'rough notes' not in serialized
    assert 'query' not in serialized


def test_capture_does_not_accept_failed_http_status_as_a_match():
    row = result('a', ['good'])
    row['http_status'] = 500
    captured = validate_capture({'corpus_sha256': 'frozen', 'cases': [row]}, {'a'}, 'frozen')
    assert captured[0]['outcome'] == 'invalid_response'
