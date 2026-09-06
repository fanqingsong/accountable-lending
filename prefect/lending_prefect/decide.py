"""Record the three-Decision CAUSED chain. Policy facts still live on the Application."""

from __future__ import annotations

from typing import Dict, List

from backend.application import (
    HIGH_RISK_FLAG,
    REQUIRES_MANUAL_REVIEW,
    THIN_CREDIT_HISTORY,
    attach_decision_chain,
    policy_facts_from_graph,
    stamp_application_facts,
)


def record_decision_chain(
    graph,
    application_id: str,
    applicant: str,
    entity_ids: List[str] | None = None,
) -> Dict[str, str]:
    """Record the three Decisions from Application facts already on the graph."""
    if entity_ids is None:
        entity_ids = [
            node.get("id")
            for node in (graph.to_dict() or {}).get("nodes") or []
            if node.get("id") and node.get("type") not in {"Application", "Document", "Decision"}
        ][:6]

    facts = policy_facts_from_graph(graph, application_id)
    requires_manual = facts[HIGH_RISK_FLAG] and facts[THIN_CREDIT_HISTORY]
    stamp_application_facts(
        graph, application_id, **{REQUIRES_MANUAL_REVIEW: requires_manual}
    )
    if facts[HIGH_RISK_FLAG]:
        risk_outcome = "high_risk"
        risk_reason = (
            "Revenue concentration or missing repayment history flags this "
            f"applicant ({applicant}) as high risk."
        )
    else:
        risk_outcome = "standard_risk"
        risk_reason = f"No high-risk flags were raised for {applicant}."

    if requires_manual:
        policy_outcome = "manual_review_required"
        policy_reason = (
            "Policy 7.3 requires manual review when revenue concentration "
            "exceeds 35% or when no external repayment record exists."
        )
        final_outcome = "referred_to_manual_review"
        final_reason = (
            "Automated approval is not permitted under Policy 7.3; the "
            "application is routed to the manual review queue."
        )
    else:
        policy_outcome = "policy_cleared"
        policy_reason = (
            "Policy 7.3 does not require manual review for this profile."
        )
        final_outcome = "approved"
        final_reason = (
            f"Automated approval is permitted for {applicant} under Policy 7.3."
        )

    decisions: Dict[str, str] = {}
    decisions["risk_classification"] = graph.record_decision(
        category="risk_classification",
        scenario=f"Loan application for {applicant}",
        reasoning=risk_reason,
        outcome=risk_outcome,
        confidence=0.87,
        entities=entity_ids,
        decision_maker="underwriting_agent",
    )
    decisions["policy_check"] = graph.record_decision(
        category="policy_check",
        scenario="Internal lending policy for first-time borrowers",
        reasoning=policy_reason,
        outcome=policy_outcome,
        confidence=0.95,
        entities=entity_ids,
        decision_maker="policy_engine",
    )
    decisions["final_decision"] = graph.record_decision(
        category="final_decision",
        scenario=f"Loan outcome for {applicant}",
        reasoning=final_reason,
        outcome=final_outcome,
        confidence=0.93,
        entities=entity_ids,
        decision_maker="underwriting_agent",
    )
    graph.add_edge(
        decisions["risk_classification"], decisions["policy_check"], "CAUSED"
    )
    graph.add_edge(
        decisions["policy_check"], decisions["final_decision"], "CAUSED"
    )
    attach_decision_chain(graph, application_id, decisions)
    return decisions
