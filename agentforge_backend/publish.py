from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentforge_backend.models import Skill


def canonical_version(skill: Skill, body: str) -> dict[str, Any]:
    """The immutable content; refresh times and per-search fit do not create versions."""
    payload = skill.model_dump(exclude={'fit'})
    payload['source'].pop('checked_at', None)
    for support in payload['harness_support']:
        support.pop('checked_at', None)
    return {'payload': payload, 'body': body}


def version_id_for(skill: Skill, body: str) -> str:
    identity = skill.skill_id + '@' + skill.source.revision
    if skill.profile.extractor_version == 'legacy':
        return identity
    encoded = json.dumps(
        canonical_version(skill, body), sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode()
    return identity + '#' + hashlib.sha256(encoded).hexdigest()


class VersionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version_id: str
    skill_id: str
    name: str = Field(max_length=120)
    description: str = Field(max_length=1800)
    body: str = Field(max_length=128000)
    examples: list[str] = Field(max_length=10)
    payload: Skill

    @model_validator(mode='after')
    def pinned_identity(self):
        if self.skill_id != self.payload.skill_id or self.version_id != version_id_for(self.payload, self.body):
            raise ValueError('Version identity must match its pinned source and extracted content.')
        if (self.name, self.description, self.examples) != (
            self.payload.name,
            self.payload.summary,
            self.payload.example_prompts,
        ):
            raise ValueError('Version search fields must match its payload.')
        if self.payload.fit is not None:
            raise ValueError('Search-specific fit cannot be published.')
        if (
            self.payload.profile.extractor_version != 'legacy'
            and self.payload.profile.source_revision != self.payload.source.revision
        ):
            raise ValueError('The profile must describe the pinned source revision.')
        return self


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[VersionInput] = Field(min_length=1, max_length=2000)
    complete_repositories: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def unique_sources(self):
        if len({row.skill_id for row in self.rows}) != len(self.rows):
            raise ValueError('Publish one version per canonical skill directory.')
        return self


def publish_rows(
    *, sources: Any, versions: Any, rows: list[VersionInput], complete_repositories: list[str]
) -> dict[str, int]:
    existing = {row['version_id'] for row in versions.select(versions.version_id).collect()}
    repeated = [row for row in rows if row.version_id in existing]
    if repeated:
        stored = {
            row['version_id']: row
            for row in versions.where(versions.version_id.isin([row.version_id for row in repeated]))
            .select(versions.version_id, versions.payload, versions.body)
            .collect()
        }
        for row in repeated:
            previous = stored[row.version_id]
            if canonical_version(Skill.model_validate(previous['payload']), previous['body']) != canonical_version(
                row.payload, row.body
            ):
                raise ValueError('An existing immutable version has different content; publication refused.')
    pending = [row.model_dump() for row in rows if row.version_id not in existing]
    for start in range(0, len(pending), 20):
        versions.insert(pending[start : start + 20])
    pointers = [
        {'skill_id': row.skill_id, 'published_version': row.version_id, 'checked_at': row.payload.source.checked_at}
        for row in rows
    ]
    if pointers:
        sources.batch_update(pointers, if_not_exists='insert')
    expected = {row.skill_id for row in rows}
    removed = [
        row['skill_id']
        for row in sources.select(sources.skill_id).collect()
        if row['skill_id'] not in expected
        and any(row['skill_id'].startswith(repo + '/') for repo in complete_repositories)
    ]
    if removed:
        sources.delete(where=sources.skill_id.isin(removed))
    return {'published': len(pointers), 'new_versions': len(pending), 'withdrawn': len(removed)}
