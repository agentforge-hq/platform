from copy import deepcopy

import pytest
from pydantic import ValidationError

from agentforge_backend.publish import PublishRequest, VersionInput, publish_rows, version_id_for
from tests.test_profiles import extract


def version(skill=None, body='A bounded source body.'):
    skill = skill or extract()
    return VersionInput(
        version_id=version_id_for(skill, body),
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.summary,
        body=body,
        examples=skill.example_prompts,
        payload=skill,
    )


def test_profile_extractor_changes_get_distinct_immutable_versions():
    skill = extract()
    original = version_id_for(skill, 'source')
    assert '#' in original
    skill.profile.extractor_version = 'sections-v2'
    assert version_id_for(skill, 'source') != original
    assert version_id_for(skill, 'changed source') != version_id_for(skill, 'source')


def test_checked_at_is_not_version_content():
    skill = extract()
    original = version_id_for(skill, 'source')
    skill.source.checked_at = '2026-10-28T00:00:00Z'
    for support in skill.harness_support:
        support.checked_at = '2026-10-28T00:00:00Z'
    assert version_id_for(skill, 'source') == original


@pytest.mark.parametrize(
    'field,value',
    [
        ('name', 'Different'),
        ('description', 'Different'),
        ('examples', ['Different']),
        ('body', 'Changed'),
        ('version_id', 'example/skills/skills/specialist@' + 'a' * 40),
    ],
)
def test_row_search_fields_and_version_must_match_payload(field, value):
    row = version().model_dump()
    row[field] = value
    with pytest.raises(ValidationError):
        VersionInput.model_validate(row)


def test_legacy_id_is_accepted_only_for_legacy_profile():
    skill = extract()
    skill.profile.extractor_version = 'legacy'
    row = version(skill)
    assert '#' not in row.version_id
    row.payload.profile.extractor_version = 'sections-v1'
    with pytest.raises(ValidationError):
        VersionInput.model_validate(row.model_dump())


def test_request_rejects_duplicate_canonical_directories():
    row = version()
    with pytest.raises(ValidationError):
        PublishRequest(rows=[row, row])


class Column:
    def __init__(self, name):
        self.name = name

    def isin(self, values):
        return self.name, values


class Table:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.inserted = []
        self.updated = []
        self.deleted = []

    def __getattr__(self, name):
        return Column(name)

    def select(self, *columns):
        return Table([{column.name: row[column.name] for column in columns} for row in self.rows])

    def where(self, condition):
        name, values = condition
        return Table([row for row in self.rows if row[name] in values])

    def collect(self):
        return self.rows

    def insert(self, rows):
        self.inserted.extend(rows)
        self.rows.extend(rows)

    def batch_update(self, rows, **kwargs):
        self.updated.extend(rows)

    def delete(self, where):
        self.deleted.extend(where[1])


def test_repeated_publish_does_not_mutate_versions():
    row = version()
    versions, sources = Table([row.model_dump()]), Table()
    row.payload.source.checked_at = '2026-10-28T00:00:00Z'
    result = publish_rows(sources=sources, versions=versions, rows=[row], complete_repositories=[])
    assert result['new_versions'] == 0 and versions.inserted == []
    assert sources.updated[0]['checked_at'] == row.payload.source.checked_at
    assert versions.rows[0]['payload']['source']['checked_at'] != row.payload.source.checked_at


def test_legacy_collision_refuses_before_any_pointer_or_version_write():
    skill = extract()
    skill.profile.extractor_version = 'legacy'
    row = version(skill)
    stored = deepcopy(row.model_dump())
    stored['body'] = 'Different previous body'
    sources, versions = Table(), Table([stored])
    with pytest.raises(ValueError, match='immutable version'):
        publish_rows(sources=sources, versions=versions, rows=[row], complete_repositories=[])
    assert not sources.updated and not versions.inserted


def test_only_confirmed_complete_repositories_can_withdraw_entries():
    row = version()
    sources = Table([{'skill_id': 'failed/repo/keep'}, {'skill_id': 'complete/repo/remove'}])
    result = publish_rows(sources=sources, versions=Table(), rows=[row], complete_repositories=['complete/repo'])
    assert result['withdrawn'] == 1 and sources.deleted == ['complete/repo/remove']
