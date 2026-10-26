import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app
from agentforge_backend.models import SearchRequest, Skill
from agentforge_backend.retrieval import catalog_revision, fuse, lexical_score, terms
from ingest.catalog import parse_manifest


def fixture(name='review', skill_id='example/review'):
    return Skill(skill_id=skill_id,name=name,summary='Review authentication code and permission checks.',category='Engineering',capabilities=['Find missing permission checks'],example_prompts=['Review this authentication change.'],requirements=[],exclusions=[],compatibility={'harness':'portable','status':'unknown'},license={'identifier':'MIT','status':'declared'},source={'url':'https://github.com/example/skills','repository':'example/skills','revision':'a'*40,'skill_path':'review','manifest_sha256':'b'*64,'checked_at':'2026-10-26T00:00:00Z'},adoption_status='review_required')


@pytest.mark.parametrize('payload',[{'query':' '},{'query':'é'*1025},{'query':'task','limit':0},{'query':'task','limit':True},{'query':'task','harness':'made-up'},{'query':'task','transcript':'private'}])
def test_search_rejects_invalid_input(payload):
    with pytest.raises(ValidationError): SearchRequest.model_validate(payload)


def test_trimmed_task_keeps_only_contract_fields():
    request=SearchRequest(query='  review permissions  ',harness='codex')
    assert request.query=='review permissions' and request.limit==5


def test_fusion_deduplicates_skill_without_losing_other_candidates():
    first,second=fixture(),fixture('debug','example/debug')
    result=fuse(lexical=[(first,2),(first,1)],semantic=[(second,.8),(first,.7)],limit=3)
    assert len(result)==2 and result[0].skill_id==first.skill_id


def test_lexical_terms_ignore_filler_and_identifier_matches_have_weight():
    assert terms('Please help me with permission checks')==['permission','checks']
    assert lexical_score(fixture(),['permission'])>0
    assert lexical_score(fixture(),['unrelatedzebra'])==0


def test_catalog_revision_is_order_independent():
    a,b=fixture(),fixture('debug','example/debug')
    assert catalog_revision([a,b])==catalog_revision([b,a])


def test_metadata_only_for_unresolved_license_and_preserves_source_revision():
    raw=b'---\nname: sample\ndescription: |\n  Help explain a task.\nlicense: See LICENSE.txt\n---\n# Sample\nInstructions.'
    skill,body=parse_manifest(raw=raw,repository='example/skills',revision='a'*40,path='skills/sample/SKILL.md',license_id='MIT',checked_at='2026-10-26T00:00:00Z')
    assert skill.adoption_status=='metadata_only' and skill.license['identifier'] is None
    assert skill.source.revision=='a'*40 and skill.skill_id=='example/skills/skills/sample'
    assert 'Instructions.' in body


def test_invalid_frontmatter_does_not_become_a_listing():
    with pytest.raises(ValueError):
        parse_manifest(raw=b'not a skill',repository='example/skills',revision='a'*40,path='SKILL.md',license_id=None,checked_at='2026-10-26T00:00:00Z')


def test_http_validation_and_body_limits():
    client=TestClient(app.application)
    assert client.post('/v1/search',json={'query':'task','private_context':'secret'}).status_code==422
    assert client.post('/v1/search',content='x'*9000,headers={'Content-Type':'application/json'}).status_code==413
    assert client.post('/v1/search',content='task').status_code==415


def test_refresh_requires_its_own_secret_even_with_a_service_key(monkeypatch):
    monkeypatch.setenv('AGENTFORGE_INDEX_TOKEN','operator-only')
    client=TestClient(app.application)
    assert client.post('/internal/refresh',json={},headers={'X-api-key':'search-service-key'}).status_code==403
    assert client.post('/internal/refresh',json={},headers={'X-AgentForge-Index-Key':'wrong'}).status_code==403
