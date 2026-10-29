import hashlib
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from agentforge_backend.publish import VersionInput, version_id_for
from evaluation.core import EvaluationError, load_corpus, utc_now
from evaluation.review import encoded, make_packet, render_packet, reviewed_rows, write_successor
from test_backend import fixture


def inputs(tmp_path):
    corpus = tmp_path / 'original'
    corpus.mkdir()
    prompts = {'prompts': [{'id': f'task-{i}', 'text': f'Synthetic review task number {i}.'} for i in range(100)]}
    labels = {
        'labels': [
            {
                'id': f'task-{i}',
                'stratum': 'relevant' if i < 50 else 'no_match' if i < 75 else 'trivial',
                'domain': 'engineering',
                'approved_skill_ids': ['example/review'] if i < 50 else [],
                'rationale': 'EXPECTED_ANSWER_SENTINEL',
                'source_evidence': ['synthetic fixture'],
            }
            for i in range(100)
        ]
    }
    hashes = {}
    for name, value in [('prompts.json', prompts), ('labels.json', labels)]:
        content = json.dumps(value)
        (corpus / name).write_text(content)
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
    freeze = {'files': hashes, 'corpus_sha256': hashlib.sha256(encoded(hashes).encode()).hexdigest()}
    (corpus / 'freeze.json').write_text(json.dumps(freeze))
    skill = fixture()
    body = '</script><script>alert("source text must not execute")</script>\n# Synthetic source'
    version = VersionInput(
        version_id=version_id_for(skill, body),
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.summary,
        body=body,
        examples=skill.example_prompts,
        payload=skill,
    )
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps([version.model_dump()]))
    return corpus, catalog


def judgments(packet):
    domains = ['writing', 'design', 'engineering', 'research', 'operations']
    return {
        'schema_version': 1,
        'packet_id': packet['packet_id'],
        'reviewer': 'Synthetic fixture reviewer',
        'attestation': True,
        'annotations': [
            {
                **row,
                'stratum': 'relevant' if i < 50 else 'no_match' if i < 75 else 'trivial',
                'domain': domains[i // 10] if i < 50 else 'none',
                'approved_skill_ids': ['example/review'] if i < 50 else [],
                'rationale': 'Synthetic judgment for test coverage.',
                'reviewed_at': utc_now(),
            }
            for i, row in enumerate(packet['prompts'])
        ],
    }


def test_packet_hides_expected_answers_and_escapes_source_markup(tmp_path):
    packet = make_packet(*inputs(tmp_path))
    assert len(packet['prompts']) == 100
    assert [row['id'] for row in packet['prompts']] != [f'task-{i}' for i in range(100)]
    assert all(set(row) == {'id', 'text'} for row in packet['prompts'])
    assert 'EXPECTED_ANSWER_SENTINEL' not in encoded(packet)
    page = render_packet(packet)
    assert 'EXPECTED_ANSWER_SENTINEL' not in page
    assert '</script><script>alert' not in page
    assert '\\u003c/script\\u003e' in page
    assert "connect-src 'none'" in page


def test_worksheet_supports_every_required_task_family():
    class Options(HTMLParser):
        def __init__(self):
            super().__init__()
            self.domain = False
            self.values = set()

        def handle_starttag(self, tag, attrs):
            if tag == 'select':
                self.domain = dict(attrs).get('id') == 'domain'
            if self.domain and tag == 'option':
                self.values.add(dict(attrs).get('value'))

        def handle_endtag(self, tag):
            if tag == 'select':
                self.domain = False

    parsed = Options()
    parsed.feed((Path(__file__).resolve().parents[1] / 'evaluation/review.html').read_text())
    assert parsed.values == {'none', 'writing', 'design', 'engineering', 'research', 'operations'}


def test_catalog_and_corpus_are_bound_to_the_review_file(tmp_path):
    corpus, catalog = inputs(tmp_path)
    packet = make_packet(corpus, catalog)
    review = judgments(packet)
    changed = json.loads(catalog.read_text())
    changed[0]['payload']['source']['checked_at'] = '2026-10-28T00:00:00Z'
    catalog.write_text(json.dumps(changed))
    with pytest.raises(EvaluationError, match='different corpus or catalog'):
        reviewed_rows(make_packet(corpus, catalog), review)
    with (corpus / 'prompts.json').open('a') as output:
        output.write(' ')
    with pytest.raises(EvaluationError, match='digest changed'):
        make_packet(corpus, catalog)


@pytest.mark.parametrize(
    'change,message',
    [
        (lambda r: r.update(attestation=False), 'attest'),
        (lambda r: r['annotations'].pop(), 'Every task'),
        (lambda r: r['annotations'][0].update(reviewed_at=None), 'valid timestamp'),
        (lambda r: r['annotations'][0].update(approved_skill_ids=['invented/identity']), 'catalog identities'),
        (lambda r: r['annotations'][0].update(domain=[]), 'task family'),
        (lambda r: r['annotations'][0].update(stratum={}), 'Classify'),
        (lambda r: r['annotations'][0].update(rationale=''), 'reason'),
        (lambda r: r['annotations'][50].update(approved_skill_ids=['example/review']), 'catalog identities'),
        (lambda r: r['annotations'][0].update(domain='design'), 'ten reviewed'),
    ],
)
def test_incomplete_or_untrusted_judgments_cannot_make_a_successor(tmp_path, change, message):
    packet = make_packet(*inputs(tmp_path))
    review = judgments(packet)
    change(review)
    with pytest.raises(EvaluationError, match=message):
        write_successor(packet, review, tmp_path / 'successor')
    assert not (tmp_path / 'successor').exists()


def test_duplicate_task_text_is_rejected_after_human_edits(tmp_path):
    packet = make_packet(*inputs(tmp_path))
    review = judgments(packet)
    review['annotations'][1]['text'] = review['annotations'][0]['text'].upper()
    with pytest.raises(EvaluationError, match='distinct'):
        reviewed_rows(packet, review)


def test_successor_keeps_the_original_freeze_and_does_not_claim_release_approval(tmp_path):
    corpus, catalog = inputs(tmp_path)
    originals = {path.name: path.read_bytes() for path in corpus.iterdir()}
    packet = make_packet(corpus, catalog)
    review = judgments(packet)
    review['annotations'][0]['text'] = 'A revised synthetic task for the successor.'
    first_id = review['annotations'][0]['id']
    destination = tmp_path / 'successor'
    freeze = write_successor(packet, review, destination)
    prompts, labels, manifest = load_corpus(destination)
    assert prompts[first_id] == review['annotations'][0]['text']
    assert labels[first_id]['source_evidence'][0]['version_id'] == packet['skills'][0]['version_id']
    assert manifest['corpus_sha256'] != packet['corpus_sha256']
    assert freeze['human_review_status'] == 'attested_not_independently_verified'
    assert freeze['release_gates_established'] is False
    assert {path.name: path.read_bytes() for path in corpus.iterdir()} == originals
    with pytest.raises(FileExistsError):
        write_successor(packet, review, destination)
    assert load_corpus(destination)[2] == manifest


def test_prepare_cli_prints_counts_without_task_text_and_preserves_existing_files(tmp_path):
    corpus, catalog = inputs(tmp_path)
    target = tmp_path / 'worksheet.html'
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / 'scripts/review.py'),
        'prepare',
        '--corpus',
        str(corpus),
        '--catalog',
        str(catalog),
        '--output',
        str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['tasks'] == 100
    assert 'Synthetic review task' not in completed.stdout
    original = target.read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode == 1
    assert target.read_bytes() == original
