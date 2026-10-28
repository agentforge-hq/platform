import json

import pytest

from ingest.catalog import parse_manifest


def extract(description='Use when writing a research report.', body='', metadata=''):
    raw = f'---\nname: specialist\ndescription: {description}\n{metadata}---\n{body}'.encode()
    return parse_manifest(
        raw=raw,
        repository='Example/Skills',
        revision='a' * 40,
        path='skills/specialist/SKILL.md',
        license_id='MIT',
        checked_at='2026-10-27T00:00:00Z',
    )[0]


def test_profile_uses_source_sections_and_keeps_author_metadata():
    skill = extract(
        body="""# Specialist
## Outputs
- A cited research report.
## When to use
- Compare competing explanations using published evidence.
## Do not use
- Unverified real-time market prices.
## Requirements
- Python 3.11 and pandoc.
- Set REPORT_API_KEY before fetching account data.
## Example prompts
- Help me compare the evidence for these two explanations.
""",
        metadata='custom-owner: analyst\nlast-updated: 2026-10-27\n',
    )
    assert skill.author_metadata['custom-owner'] == 'analyst'
    assert skill.author_metadata['last-updated'] == '2026-10-27'
    assert skill.profile.outputs == ['A cited research report.']
    assert 'Unverified real-time market prices.' in skill.profile.avoid_when
    assert skill.profile.tools == ['python', 'pandoc']
    assert 'REPORT_API_KEY' in skill.profile.credentials
    assert skill.example_prompts == ['Help me compare the evidence for these two explanations.']
    assert skill.profile.source_revision == skill.source.revision
    assert skill.profile.extractor_version != 'legacy'
    for item in skill.profile.evidence:
        assert item.quote and len(item.quote) <= 480 and item.source_url == skill.source.url
        assert item.location.startswith(('skills/specialist/SKILL.md:L', 'frontmatter.'))
    assert not any(item.status == 'tested' for item in skill.harness_support)


def test_negated_example_is_not_an_exclusion_and_code_is_not_a_task():
    skill = extract(
        body="""## Examples
- Write a do not use list for our style guide.
```python
create_secret_account()
```
## Procedure
Do not skip validation.
"""
    )
    assert skill.profile.avoid_when == []
    assert skill.exclusions == []
    assert skill.example_prompts == ['Write a do not use list for our style guide.']


def test_explicit_description_trigger_and_exclusion_are_separate():
    skill = extract(description='Use when writing detailed reports. Do NOT use for legal advice.')
    assert skill.profile.use_when == ['writing detailed reports']
    assert skill.profile.avoid_when == ['legal advice']
    assert skill.example_prompts == ['Help me with writing detailed reports.']
    assert any(item.field == 'example_prompts' and item.status == 'inferred' for item in skill.profile.evidence)


def test_missing_facts_are_unknown_and_allowed_tools_are_not_requirements():
    skill = extract(description='Review a proposed change.', metadata='allowed-tools: Read Bash\n')
    assert skill.profile.tools == [] and skill.profile.credentials == []
    assert skill.profile.outputs == []
    assert skill.harness_support[0].status == 'unknown'
    assert skill.author_metadata['allowed-tools'] == 'Read Bash'


def test_author_claim_of_tested_support_is_only_declared():
    skill = extract(metadata='compatibility: Tested with Codex. Not compatible with Cursor.\n')
    assert {item.harness: item.status for item in skill.harness_support} == {
        'codex': 'declared',
        'cursor': 'incompatible',
    }


def test_extraction_is_deterministic_and_bounded():
    body = '## Requirements\n' + '\n'.join(
        '- python npm git gh docker kubectl terraform az aws ffmpeg pandoc qpdf ' + str(i) for i in range(100)
    )
    first, second = extract(body=body), extract(body=body)
    assert first.model_dump() == second.model_dump()
    assert len(first.profile.evidence) <= 24
    assert any(item.field == 'tools' and 'python' in item.quote for item in first.profile.evidence)
    assert len(json.dumps(first.model_dump())) < 20000


@pytest.mark.parametrize(
    'metadata', ['recursive: &root [*root]\n', 'bad: !!set {a: null}\n', 'large: ' + 'x' * 17000 + '\n']
)
def test_unsupported_or_oversized_author_metadata_is_rejected(metadata):
    with pytest.raises(ValueError):
        extract(metadata=metadata)


def test_action_headings_produce_concrete_inferred_examples_and_outputs():
    skill = extract(
        description='If the user asks to produce one, use this skill.',
        body='## Merge PDFs\nRead the inputs.\n## Extract Metadata\nRead the properties.\n',
    )
    assert skill.example_prompts == ['Merge PDFs.', 'Extract Metadata.']
    assert skill.profile.outputs == ['PDFs', 'Metadata']
    assert all(
        item.status == 'inferred' for item in skill.profile.evidence if item.field in {'outputs', 'example_prompts'}
    )


def test_optional_or_negative_setup_statements_do_not_become_requirements():
    skill = extract(
        body='## Requirements\nPython is optional.\nNo dependencies are required.\n## Authentication\nNo credentials are required.\nREPORT_API_KEY must be configured.\n'
    )
    assert skill.profile.tools == [] and skill.requirements == []
    assert skill.profile.credentials == ['REPORT_API_KEY']
