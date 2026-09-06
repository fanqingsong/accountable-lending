"""Query expansion. Aliases are query language only — not Application ids."""

from __future__ import annotations

import re
from typing import List

QUERY_ALIASES = {
    "转人工": "manual review referred_to_manual_review Policy 7.3 concentration 38%",
    "人工": "manual review referred",
    "为什么": "why outcome reasoning risk",
    "高风险": "high risk concentration 38%",
}


def expand_query(query: str) -> str:
    extra = []
    lowered = query.lower()
    for needle, expansion in QUERY_ALIASES.items():
        if needle.lower() in lowered:
            extra.append(expansion)
    return " ".join([query] + extra).strip()


def query_terms(query: str) -> List[str]:
    expanded = expand_query(query)
    terms: List[str] = []
    for part in re.split(r"\s+", expanded.lower()):
        if len(part) > 1 and part not in terms:
            terms.append(part)
        for sub in re.split(r"[-_]+", part):
            if len(sub) > 1 and sub not in terms:
                terms.append(sub)
    return terms
