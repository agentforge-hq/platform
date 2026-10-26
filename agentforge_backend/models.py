from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Harness = Literal['codex', 'claude-code', 'cursor', 'gemini', 'opencode', 'devin', 'portable']


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1, max_length=2048)
    harness: Harness | None = None
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator('query')
    @classmethod
    def bounded_query(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value.encode('utf-8')) > 2048:
            raise ValueError('Describe a task using 1 to 2048 UTF-8 bytes.')
        return value


class Source(BaseModel):
    url: str
    repository: str
    revision: str
    skill_path: str
    manifest_sha256: str
    checked_at: str


class Skill(BaseModel):
    model_config = ConfigDict(extra='forbid')
    skill_id: str
    name: str
    summary: str
    category: str
    capabilities: list[str]
    example_prompts: list[str]
    requirements: list[str]
    exclusions: list[str]
    compatibility: dict[str, str]
    license: dict[str, str | None]
    source: Source
    adoption_status: Literal['review_required', 'metadata_only', 'unavailable']


class SearchMeta(BaseModel):
    status: Literal['matches', 'no_match']
    retrieval_mode: Literal['hybrid', 'lexical_only']
    catalog_revision: str
    ranking_version: str = 'hybrid-v1'
    request_id: str


class SearchResponse(BaseModel):
    rows: list[Skill]
    meta: SearchMeta


class CatalogResponse(BaseModel):
    rows: list[Skill]
    skill_count: int
    source_count: int
    categories: list[str]
    updated_at: str | None

