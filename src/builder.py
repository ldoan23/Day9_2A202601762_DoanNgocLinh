from src.facts import (
    customer_facts,
    delivery_facts,
    order_product_facts,
    payment_facts,
)
from src.policy import apply_policy

_EVIDENCE_LIMIT = 20


def _trim_evidence(evidence):
    if len(evidence) <= _EVIDENCE_LIMIT:
        return evidence
    head = evidence[:1]
    tail = evidence[-1:]
    middle = evidence[1:-1]
    keep = _EVIDENCE_LIMIT - 2
    left = keep // 2
    right = keep - left
    return head + middle[:left] + middle[len(middle) - right:] + tail


def _build_evidence_ids(order_id, item_ids, payment_ids, responsible_parties, policy_code):
    seller_ids = [p["party_id"] for p in responsible_parties if p["party_type"] == "seller"]
    evidence = ["order:%s" % order_id]
    evidence.extend("item:%s" % item_id for item_id in item_ids)
    evidence.extend("payment:%s" % payment_id for payment_id in payment_ids)
    evidence.extend("seller:%s" % sid for sid in seller_ids)
    evidence.append("policy:%s" % policy_code)
    return _trim_evidence(evidence)


def build_payload(data, order_id, case_id):
    facts = {}
    facts.update(customer_facts(data, order_id))
    facts.update(order_product_facts(data, order_id))
    facts.update(payment_facts(data, order_id))
    facts.update(delivery_facts(data, order_id))
    facts["order_id"] = order_id
    facts["order_status"] = data.orders_by_id[order_id]["order_status"]

    policy = apply_policy(facts)
    evidence_ids = _build_evidence_ids(
        order_id,
        facts["item_ids"],
        facts["payment_ids"],
        policy["responsible_parties"],
        policy["ranked_causes"][0]["cause_code"],
    )

    return {
        "case_id": case_id,
        "case_assessment": {
            "primary_issue": policy["primary_issue"],
            "secondary_issues": policy["secondary_issues"],
            "case_status": policy["case_status"],
            "confidence": policy["confidence"],
        },
        "affected_entities": {
            "order_ids": [order_id],
            "item_ids": facts["item_ids"],
            "seller_ids": facts["seller_ids"],
            "payment_ids": facts["payment_ids"],
        },
        "customer_context": {
            "customer_unique_id": facts["customer_unique_id"],
            "related_order_ids": facts["related_order_ids"],
        },
        "product_context": {
            "product_ids": facts["product_ids"],
            "category_names": facts["category_names"],
        },
        "delivery_analysis": {
            "delivered_at": facts["delivered_at"],
            "estimated_delivery_at": facts["estimated_delivery_at"],
            "carrier_handoff_at": facts["carrier_handoff_at"],
            "delivery_variance_hours": facts["delivery_variance_hours"],
            "seller_handoff_analysis": facts["seller_handoff_analysis"],
            "late_handoff_seller_ids": facts["late_handoff_seller_ids"],
        },
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": facts["item_total_brl"],
            "freight_total_brl": facts["freight_total_brl"],
            "expected_total_brl": facts["expected_total_brl"],
            "payment_total_brl": facts["payment_total_brl"],
            "difference_brl": facts["difference_brl"],
            "reconciled": facts["reconciled"],
            "payment_types": facts["payment_types"],
        },
        "root_cause_analysis": {
            "ranked_causes": policy["ranked_causes"],
            "responsible_parties": policy["responsible_parties"],
        },
        "evidence_ids": evidence_ids,
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": policy["recommended_refund_brl"],
        },
        "resolution_actions": policy["resolution_actions"],
    }
