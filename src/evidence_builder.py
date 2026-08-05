"""Build affected_entities and evidence_ids strictly from data that was
actually joined from the CSVs (README section 5) - never invented.
"""

MAX_ORDER_IDS = 5
MAX_ITEM_IDS = 5
MAX_SELLER_IDS = 3
MAX_PAYMENT_IDS = 5
MAX_RELATED_ORDER_IDS = 5
MAX_PRODUCT_IDS = 5
MAX_CATEGORIES = 5
MAX_EVIDENCE = 20
MAX_RESPONSIBLE_PARTIES = 3
MAX_ROOT_CAUSES = 3
MAX_ACTIONS = 5

SECONDARY_ISSUE_ORDER = [
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
]

ACTION_ORDER = [
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
    "review_seller_handoff",
    "review_carrier_delay",
    "verify_refund_completion",
    "coordinate_multi_seller_case",
    "verify_payment_allocation",
]


def canonicalize_order(items: list[str], canonical_order: list[str]) -> list[str]:
    """Re-sort a set of already-decided labels into the fixed display order
    required by README - this only reorders, it never decides which labels
    are present (that decision belongs to the LLM)."""
    known = [x for x in canonical_order if x in items]
    unknown = [x for x in items if x not in canonical_order]
    return known + unknown


def build_affected_entities(order: dict, items: list[dict], payments: list[dict], sellers: list[dict]) -> dict:
    order_id = order["order_id"]
    return {
        "order_ids": [order_id][:MAX_ORDER_IDS],
        "item_ids": [f"{order_id}:{i['order_item_id']}" for i in items][:MAX_ITEM_IDS],
        "seller_ids": [s["seller_id"] for s in sellers][:MAX_SELLER_IDS],
        "payment_ids": [f"{order_id}:{p['payment_sequential']}" for p in payments][:MAX_PAYMENT_IDS],
    }


def build_customer_context(customer: dict, related_order_ids: list[str]) -> dict:
    return {
        "customer_unique_id": customer["customer_unique_id"] if customer else None,
        "related_order_ids": related_order_ids[:MAX_RELATED_ORDER_IDS],
    }


def build_product_context(products: list[dict]) -> dict:
    product_ids = [p["product_id"] for p in products][:MAX_PRODUCT_IDS]
    categories = []
    for p in products:
        cat = p.get("product_category_name_english")
        if cat is not None and cat not in categories:
            categories.append(cat)
    return {
        "product_ids": product_ids,
        "category_names": categories[:MAX_CATEGORIES],
    }


def build_evidence_ids(order: dict, items: list[dict], payments: list[dict], responsible_parties: list[dict], root_cause_code: str) -> list[str]:
    """order -> items -> payments -> responsible sellers -> policy, capped
    at 20 and at the same per-entity limits as affected_entities so the
    two stay consistent.
    """
    order_id = order["order_id"]
    evidence = [f"order:{order_id}"]

    for item in items[:MAX_ITEM_IDS]:
        evidence.append(f"item:{order_id}:{item['order_item_id']}")

    for payment in payments[:MAX_PAYMENT_IDS]:
        evidence.append(f"payment:{order_id}:{payment['payment_sequential']}")

    responsible_seller_ids = [
        rp["party_id"] for rp in responsible_parties if rp["party_type"] == "seller"
    ][:MAX_SELLER_IDS]
    for seller_id in responsible_seller_ids:
        evidence.append(f"seller:{seller_id}")

    evidence.append(f"policy:{root_cause_code}")

    return evidence[:MAX_EVIDENCE]
