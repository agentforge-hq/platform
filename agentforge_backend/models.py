from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

Harness = Literal['codex', 'claude-code', 'cursor', 'gemini', 'opencode', 'devin', 'portable']


class SearchConstraints(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    available_tools: list[str] | None = Field(default=None, max_length=32)
    allow_setup: bool = True
    allow_credentials: bool = True

    @field_validator('available_tools')
    @classmethod
    def named_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}', tool) for tool in value):
            raise ValueError('Use tool names, not paths or credentials.')
        return sorted(set(tool.casefold() for tool in value))


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1, max_length=2048)
    harness: Harness | None = None
    limit: int = Field(default=5, ge=1, le=20)
    constraints: SearchConstraints | None = None

    @field_validator('query')
    @classmethod
    def bounded_query(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value.encode('utf-8')) > 2048:
            raise ValueError('Describe a task using 1 to 2048 UTF-8 bytes.')
        return value


class FieldEvidence(BaseModel):
    field: str = Field(max_length=64)
    quote: str = Field(max_length=480)
    location: str = Field(max_length=240)
    source_url: str
    status: Literal['declared', 'inferred'] = 'declared'


class CapabilityProfile(BaseModel):
    extractor_version: str = 'legacy'
    source_revision: str = ''
    outputs: list[str] = Field(default_factory=list, max_length=12)
    use_when: list[str] = Field(default_factory=list, max_length=12)
    avoid_when: list[str] = Field(default_factory=list, max_length=12)
    tools: list[str] = Field(default_factory=list, max_length=32)
    credentials: list[str] = Field(default_factory=list, max_length=12)
    evidence: list[FieldEvidence] = Field(default_factory=list, max_length=24)


class HarnessSupport(BaseModel):
    harness: Harness
    status: Literal['declared', 'inferred', 'tested', 'incompatible', 'unknown']
    detail: str = Field(max_length=480)
    evidence_url: str
    checked_at: str | None = None
    harness_version: str | None = None


class RecommendationFit(BaseModel):
    reason: str = Field(max_length=640)
    evidence: list[FieldEvidence] = Field(default_factory=list, max_length=3)
    missing_tools: list[str] = Field(default_factory=list, max_length=32)
    notes: list[str] = Field(default_factory=list, max_length=8)


class SourceFile(BaseModel):
    path: str
    git_blob_sha1: str = Field(pattern=r'^[a-f0-9]{40}$')


class Source(BaseModel):
    url: str
    repository: str
    revision: str
    skill_path: str
    manifest_sha256: str
    checked_at: str
    files: list[SourceFile] = Field(default_factory=list, max_length=200)
    discovered_via: list[str] = Field(default_factory=list, max_length=20)


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
    profile: CapabilityProfile = Field(default_factory=CapabilityProfile)
    harness_support: list[HarnessSupport] = Field(default_factory=list, max_length=12)
    fit: RecommendationFit | None = None
    author_metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)

    @field_validator('author_metadata')
    @classmethod
    def bounded_author_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(json.dumps(value, ensure_ascii=False).encode('utf-8')) > 16384:
            raise ValueError('Author metadata exceeds 16 KiB.')
        return value


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
    offset: int = 0
    limit: int = 100
    next_offset: int | None = None

