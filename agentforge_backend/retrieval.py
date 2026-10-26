from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from agentforge_backend.models import Skill

STOP = frozenset('a an the to for of and or i me my we our you your help please want need can could would with this that it is'.split())


def terms(query: str) -> list[str]:
    return list(dict.fromkeys(t for t in re.findall(r'[\w]+', query.casefold()) if len(t) > 1 and t not in STOP))[:12]


def lexical_score(skill: Skill, query_terms: list[str]) -> float:
    name = set(re.findall(r'[\w]+', skill.name.casefold()))
    summary = set(re.findall(r'[\w]+', skill.summary.casefold()))
    examples = set(re.findall(r'[\w]+', ' '.join(skill.example_prompts + skill.capabilities).casefold()))
    return sum((4 if t in name else 0) + (2 if t in summary else 0) + (1 if t in examples else 0) for t in query_terms)


def fuse(*, lexical: Sequence[tuple[Skill, float]], semantic: Sequence[tuple[Skill, float]], limit: int) -> list[Skill]:
    scores: dict[str, float] = {}
    skills: dict[str, Skill] = {}
    for candidates in (lexical, semantic):
        seen: set[str] = set()
        for rank, (skill, _) in enumerate(candidates, start=1):
            if skill.skill_id in seen:
                continue
            seen.add(skill.skill_id)
            skills[skill.skill_id] = skill
            scores[skill.skill_id] = scores.get(skill.skill_id, 0) + 1 / (60 + rank)
    return [skills[key] for key in sorted(scores, key=lambda key: (-scores[key], key))[:limit]]


def catalog_revision(rows: Sequence[Skill]) -> str:
    return hashlib.sha256('\n'.join(sorted(s.skill_id + '@' + s.source.revision for s in rows)).encode()).hexdigest()[:16]
