from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentforge_backend.models import Skill


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
        if self.skill_id != self.payload.skill_id or self.version_id != self.skill_id + '@' + self.payload.source.revision:
            raise ValueError('Version identity must match its pinned source.')
        return self


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[VersionInput] = Field(min_length=1, max_length=500)
    complete_repositories: list[str] = Field(default_factory=list, max_length=10)


def publish_rows(*, sources: Any, versions: Any, rows: list[VersionInput], complete_repositories: list[str]) -> dict[str, int]:
    existing = {row['version_id'] for row in versions.select(versions.version_id).collect()}
    pending = [row.model_dump() for row in rows if row.version_id not in existing]
    for start in range(0, len(pending), 20):
        versions.insert(pending[start:start + 20])
    pointers = [{'skill_id': row.skill_id, 'published_version': row.version_id, 'checked_at': row.payload.source.checked_at} for row in rows]
    sources.batch_update(pointers, if_not_exists='insert')
    expected = {row.skill_id for row in rows}
    removed = [row['skill_id'] for row in sources.select(sources.skill_id).collect() if row['skill_id'] not in expected and any(row['skill_id'].startswith(repo + '/') for repo in complete_repositories)]
    if removed:
        sources.delete(where=sources.skill_id.isin(removed))
    return {'published': len(pointers), 'new_versions': len(pending), 'withdrawn': len(removed)}
