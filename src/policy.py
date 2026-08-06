CONFIDENCE = {
    "canceled_order_paid": 0.95,
    "unavailable_order_paid": 0.95,
    "late_delivery_seller": 0.92,
    "late_delivery_logistics": 0.90,
    "valid_split_payment": 0.90,
    "unsupported_late_claim": 0.88,
}

RANKED_CAUSES = {
    "late_delivery_seller": ["SELLER_HANDOFF_AFTER_LIMIT", "CARRIER_DELIVERED_AFTER_ESTIMATE"],
    "late_delivery_logistics": ["CARRIER_DELIVERED_AFTER_ESTIMATE"],
    "canceled_order_paid": ["ORDER_CANCELED_AFTER_PAYMENT"],
    "unavailable_order_paid": ["ORDER_UNAVAILABLE_AFTER_PAYMENT"],
    "valid_split_payment": ["MULTIPLE_PAYMENTS_RECONCILED"],
    "unsupported_late_claim": ["DELIVERY_WITHIN_ESTIMATE"],
}

MAIN_ACTION = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}


def _primary_issue(facts):
    status = facts["order_status"]
    payment_total = facts["payment_total_brl"]
    if status == "canceled" and payment_total and payment_total > 0:
        return "canceled_order_paid"
    if status == "unavailable" and payment_total and payment_total > 0:
        return "unavailable_order_paid"
    variance = facts["delivery_variance_hours"]
    if variance is not None and variance > 0 and facts["late_handoff_seller_ids"]:
        return "late_delivery_seller"
    if variance is not None and variance > 0:
        return "late_delivery_logistics"
    if facts["n_payments"] >= 2 and facts["reconciled"] is True:
        return "valid_split_payment"
    return "unsupported_late_claim"


def _secondary_issues(facts):
    issues = []
    if facts["n_items"] >= 2:
        issues.append("multi_item_order")
    if facts["n_sellers"] >= 2:
        issues.append("multi_seller_order")
    if facts["n_payments"] >= 2:
        issues.append("split_payment")
    if facts["related_order_ids"]:
        issues.append("repeat_customer")
    if facts["n_categories"] >= 2:
        issues.append("multiple_categories")
    return issues


def _responsible_parties(primary, facts):
    if primary in ("canceled_order_paid", "unavailable_order_paid"):
        return [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
    if primary == "late_delivery_seller":
        return [
            {"party_type": "seller", "party_id": sid}
            for sid in facts["late_handoff_seller_ids"][:3]
        ]
    if primary == "late_delivery_logistics":
        return [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
    return []


def _recommended_refund(primary, facts):
    if primary in ("canceled_order_paid", "unavailable_order_paid"):
        return facts["payment_total_brl"] or 0
    if primary in ("late_delivery_seller", "late_delivery_logistics"):
        return facts["freight_total_brl"] or 0
    return 0


def _resolution_actions(primary, refund, secondary_issues):
    actions = [MAIN_ACTION[primary]]
    if primary == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary == "late_delivery_logistics":
        actions.append("review_carrier_delay")
    if refund and refund > 0:
        actions.append("verify_refund_completion")
    if "multi_seller_order" in secondary_issues:
        actions.append("coordinate_multi_seller_case")
    if "split_payment" in secondary_issues and primary != "valid_split_payment":
        actions.append("verify_payment_allocation")
    return actions[:5]


def apply_policy(facts):
    primary = _primary_issue(facts)
    secondary_issues = _secondary_issues(facts)
    ranked_causes = [
        {"cause_code": code, "rank": idx + 1}
        for idx, code in enumerate(RANKED_CAUSES[primary])
    ]
    responsible_parties = _responsible_parties(primary, facts)
    recommended_refund_brl = _recommended_refund(primary, facts)
    return {
        "primary_issue": primary,
        "secondary_issues": secondary_issues,
        "ranked_causes": ranked_causes,
        "responsible_parties": responsible_parties,
        "recommended_refund_brl": recommended_refund_brl,
        "case_status": "action_required" if recommended_refund_brl > 0 else "no_action",
        "confidence": CONFIDENCE[primary],
        "resolution_actions": _resolution_actions(
            primary, recommended_refund_brl, secondary_issues
        ),
    }
