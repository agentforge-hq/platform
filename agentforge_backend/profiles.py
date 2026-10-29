"""Deterministic, bounded extraction. Source content is data, never instructions."""

from __future__ import annotations

import re
from typing import Any

from agentforge_backend.models import CapabilityProfile, FieldEvidence, HarnessSupport

EXTRACTOR_VERSION = 'sections-v2'
SECTION_FIELDS = {
    'avoid_when': ('when not to use', 'do not use', 'dont use', 'exclusions', 'out of scope', 'not suitable'),
    'use_when': ('when to use', 'use when', 'use cases', 'usage scenarios', 'triggers', 'activation'),
    'outputs': ('outputs', 'output', 'deliverables', 'what you get'),
    'requirements': ('prerequisites', 'requirements', 'dependencies', 'environment', 'setup'),
    'tools': ('required tools', 'tools required', 'tool requirements'),
    'credentials': ('credentials', 'authentication', 'api keys'),
    'examples': ('example prompts', 'sample prompts', 'usage examples', 'examples'),
    'support': ('compatibility', 'supported agents', 'supported harnesses'),
}
HARNESS_NAMES = {
    'codex': ('codex',),
    'claude-code': ('claude code', 'claude-code'),
    'cursor': ('cursor',),
    'gemini': ('gemini',),
    'opencode': ('opencode',),
    'devin': ('devin',),
}
TOOL_NAMES = (
    'python',
    'node',
    'npm',
    'npx',
    'uv',
    'pip',
    'git',
    'gh',
    'docker',
    'kubectl',
    'terraform',
    'az',
    'aws',
    'ffmpeg',
    'pandoc',
    'qpdf',
    'pdftotext',
    'playwright',
    'semgrep',
    'slither',
    'forge',
    'solc',
    'cargo',
    'go',
    'bun',
    'pnpm',
    'yarn',
)


def clean(value: str, limit: int = 360) -> str:
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
    return re.sub(r'\s+', ' ', value.strip().lstrip('-*+> ')).strip('`"')[:limit]


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [clean(value)] if value.strip() else []
    if isinstance(value, list):
        return [clean(item) for item in value if isinstance(item, str) and item.strip()][:12]
    return []


def section_lines(body: str, *, path: str, line_offset: int) -> list[tuple[str, str, str]]:
    """Classify only explicit sections, respecting nested headings and code fences."""
    result = []
    headings: list[tuple[int, str | None]] = []
    fence: str | None = None
    for number, line in enumerate(body.splitlines(), line_offset + 1):
        if re.match(r'^\s*(`{3,}|~{3,})', line):
            marker = line.strip()[0]
            fence = None if fence == marker else marker
            continue
        if fence:
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading:
            level = len(heading[1])
            label = re.sub(r'[^a-z0-9 ]', '', heading[2].casefold()).strip()
            field = next(
                (
                    field
                    for field, labels in SECTION_FIELDS.items()
                    if any(label == name or label.startswith(name + ' ') for name in labels)
                ),
                None,
            )
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, field))
            title = clean(heading[2])
            if re.match(
                r'(?i)^(?:create|generate|build|write|export|merge|split|extract|convert|analyze|analyse|review|debug|test|plan|design)\s+\S',
                title,
            ) and not re.search(
                r'(?i)\b(?:principles|patterns|guidelines|overview|configuration|failures|strategy|reference|options)$',
                title,
            ):
                result.append(('task_heading', title, f'{path}:L{number}'))
            continue
        field = next((field for _, field in reversed(headings) if field), None)
        value = clean(line)
        if field and value and not value.startswith('|') and not re.fullmatch(r'[-=: ]+', value):
            result.append((field, value, f'{path}:L{number}'))
    return result


def extract_profile(
    *, metadata: dict, body: str, revision: str, source_url: str, path: str, line_offset: int = 0
) -> tuple[CapabilityProfile, list[str], list[str], list[HarnessSupport]]:
    values: dict[str, list[str]] = {
        field: [] for field in ('outputs', 'use_when', 'avoid_when', 'tools', 'credentials', 'requirements', 'examples')
    }
    evidence: list[FieldEvidence] = []

    def add(field: str, value: str, quote: str, location: str, status: str = 'declared') -> None:
        value = clean(value)
        limit = 6 if field == 'tools' else 3
        if (
            not value
            or value in values[field]
            or len(evidence) >= (24 if field == 'examples' else 22)
            or len(values[field]) >= limit
        ):
            return
        values[field].append(value)
        evidence.append(
            FieldEvidence(
                field='example_prompts' if field == 'examples' else field,
                quote=quote[:480],
                location=location[:240],
                source_url=source_url,
                status=status,
            )
        )

    declared = {
        'use_when': ('use_when', 'use-when'),
        'outputs': ('outputs', 'deliverables'),
        'avoid_when': ('avoid_when', 'avoid-when', 'exclusions'),
        'tools': ('required-tools', 'tools'),
        'credentials': ('credentials',),
        'requirements': ('requirements', 'compatibility'),
        'examples': ('example_prompts', 'examples'),
    }
    description = str(metadata['description']).strip()
    if not any(strings(metadata.get(key)) for key in declared['use_when']):
        candidates = re.split(r'(?<=[.!?])\s+', description)
        first = next(
            (
                part
                for part in candidates
                if re.match(
                    r'(?i)^(?:Use (?:this skill )?(?:when|whenever|for)|Create|Write|Build|Generate|Review|Test|Analyze|Rewrite)\b',
                    part,
                )
            ),
            candidates[0],
        )
        trigger = re.match(r'(?i)^Use (?:this skill )?(?:when|whenever|for)\s+(.+)', first)
        add(
            'use_when',
            trigger[1].rstrip('.!?') if trigger else first,
            first,
            'frontmatter.description',
            'declared' if trigger else 'inferred',
        )
    for field, keys in declared.items():
        for key in keys:
            for value in strings(metadata.get(key))[:3]:
                if field == 'tools':
                    for tool in re.split(r'[,\s]+', value):
                        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}', tool):
                            add(field, tool, value, f'frontmatter.{key}')
                else:
                    add(field, value, value, f'frontmatter.{key}')
    # Negation is recognized only in an explicit author trigger clause. Example text
    # such as "write a do-not-use list" never becomes an exclusion.
    for match in re.finditer(
        r'(?:^|(?<=[.!?])\s+)(Use (?:this skill )?when|Do not use (?:this skill )?(?:when|for)|Don\x27t use (?:this skill )?(?:when|for))\s+([^.!?]+)',
        description,
        re.I,
    ):
        field = 'use_when' if match[1].casefold().startswith('use ') else 'avoid_when'
        add(field, match[2], match[0].strip(), 'frontmatter.description')
    if not values['use_when']:
        first = re.split(r'(?<=[.!?])\s+', description)[0]
        add('use_when', first, first, 'frontmatter.description', 'inferred')

    sections = section_lines(body, path=path, line_offset=line_offset)
    support_clauses = [(value, location) for field, value, location in sections if field == 'support']
    if isinstance(metadata.get('compatibility'), str):
        support_clauses.append((metadata['compatibility'], 'frontmatter.compatibility'))
    for field, value, location in sections:
        optional = bool(
            re.search(
                r'(?i)\b(?:not required|optional|no (?:credentials|dependencies|prerequisites|accounts?|authentication|api keys?))\b',
                value,
            )
        )
        if (
            field in {'use_when', 'avoid_when', 'outputs', 'requirements'}
            and len(values[field]) < 3
            and not (field == 'requirements' and optional)
        ):
            add(field, value, value, location)
        if (
            field == 'examples'
            and re.search(
                r'(?i)\b(help me|i (?:want|need)|create|write|build|review|analyze|analyse|find|extract|turn|make|generate|check|convert|debug|test)\b',
                value,
            )
            and len(values['examples']) < 3
        ):
            add('examples', value, value, location)
        if field in {'tools', 'requirements'} and not optional:
            for tool in TOOL_NAMES:
                if re.search(r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])', value, re.I):
                    add('tools', tool, value, location)
        if field in {'credentials', 'requirements'} and not optional:
            credentials = re.findall(r'\b(?:[A-Z][A-Z0-9_]*_)?(?:API_KEY|ACCESS_KEY|TOKEN|SECRET|CREDENTIALS)\b', value)
            for credential in credentials:
                add('credentials', credential, value, location)
            if not credentials and re.search(
                r'(?i)\b(?:api[ -]?key|access token|credentials?|account|sign[ -]?in|log[ -]?in|authenticated)\b', value
            ):
                add('credentials', value, value, location)
    if not values['outputs']:
        for match in re.finditer(
            r'\b(?:create|produce|generate|deliver|export|write|build)s?\s+([^.!?;\n]{4,180})', description, re.I
        ):
            if re.match(r'(?i)^(?:one|it|this|them|use)\b', match[1]):
                continue
            add('outputs', match[1], match[0], 'frontmatter.description', 'inferred')
            if len(values['outputs']) == 3:
                break
    action_headings = [(value, location) for field, value, location in sections if field == 'task_heading']
    if not values['outputs']:
        for value, location in action_headings:
            match = re.match(r'(?i)^(create|generate|build|write|export|merge|split|extract)\s+(.+)', value)
            if match and re.search(
                r'(?i)\b(documents?|reports?|pdfs?|spreadsheets?|charts?|code|apps?|scripts?|tests?|plans?|images?|slides?|metadata|tables?|schemas?|summaries|queries)\b',
                match[2],
            ):
                add('outputs', match[2], value, location, 'inferred')
    if not values['examples']:
        candidates = action_headings[:2] or [(value, '') for value in values['use_when'] if not value.endswith(':')][:2]
        for value, location in candidates:
            task = re.sub(
                r'(?i)^(?:use (?:this skill )?(?:when|whenever|for)|this skill (?:helps|is for)|when|guidance for)\s+',
                '',
                value,
            ).rstrip('.')
            task = re.sub(r'(?i)^(?:the )?user (?:wants|needs) to\s+', '', task)
            task = re.sub(r'(?i)^you (?:want|need) to\s+', '', task)
            task = re.sub(r'(?i)^you (?:must|should) use this before\s+', 'plan ', task)
            if re.match(
                r'(?i)^(?:create|write|build|generate|review|test|analyze|analyse|rewrite|make|extract|merge|split|convert|debug|plan|design|export)\b',
                task,
            ):
                prompt = task[0].upper() + task[1:] + '.'
            else:
                prompt = 'Help me with ' + task[0].lower() + task[1:] + '.'
            origin = next(item for item in evidence if item.field == 'use_when' and item.quote)
            add('examples', prompt, value if location else origin.quote, location or origin.location, 'inferred')

    support = []
    for harness, names in HARNESS_NAMES.items():
        clauses = [
            (value, location)
            for value, location in support_clauses
            if any(re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', value, re.I) for name in names)
        ]
        if clauses:
            all_names = '|'.join(re.escape(name) for aliases in HARNESS_NAMES.values() for name in aliases)
            negative_pattern = (
                r'(?:not compatible with|does not support|unsupported on)\s+('
                + r'(?:'
                + all_names
                + r')(?:\s*(?:,|and|or|/|&)\s*(?:'
                + all_names
                + r'))*)'
            )
            negative = next(
                (
                    value
                    for value, _ in clauses
                    if any(
                        any(re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', match[1], re.I) for name in names)
                        for match in re.finditer(negative_pattern, value, re.I)
                    )
                ),
                None,
            )
            value = negative or clauses[0][0]
            support.append(
                HarnessSupport(
                    harness=harness,
                    status='incompatible' if negative else 'declared',
                    detail=clean(value, 480),
                    evidence_url=source_url,
                )
            )
    if not support:
        support.append(
            HarnessSupport(
                harness='portable',
                status='unknown',
                detail='Harness support is not established by the extracted source declarations.',
                evidence_url=source_url,
            )
        )
    profile = CapabilityProfile(
        extractor_version=EXTRACTOR_VERSION,
        source_revision=revision,
        evidence=evidence,
        **{key: values[key] for key in ('outputs', 'use_when', 'avoid_when', 'tools', 'credentials')},
    )
    return profile, values['examples'], values['requirements'], support
