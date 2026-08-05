"""Verifier Agent: final gate before writing a case to output/. Checks
schema validity, array limits and that every evidence ID is actually
derivable from the joined data (no hallucinated evidence). Deliberately
pure code, not an LLM call, because this step must be exact."""

import re

from src.evidence_builder import (
    ACTION_ORDER,
    MAX_ACTIONS,
    MAX_CATEGORIES,
    MAX_EVIDENCE,
    MAX_ITEM_IDS,
    MAX_ORDER_IDS,
    MAX_PAYMENT_IDS,
    MAX_PRODUCT_IDS,
    MAX_RELATED_ORDER_IDS,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    MAX_SELLER_IDS,
    SECONDARY_ISSUE_ORDER,
)

_EVIDENCE_PATTERN = re.compile(
    r"^(order:[^:]+|item:[^:]+:[^:]+|payment:[^:]+:[^:]+|seller:[^:]+|policy:[A-Z_]+)$"
)

VALID_PRIMARY_ISSUES = {
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
    "late_delivery_logistics", "valid_split_payment", "unsupported_late_claim",
}
VALID_ROOT_CAUSE_CODES = {
    "SELLER_HANDOFF_AFTER_LIMIT", "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT", "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED", "DELIVERY_WITHIN_ESTIMATE",
}


def verify(case_result: dict, data: dict) -> list[str]:
    """Return a list of problem descriptions; empty list means the case is
    clean and safe to write to output/."""
    problems = []

    assessment = case_result["case_assessment"]
    if not (0 <= assessment["confidence"] <= 1):
        problems.append(f"confidence out of range: {assessment['confidence']}")
    if assessment["case_status"] not in ("action_required", "no_action"):
        problems.append(f"invalid case_status: {assessment['case_status']}")
    if assessment["primary_issue"] not in VALID_PRIMARY_ISSUES:
        problems.append(f"primary_issue outside taxonomy: {assessment['primary_issue']}")
    for cause in case_result["root_cause_analysis"]["ranked_causes"]:
        if cause["cause_code"] not in VALID_ROOT_CAUSE_CODES:
            problems.append(f"root cause outside taxonomy: {cause['cause_code']}")

    entities = case_result["affected_entities"]
    if len(entities["order_ids"]) > MAX_ORDER_IDS:
        problems.append("order_ids exceeds limit")
    if len(entities["item_ids"]) > MAX_ITEM_IDS:
        problems.append("item_ids exceeds limit")
    if len(entities["seller_ids"]) > MAX_SELLER_IDS:
        problems.append("seller_ids exceeds limit")
    if len(entities["payment_ids"]) > MAX_PAYMENT_IDS:
        problems.append("payment_ids exceeds limit")

    if len(case_result["customer_context"]["related_order_ids"]) > MAX_RELATED_ORDER_IDS:
        problems.append("related_order_ids exceeds limit")

    product_ctx = case_result["product_context"]
    if len(product_ctx["product_ids"]) > MAX_PRODUCT_IDS:
        problems.append("product_ids exceeds limit")
    if len(product_ctx["category_names"]) > MAX_CATEGORIES:
        problems.append("category_names exceeds limit")

    root_cause = case_result["root_cause_analysis"]
    if len(root_cause["ranked_causes"]) > MAX_ROOT_CAUSES:
        problems.append("ranked_causes exceeds limit")
    if len(root_cause["responsible_parties"]) > MAX_RESPONSIBLE_PARTIES:
        problems.append("responsible_parties exceeds limit")

    if len(case_result["resolution_actions"]) > MAX_ACTIONS:
        problems.append("resolution_actions exceeds limit")
    for action in case_result["resolution_actions"]:
        if action not in ACTION_ORDER:
            problems.append(f"resolution_action outside taxonomy: {action}")
    for issue in assessment["secondary_issues"]:
        if issue not in SECONDARY_ISSUE_ORDER:
            problems.append(f"secondary_issue outside taxonomy: {issue}")

    # Sanity check (not a classification decision - just catches a refund
    # number that isn't grounded in any real computed total): the refund
    # must equal one of the actual candidate amounts for this case.
    refund = case_result["financial_resolution"]["recommended_refund_brl"]
    pay = case_result["payment_reconciliation"]
    plausible_refunds = {0.0, pay["freight_total_brl"], pay["payment_total_brl"]}
    if not any(abs(refund - p) <= 0.01 for p in plausible_refunds):
        problems.append(f"recommended_refund_brl not grounded in real totals: {refund}")

    evidence_ids = case_result["evidence_ids"]
    if len(evidence_ids) > MAX_EVIDENCE:
        problems.append("evidence_ids exceeds limit")

    valid_order_ids = {data["order"]["order_id"]} if data["order"] else set()
    valid_item_ids = {f"{i['order_id']}:{i['order_item_id']}" for i in data["items"]}
    valid_payment_ids = {f"{p['order_id']}:{p['payment_sequential']}" for p in data["payments"]}
    valid_seller_ids = {s["seller_id"] for s in data["sellers"]}

    for evidence_id in evidence_ids:
        if not _EVIDENCE_PATTERN.match(evidence_id):
            problems.append(f"malformed evidence id: {evidence_id}")
            continue
        kind, _, rest = evidence_id.partition(":")
        if kind == "order" and rest not in valid_order_ids:
            problems.append(f"evidence references unknown order: {evidence_id}")
        elif kind == "item" and rest not in valid_item_ids:
            problems.append(f"evidence references unknown item: {evidence_id}")
        elif kind == "payment" and rest not in valid_payment_ids:
            problems.append(f"evidence references unknown payment: {evidence_id}")
        elif kind == "seller" and rest not in valid_seller_ids:
            problems.append(f"evidence references unknown seller: {evidence_id}")

    return problems
