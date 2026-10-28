from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

import app
from agentforge_backend.models import HarnessSupport, SearchRequest, SearchConstraints
from agentforge_backend.retrieval import catalog_revision, eligible, explain_fit, lexical_candidates
from test_backend import fixture


def profiled():
    skill = fixture('permission-review')
    skill.profile.extractor_version = 'profile-v1'
    skill.profile.source_revision = skill.source.revision
    skill.profile.outputs = ['A report of missing permission checks']
    skill.profile.tools = ['python']
    return skill


def test_explicit_constraints_do_not_upload_inventory_or_accept_paths():
    with pytest.raises(ValidationError):
        SearchConstraints(available_tools=['/private/path/python'])
    with pytest.raises(ValidationError):
        SearchConstraints(available_tools=['python'] * 33)
    with pytest.raises(ValidationError):
        SearchConstraints(allow_setup='false')
    with pytest.raises(ValidationError):
        SearchRequest(query='review', constraints={'installed_skills': ['private']})
    assert SearchConstraints(available_tools=['Python3', 'git', 'git']).available_tools == ['git', 'python3']


def test_constraints_exclude_known_setup_and_credentials_but_not_unknown():
    skill = profiled()
    assert not eligible(
        skill, SearchRequest(query='permissions', constraints={'available_tools': ['node'], 'allow_setup': False})
    )
    assert eligible(
        skill, SearchRequest(query='permissions', constraints={'available_tools': ['python3.11'], 'allow_setup': False})
    )
    skill.profile.credentials = ['API key']
    assert not eligible(skill, SearchRequest(query='permissions', constraints={'allow_credentials': False}))
    unknown = fixture('unknown')
    assert eligible(unknown, SearchRequest(query='permissions', constraints={'allow_credentials': False}))
    assert any(
        'not been established' in note for note in explain_fit(unknown, SearchRequest(query='permissions')).fit.notes
    )


def test_harness_exclusion_does_not_turn_unknown_support_into_tested():
    skill = profiled()
    skill.harness_support = [
        HarnessSupport(harness='codex', status='incompatible', detail='not supported', evidence_url=skill.source.url)
    ]
    # Validate at the same boundary used for collected payloads.
    skill = type(skill).model_validate(skill.model_dump())
    assert not eligible(skill, SearchRequest(query='permissions', harness='codex'))
    other = explain_fit(skill, SearchRequest(query='permissions', harness='cursor'))
    assert other.compatibility == {'harness': 'cursor', 'status': 'unknown'}


def test_keyword_fallback_abstains_on_generic_and_one_weak_overlap():
    skill = profiled()
    assert lexical_candidates([skill], 'Please help me review this') == []
    assert lexical_candidates([skill], 'check turtle permission biology') == []
    assert lexical_candidates([skill], 'permission-review')[0][0].skill_id == skill.skill_id
    assert lexical_candidates([skill], 'find missing permission checks')[0][0].skill_id == skill.skill_id


def test_fit_quotes_pinned_source_and_reports_setup_without_confidence_claim():
    skill = profiled()
    result = explain_fit(
        skill, SearchRequest(query='permission report', harness='codex', constraints={'available_tools': []})
    )
    assert result.fit.evidence[0].source_url == skill.source.url
    assert result.fit.evidence[0].quote in skill.summary
    assert result.fit.missing_tools == ['python']
    assert result.compatibility['status'] == 'unknown'
    assert '%' not in result.fit.reason


def test_catalog_revision_tracks_profile_changes_but_not_refresh_timestamps():
    skill = profiled()
    original = catalog_revision([skill])
    skill.source.checked_at = '2026-10-28T00:00:00Z'
    assert catalog_revision([skill]) == original
    skill.profile.outputs.append('A second genuinely different output')
    assert catalog_revision([skill]) != original


def test_browse_pages_filter_before_count_and_have_a_stable_next_offset(monkeypatch):
    rows = [fixture(f'review-{i}', f'example/{i}') for i in range(60)]
    monkeypatch.setattr(app, 'current_rows', lambda *args: rows)
    client = TestClient(app.application)
    first = client.get('/v1/catalog?limit=50').json()
    second = client.get('/v1/catalog?offset=50&limit=50').json()
    assert first['skill_count'] == 60 and first['next_offset'] == 50
    assert len(first['rows']) == 50 and len(second['rows']) == 10
    assert second['next_offset'] is None
    assert not ({row['skill_id'] for row in first['rows']} & {row['skill_id'] for row in second['rows']})
    assert client.get('/v1/catalog?limit=51').status_code == 422
    assert client.get('/v1/catalog?offset=-1').status_code == 422
    assert client.get('/v1/catalog?category=Writing').json()['rows'] == []


def test_keyword_candidates_read_profile_fields_after_long_descriptions():
    skill = profiled()
    skill.summary = ' '.join(f'word{n}' for n in range(100))
    skill.capabilities = []
    skill.profile.outputs = ['A pineapple telescope']
    assert lexical_candidates([skill], 'pineapple telescope')[0][0].skill_id == skill.skill_id


def test_ordinary_task_semantics_outrank_an_isolated_keyword_candidate():
    from agentforge_backend.retrieval import fuse

    keyword = fixture('execution-plans', 'example/execution-plans')
    semantic = fixture('sql-optimization', 'example/sql-optimization')
    assert fuse(lexical=[(keyword, 20)], semantic=[(semantic, 0.76)], limit=2)[0] == semantic


def test_acknowledgments_have_no_discovery_terms():
    from agentforge_backend.retrieval import terms

    assert terms('Thanks, that helps.') == []
    assert terms('Great, perfect!') == []
