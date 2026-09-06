"""CAUSED Decision chain and related Entities for retrieve evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.context_graph import node_properties, nodes_and_edges
from backend.retrieve.membership import application_id_of
from backend.retrieve.text import score_text

DECISION_CATEGORIES = ("risk_classification", "policy_check", "final_decision")
CAUSED_TYPE = "CAUSED"


def related_decisions(
    graph, application_ids: List[str], mapping: Dict[str, str] | None = None
) -> Dict[str, Any]:
    nodes, edges = nodes_and_edges(graph)
    wanted = set(application_ids)
    decisions = []
    for node in nodes:
        if str(node.get("type") or "") != "decision":
            continue
        app_id = application_id_of(node, mapping)
        if wanted and app_id not in wanted:
            continue
        meta = node_properties(node)
        decisions.append(
            {
                "id": node.get("id"),
                "category": meta.get("category"),
                "outcome": meta.get("outcome"),
                "scenario": node.get("content") or meta.get("scenario"),
                "reasoning": meta.get("reasoning"),
                "application_id": app_id,
            }
        )
    order = {category: index for index, category in enumerate(DECISION_CATEGORIES)}
    decisions.sort(key=lambda item: order.get(str(item.get("category") or ""), 9))
    caused = [
        {
            "from": edge.get("source") or edge.get("source_id"),
            "to": edge.get("target") or edge.get("target_id"),
        }
        for edge in edges
        if str(edge.get("type") or "") == CAUSED_TYPE
    ]
    decision_ids = {item["id"] for item in decisions}
    return {
        "decisions": decisions,
        "caused": [
            link
            for link in caused
            if link["from"] in decision_ids and link["to"] in decision_ids
        ],
    }


def related_entities(
    graph,
    application_ids: List[str],
    terms: List[str],
    limit: int = 12,
    mapping: Dict[str, str] | None = None,
) -> List[Dict[str, Any]]:
    nodes, _ = nodes_and_edges(graph)
    wanted = set(application_ids)
    scored = []
    for node in nodes:
        ntype = str(node.get("type") or "")
        if ntype in {"Document", "decision", "Application", "category", "decision_maker"}:
            continue
        app_id = application_id_of(node, mapping)
        if wanted and app_id not in wanted:
            continue
        text = str(node.get("content") or node.get("id") or "")
        display = text.split("::", 1)[-1] if "::" in text else text
        score = score_text(display, terms)
        if score <= 0 and not wanted:
            continue
        scored.append(
            {
                "id": node.get("id"),
                "type": ntype,
                "text": display,
                "score": score,
                "application_id": app_id,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
