from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Sequence

from agentforge_backend.models import FieldEvidence, RecommendationFit, SearchRequest, Skill

STOP = frozenset(
    'a an the to for of and or i me my we our you your help helps helpful please want need can could would with this that it is do how what get make use using some about have has be been am are as at by on in from into thanks thank hello hi okay ok yes no great cool perfect nice done continue ahead sure yep understood got awesome'.split()
)
GENERIC = frozenset('task work skill agent tool useful better improve create build find write review check'.split())
SEMANTIC_FLOOR = 0.62
RANKING_VERSION = 'profile-hybrid-v2'


def terms(query: str, *, limit: int | None = 32) -> list[str]:
    tokens = list(dict.fromkeys(t for t in re.findall(r'[\w]+', query.casefold()) if len(t) > 1 and t not in STOP))
    return tokens[:limit] if limit is not None else tokens


def field_text(skill: Skill) -> dict[str, str]:
    return {
        'name': skill.name.replace('-', ' ').replace('_', ' '),
        'summary': skill.summary,
        'capabilities': ' '.join(skill.capabilities),
        'use_when': ' '.join(skill.profile.use_when),
        'outputs': ' '.join(skill.profile.outputs),
        'example_prompts': ' '.join(skill.example_prompts),
    }


def lexical_score(skill: Skill, query_terms: list[str]) -> float:
    weights = {'name': 4, 'summary': 2, 'capabilities': 2, 'use_when': 2, 'outputs': 2, 'example_prompts': 1}
    fields = field_text(skill)
    return sum(weights[field] * len(set(query_terms) & set(terms(text, limit=None))) for field, text in fields.items())


def normalized_tool(tool: str) -> str:
    tool = tool.casefold()
    if re.fullmatch(r'python(?:3(?:\.\d+)?)?', tool):
        return 'python'
    return {'nodejs': 'node'}.get(tool, tool)


def compatibility_for(skill: Skill, harness: str | None) -> dict[str, str]:
    if not harness:
        return dict(skill.compatibility)
    entries = [entry for entry in skill.harness_support if entry.harness == harness]
    if entries:
        entry = next((entry for entry in entries if entry.status == 'incompatible'), entries[0])
        return {'harness': harness, 'status': entry.status}
    if skill.compatibility.get('harness') == harness:
        return dict(skill.compatibility)
    return {'harness': harness, 'status': 'unknown'}


def missing_tools(skill: Skill, request: SearchRequest) -> list[str]:
    if not request.constraints or request.constraints.available_tools is None:
        return []
    available = {normalized_tool(tool) for tool in request.constraints.available_tools}
    return sorted(tool for tool in skill.profile.tools if normalized_tool(tool) not in available)


def eligible(skill: Skill, request: SearchRequest) -> bool:
    if (
        skill.adoption_status == 'unavailable'
        or compatibility_for(skill, request.harness).get('status') == 'incompatible'
    ):
        return False
    constraints = request.constraints
    if constraints and not constraints.allow_credentials and skill.profile.credentials:
        return False
    if constraints and not constraints.allow_setup and missing_tools(skill, request):
        return False
    return True


def lexical_candidates(rows: Sequence[Skill], query: str) -> list[tuple[Skill, float]]:
    query_terms = terms(query)
    if not query_terms:
        return []
    frequency = Counter(term for skill in rows for term in set(terms(' '.join(field_text(skill).values()), limit=None)))
    result = []
    for skill in rows:
        fields = field_text(skill)
        document_terms = set(terms(' '.join(fields.values()), limit=None))
        hits = set(query_terms) & document_terms
        specific_hits = hits - GENERIC
        exact_name = (
            skill.name.casefold() == query.strip().casefold() or fields['name'].casefold() == query.strip().casefold()
        )
        # One generic overlap cannot establish suitability in keyword-only operation.
        needed = min(2, len(set(query_terms) - GENERIC))
        if not exact_name and (not specific_hits or len(specific_hits) < max(1, needed)):
            continue
        weighted = lexical_score(skill, query_terms)
        weighted += sum(math.log(1 + len(rows) / (1 + frequency[t])) for t in specific_hits)
        result.append((skill, weighted))
    return sorted(result, key=lambda item: (-item[1], item[0].skill_id))[:50]


def fuse(*, lexical: Sequence[tuple[Skill, float]], semantic: Sequence[tuple[Skill, float]], limit: int) -> list[Skill]:
    scores: dict[str, float] = {}
    skills: dict[str, Skill] = {}
    for candidates, weight in ((lexical, 0.1), (semantic, 1.0)):
        seen: set[str] = set()
        for rank, (skill, _) in enumerate(candidates, start=1):
            if skill.skill_id in seen:
                continue
            seen.add(skill.skill_id)
            skills[skill.skill_id] = skill
            scores[skill.skill_id] = scores.get(skill.skill_id, 0) + weight / (60 + rank)
    return [skills[key] for key in sorted(scores, key=lambda key: (-scores[key], key))[:limit]]


def explain_fit(skill: Skill, request: SearchRequest) -> Skill:
    query_terms = set(terms(request.query))
    evidence = [
        item
        for item in skill.profile.evidence
        if item.field in {'capabilities', 'use_when', 'outputs', 'example_prompts', 'summary', 'description'}
    ]
    evidence.sort(key=lambda item: (-len(query_terms & set(terms(item.quote))), item.field, item.location))
    if not evidence:
        evidence = [
            FieldEvidence(
                field='summary',
                quote=skill.summary[:480],
                location='frontmatter.description',
                source_url=skill.source.url,
            )
        ]
    chosen = evidence[:2]
    reason = 'Purpose from the pinned source: ' + chosen[0].quote[:400]
    notes = []
    support = compatibility_for(skill, request.harness)
    if support.get('status') == 'unknown':
        notes.append('Harness support has not been established for this selection.')
    if not skill.requirements:
        notes.append('Additional requirements have not been established; inspect the package.')
    if skill.adoption_status == 'metadata_only':
        notes.append('Licensing is unresolved; this listing is for discovery, not automatic adoption.')
    missing = missing_tools(skill, request)
    if missing:
        notes.append('Additional setup is needed for the listed tools.')
    return skill.model_copy(
        update={
            'compatibility': support,
            'fit': RecommendationFit(reason=reason, evidence=chosen, missing_tools=missing, notes=notes),
        }
    )


def catalog_revision(rows: Sequence[Skill]) -> str:
    stable = []
    for skill in sorted(rows, key=lambda value: value.skill_id):
        payload = skill.model_dump(exclude={'fit'})
        payload['source'].pop('checked_at', None)
        for support in payload['harness_support']:
            support.pop('checked_at', None)
        stable.append(payload)
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    ).hexdigest()[:16]
