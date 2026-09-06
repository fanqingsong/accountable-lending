"""HighRiskFlag / ThinCreditHistory / RequiresManualReview on the Application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.application.ids import application_node_id
from backend.context_graph import node_properties, nodes_and_edges

POLICY_FACTS_FILENAME = "policy_facts.json"
HIGH_RISK_FLAG = "HighRiskFlag"
THIN_CREDIT_HISTORY = "ThinCreditHistory"
REQUIRES_MANUAL_REVIEW = "RequiresManualReview"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_policy_facts(raw: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
    raw = raw or {}
    return {
        HIGH_RISK_FLAG: _as_bool(raw.get(HIGH_RISK_FLAG, raw.get("high_risk"))),
        THIN_CREDIT_HISTORY: _as_bool(raw.get(THIN_CREDIT_HISTORY, raw.get("thin_credit"))),
    }


def load_policy_facts(paths: List[Path]) -> Dict[str, bool]:
    seen: List[Path] = []
    for path in paths:
        candidate = path.parent / POLICY_FACTS_FILENAME
        if candidate in seen:
            continue
        seen.append(candidate)
        if candidate.is_file():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return normalize_policy_facts(payload)
    return normalize_policy_facts()


def _node_bag(node: Dict[str, Any]) -> Dict[str, Any]:
    bag = node_properties(node)
    for key in (HIGH_RISK_FLAG, THIN_CREDIT_HISTORY, REQUIRES_MANUAL_REVIEW, "application_id"):
        if key in node and key not in bag:
            bag[key] = node[key]
    return bag


def get_application(graph, application_id: str) -> Optional[Dict[str, Any]]:
    target = application_node_id(application_id)
    finder = getattr(graph, "find_node", None)
    if callable(finder):
        found = finder(target)
        if isinstance(found, dict):
            return found
    for node in nodes_and_edges(graph)[0]:
        if node.get("id") == target:
            return node
    return None


def policy_facts_from_graph(graph, application_id: str) -> Dict[str, bool]:
    bag = _node_bag(get_application(graph, application_id) or {})
    return {
        HIGH_RISK_FLAG: _as_bool(bag.get(HIGH_RISK_FLAG)),
        THIN_CREDIT_HISTORY: _as_bool(bag.get(THIN_CREDIT_HISTORY)),
        REQUIRES_MANUAL_REVIEW: _as_bool(bag.get(REQUIRES_MANUAL_REVIEW)),
    }


def stamp_application_facts(graph, application_id: str, **facts: Any) -> None:
    """Write policy facts onto the Application node already in the graph."""
    app_id = application_node_id(application_id)
    existing = get_application(graph, application_id) or {}
    bag = _node_bag(existing)
    bag.update(facts)
    bag["application_id"] = bag.get("application_id") or application_id
    content = existing.get("content") or application_id
    if callable(getattr(graph, "find_node", None)) and callable(getattr(graph, "add_node", None)):
        graph.add_node(app_id, "Application", content=content, **bag)
        return
    node = None
    for item in nodes_and_edges(graph)[0]:
        if item.get("id") == app_id:
            node = item
            break
    if node is None:
        return
    for key in ("metadata", "properties"):
        extra = node.get(key)
        if isinstance(extra, dict):
            extra.update(facts)
    node.update(facts)
