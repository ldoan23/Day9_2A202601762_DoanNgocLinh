"""Coordinator Agent: runs the full pipeline for one case, orchestrating the
handoff between every other agent and merging their outputs into the final
case object.

Classification ground truth = Policy Agent (LLM), per team decision to keep
EC_POLICY_V2's judgment call (primary_issue, secondary_issues,
responsible_parties, refund, resolution_actions) out of hard-coded Python
if/elif. Only exact arithmetic (calculations.py) and structural array
limits/canonical ordering (evidence_builder.py) stay in code.
"""

from datetime import datetime, timezone

from src.agents import customer_agent, delivery_agent, order_product_agent, payment_agent, policy_agent
from src.calculations import compute_delivery_variance, compute_payment_reconciliation, compute_seller_handoff
from src.data_loader import get_case_data
from src.evidence_builder import (
    ACTION_ORDER,
    MAX_ACTIONS,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    SECONDARY_ISSUE_ORDER,
    build_affected_entities,
    build_customer_context,
    build_evidence_ids,
    build_product_context,
    canonicalize_order,
)
from src.llm_client import MODEL_NAME
from src.policy_engine import unique_categories, unique_seller_ids

PRIMARY_ISSUES = {
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
    "late_delivery_logistics", "valid_split_payment", "unsupported_late_claim",
}
ACTION_REQUIRED_ISSUES = {"canceled_order_paid", "unavailable_order_paid", "late_delivery_seller", "late_delivery_logistics"}


def _trace(case_id: str, agent: str, input_summary, output) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "agent": agent,
        "model": MODEL_NAME,
        "input_summary": input_summary,
        "output": output,
    }


def empty_case_result(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "case_assessment": {
            "primary_issue": "unsupported_late_claim",
            "secondary_issues": [],
            "case_status": "no_action",
            "confidence": 0.0,
        },
        "affected_entities": {"order_ids": [], "item_ids": [], "seller_ids": [], "payment_ids": []},
        "customer_context": {"customer_unique_id": None, "related_order_ids": []},
        "product_context": {"product_ids": [], "category_names": []},
        "delivery_analysis": {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
        },
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": 0.0,
            "freight_total_brl": 0.0,
            "expected_total_brl": None,
            "payment_total_brl": 0.0,
            "difference_brl": None,
            "reconciled": None,
            "payment_types": [],
        },
        "root_cause_analysis": {"ranked_causes": [], "responsible_parties": []},
        "evidence_ids": [],
        "financial_resolution": {"currency": "BRL", "recommended_refund_brl": 0.0},
        "resolution_actions": [],
    }


def run(case_input: dict) -> tuple[dict, list[dict]]:
    case_id = case_input["case_id"]
    claimed_order_id = case_input["customer_request"]["claimed_order_id"]
    trace: list[dict] = []

    data = get_case_data(claimed_order_id)
    trace.append(_trace(case_id, "data_loader", claimed_order_id, {
        "order_found": data["order"] is not None,
        "item_count": len(data["items"]),
        "payment_count": len(data["payments"]),
    }))

    order = data["order"]
    if order is None:
        trace.append(_trace(case_id, "coordinator", claimed_order_id, "order_not_found"))
        return empty_case_result(case_id), trace

    # --- Deterministic arithmetic (no LLM, formulas given verbatim by README) ---
    delivery_variance_hours = compute_delivery_variance(order)
    handoff_result = compute_seller_handoff(data["items"], order)
    payment_result = compute_payment_reconciliation(data["items"], data["payments"])
    seller_ids = unique_seller_ids(data["items"])
    category_names = unique_categories(data["products"])

    # --- Domain agents (handoff step, each calls the LLM) ---
    customer_finding = customer_agent.run(data["customer"], data["related_order_ids"])
    trace.append(_trace(case_id, "customer_agent", data["customer"], customer_finding))

    order_product_finding = order_product_agent.run(data["items"], data["sellers"], data["products"])
    trace.append(_trace(case_id, "order_product_agent", {"item_count": len(data["items"])}, order_product_finding))

    payment_finding = payment_agent.run(data["payments"], payment_result)
    trace.append(_trace(case_id, "payment_agent", payment_result, payment_finding))

    delivery_finding = delivery_agent.run(delivery_variance_hours, handoff_result)
    trace.append(_trace(case_id, "delivery_agent", {"delivery_variance_hours": delivery_variance_hours}, delivery_finding))

    # --- Policy Agent: the ONLY place primary_issue/refund/actions get decided ---
    decision = policy_agent.run(
        case_id,
        order.get("order_status"), payment_result, len(data["payments"]),
        delivery_variance_hours, handoff_result, len(data["items"]), seller_ids,
        len(data["related_order_ids"]), category_names,
    )
    trace.append(_trace(case_id, "policy_agent", "classification", decision))

    primary_issue = decision.get("primary_issue")
    if primary_issue not in PRIMARY_ISSUES:
        # LLM returned something outside the known taxonomy - fall back to
        # the safest no-action classification; Verifier will still flag
        # the case via root_cause_code below so it surfaces for review.
        primary_issue = "unsupported_late_claim"

    secondary_issues = canonicalize_order(
        [s for s in decision.get("secondary_issues", []) if s in SECONDARY_ISSUE_ORDER],
        SECONDARY_ISSUE_ORDER,
    )
    resolution_actions = canonicalize_order(
        decision.get("resolution_actions", []), ACTION_ORDER,
    )[:MAX_ACTIONS]
    responsible_parties = decision.get("responsible_parties", [])[:MAX_RESPONSIBLE_PARTIES]
    root_cause_code = decision.get("root_cause_code", "DELIVERY_WITHIN_ESTIMATE")

    case_status = "action_required" if primary_issue in ACTION_REQUIRED_ISSUES else "no_action"
    confidence = decision.get("confidence", 0.5)
    try:
        confidence = max(0.0, min(1.0, round(float(confidence), 2)))
    except (TypeError, ValueError):
        confidence = 0.5

    # --- Evidence & context builders (no LLM, data-grounded only) ---
    evidence_ids = build_evidence_ids(order, data["items"], data["payments"], responsible_parties, root_cause_code)
    affected_entities = build_affected_entities(order, data["items"], data["payments"], data["sellers"])
    customer_context = build_customer_context(data["customer"], data["related_order_ids"])
    product_context = build_product_context(data["products"])

    result = {
        "case_id": case_id,
        "case_assessment": {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": confidence,
        },
        "affected_entities": affected_entities,
        "customer_context": customer_context,
        "product_context": product_context,
        "delivery_analysis": {
            "delivered_at": order.get("order_delivered_customer_date"),
            "estimated_delivery_at": order.get("order_estimated_delivery_date"),
            "carrier_handoff_at": order.get("order_delivered_carrier_date"),
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": handoff_result["seller_handoff_analysis"],
            "late_handoff_seller_ids": handoff_result["late_handoff_seller_ids"],
        },
        "payment_reconciliation": {"currency": "BRL", **payment_result},
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": root_cause_code, "rank": 1}][:MAX_ROOT_CAUSES],
            "responsible_parties": responsible_parties,
        },
        "evidence_ids": evidence_ids,
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": round(float(decision.get("recommended_refund_brl") or 0.0), 2),
        },
        "resolution_actions": resolution_actions,
    }
    trace.append(_trace(case_id, "coordinator", "merge", {"primary_issue": result["case_assessment"]["primary_issue"]}))

    return result, trace
