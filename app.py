"""AgentForge catalog and read-only search. Apply with pxt schema/service update."""

from __future__ import annotations

import functools
import hmac
import os
import logging
import uuid

import numpy as np
import pixeltable as pxt
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pixeltable.serving import FastAPIRouter

from agentforge_backend.models import CatalogResponse, Harness, SearchRequest, SearchResponse, Skill
from agentforge_backend.publish import PublishRequest, publish_rows
from agentforge_backend.retrieval import (
    RANKING_VERSION,
    SEMANTIC_FLOOR,
    catalog_revision,
    compatibility_for,
    eligible,
    explain_fit,
    fuse,
    lexical_candidates,
    terms,
)

logger = logging.getLogger('agentforge')
TableModel = pxt.model_base()


@functools.lru_cache(maxsize=1)
def embedding_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name='BAAI/bge-small-en-v1.5', threads=2)


@pxt.udf
def embed_text(text: str) -> pxt.Array[(384,), np.float32]:
    return np.asarray(next(embedding_model().embed([text])), dtype=np.float32)


@pxt.udf
def search_text(name: str, description: str, body: str, examples: pxt.Json) -> str:
    return '\n'.join([name, description, *[str(p) for p in examples], body[:12000]])


@pxt.udf
def profile_search_text(name: str, description: str, body: str, examples: pxt.Json, payload: pxt.Json) -> str:
    profile = payload.get('profile', {})
    sections = [name, description]
    for field in ('outputs', 'use_when'):
        sections.extend(str(value) for value in profile.get(field, []))
    sections.extend(str(value) for value in examples)
    sections.extend(str(value) for value in payload.get('capabilities', []))
    sections.extend(str(value) for value in payload.get('requirements', []))
    sections.append(body[:6000])
    return '\n'.join(sections)[:16000]


class Sources(TableModel, name='sources'):
    skill_id = pxt.Column(pxt.String, primary_key=True)
    published_version: pxt.String
    checked_at: pxt.String


class Versions(TableModel, name='skill_versions'):
    version_id = pxt.Column(pxt.String, primary_key=True)
    skill_id: pxt.String
    name: pxt.String
    description: pxt.String
    body: pxt.String
    examples: pxt.Json
    payload: pxt.Json
    indexed_text = search_text(name, description, body, examples)
    profiled_text = profile_search_text(name, description, body, examples, payload)
    __indexes__ = [
        pxt.EmbeddingIndex(indexed_text, embedding=embed_text, name='skill_meaning'),
        pxt.EmbeddingIndex(profiled_text, embedding=embed_text, name='skill_meaning_v2'),
    ]


api = FastAPIRouter(name='agentforge')
application = FastAPI(title='AgentForge discovery', version='0.1.0')


@application.middleware('http')
async def bound_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    is_refresh = request.url.path.rstrip('/').endswith('/internal/refresh')
    if is_refresh:
        expected = os.environ.get('AGENTFORGE_INDEX_TOKEN', '')
        if not expected or not hmac.compare_digest(request.headers.get('x-agentforge-index-key', ''), expected):
            return JSONResponse({'error': {'code': 'forbidden', 'message': 'Not authorized.'}}, status_code=403)
    body_limit = 33_554_432 if is_refresh else 8192
    if request.method == 'POST':
        if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
            return JSONResponse(
                {'error': {'code': 'content_type', 'message': 'Send application/json.'}, 'request_id': request_id},
                status_code=415,
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > body_limit:
                return JSONResponse(
                    {
                        'error': {'code': 'body_limit', 'message': 'Request body exceeds the route size limit.'},
                        'request_id': request_id,
                    },
                    status_code=413,
                )
        request._body = bytes(body)
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    return response


def published_versions() -> list[str]:
    sources = Sources.table
    return [row['published_version'] for row in sources.select(sources.published_version).collect()]


def current_rows(version_ids: list[str] | None = None) -> list[Skill]:
    versions = Versions.table
    version_ids = published_versions() if version_ids is None else version_ids
    if not version_ids:
        return []
    result = (
        versions.where(versions.version_id.isin(version_ids)).select(versions.version_id, versions.payload).collect()
    )
    checked = {
        row['published_version']: row['checked_at']
        for row in Sources.table.select(Sources.table.published_version, Sources.table.checked_at).collect()
    }
    rows = [(row['version_id'], Skill.model_validate(row['payload'])) for row in result]
    return [
        skill.model_copy(
            update={
                'source': skill.source.model_copy(
                    update={'checked_at': checked.get(version_id, skill.source.checked_at)}
                )
            }
        )
        for version_id, skill in rows
    ]


@api.get('/healthz')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'agentforge'}


@api.get('/v1/catalog', response_model=CatalogResponse)
def catalog(
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=50, ge=1, le=50),
    category: str | None = None,
    harness: Harness | None = None,
) -> CatalogResponse:
    try:
        rows = current_rows()
    except Exception:
        raise HTTPException(503, detail='The skill catalog is temporarily unavailable.') from None
    request = SearchRequest(query='browse', harness=harness)
    available = [row for row in rows if eligible(row, request)]
    categories = sorted({row.category for row in available})
    filtered = sorted(
        (row for row in available if not category or row.category == category),
        key=lambda row: (row.category, row.name, row.skill_id),
    )
    selected = [
        row.model_copy(update={'compatibility': compatibility_for(row, harness)})
        for row in filtered[offset : offset + limit]
    ]
    return CatalogResponse(
        rows=selected,
        skill_count=len(rows),
        filtered_count=len(filtered),
        source_count=len({row.source.repository for row in available}),
        categories=categories,
        updated_at=max((row.source.checked_at for row in rows), default=None),
        offset=offset,
        limit=limit,
        next_offset=offset + limit if offset + limit < len(filtered) else None,
    )


@api.post('/v1/search', response_model=SearchResponse)
def search(body: SearchRequest, request: Request) -> SearchResponse:
    request_id = request.state.request_id
    try:
        version_ids = published_versions()
        rows = current_rows(version_ids)
    except Exception:
        logger.exception('search_catalog_failed')
        raise HTTPException(503, detail='The skill catalog is temporarily unavailable.') from None
    if not rows:
        raise HTTPException(503, detail='The catalog is being prepared. Please try again shortly.')
    allowed = [row for row in rows if eligible(row, body)]
    lexical = lexical_candidates(allowed, body.query)
    semantic: list[tuple[Skill, float]] = []
    mode = 'hybrid'
    if allowed and terms(body.query):
        try:
            versions = Versions.table
            similarity = versions.profiled_text.similarity(string=body.query)
            by_id = {skill.skill_id: skill for skill in allowed}
            frame = versions.where(versions.version_id.isin(version_ids) & versions.skill_id.isin(list(by_id)))
            result = (
                frame.select(versions.skill_id, score=similarity).order_by(similarity, asc=False).limit(50).collect()
            )
            semantic = [
                (by_id[row['skill_id']], float(row['score'])) for row in result if row['score'] >= SEMANTIC_FLOOR
            ]
        except Exception as exc:
            logger.warning('semantic_search_unavailable type=%s request_id=%s', type(exc).__name__, request_id)
            mode = 'lexical_only'
    result_rows = [explain_fit(skill, body) for skill in fuse(lexical=lexical, semantic=semantic, limit=body.limit)]
    return SearchResponse(
        rows=result_rows,
        meta={
            'status': 'matches' if result_rows else 'no_match',
            'retrieval_mode': mode,
            'catalog_revision': catalog_revision(rows),
            'request_id': request_id,
            'ranking_version': RANKING_VERSION,
        },
    )


@api.post('/internal/refresh')
def refresh(body: PublishRequest, request: Request) -> dict[str, int]:
    expected = os.environ.get('AGENTFORGE_INDEX_TOKEN', '')
    if not expected or not hmac.compare_digest(request.headers.get('x-agentforge-index-key', ''), expected):
        raise HTTPException(403, detail='Not authorized.')
    return publish_rows(
        sources=Sources.table, versions=Versions.table, rows=body.rows, complete_repositories=body.complete_repositories
    )


application.include_router(api)
