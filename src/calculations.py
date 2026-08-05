"""Pure-Python calculations for delivery variance, seller handoff and payment
reconciliation. Kept free of LLM calls so every number is exact and
reproducible.
"""

import pandas as pd


def _to_datetime(value):
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value)


def compute_delivery_variance(order: dict) -> float | None:
    """Hours between actual delivery and the estimated delivery date.

    Positive => delivered late. None when the order was never delivered.
    """
    delivered = _to_datetime(order.get("order_delivered_customer_date"))
    estimated = _to_datetime(order.get("order_estimated_delivery_date"))
    if delivered is None or estimated is None:
        return None
    hours = (delivered - estimated).total_seconds() / 3600
    return round(hours, 2)


def compute_seller_handoff(items: list[dict], order: dict) -> dict:
    """Per-seller handoff variance vs. their earliest shipping_limit_date.

    Returns {"seller_handoff_analysis": [...], "late_handoff_seller_ids": [...]}
    in stable order of first appearance in `items`.
    """
    carrier_handoff = _to_datetime(order.get("order_delivered_carrier_date"))

    seller_ids_in_order = []
    limits_by_seller: dict[str, list] = {}
    for item in items:
        seller_id = item.get("seller_id")
        if seller_id is None:
            continue
        if seller_id not in limits_by_seller:
            limits_by_seller[seller_id] = []
            seller_ids_in_order.append(seller_id)
        limit = _to_datetime(item.get("shipping_limit_date"))
        if limit is not None:
            limits_by_seller[seller_id].append(limit)

    analysis = []
    late_handoff_seller_ids = []
    for seller_id in seller_ids_in_order:
        limits = limits_by_seller[seller_id]
        if not limits or carrier_handoff is None:
            continue
        earliest_limit = min(limits)
        variance_hours = round((carrier_handoff - earliest_limit).total_seconds() / 3600, 2)
        late = variance_hours > 0
        analysis.append(
            {
                "seller_id": seller_id,
                "shipping_limit_at": earliest_limit.strftime("%Y-%m-%d %H:%M:%S"),
                "handoff_variance_hours": variance_hours,
                "late_handoff": late,
            }
        )
        if late:
            late_handoff_seller_ids.append(seller_id)

    return {
        "seller_handoff_analysis": analysis,
        "late_handoff_seller_ids": late_handoff_seller_ids,
    }


def compute_payment_reconciliation(items: list[dict], payments: list[dict]) -> dict:
    """Sum items/freight/payments and reconcile within a 0.10 BRL tolerance.

    expected_total_brl, difference_brl and reconciled are None when the
    order has no item rows, per policy EC_POLICY_V2.
    """
    item_total_brl = round(sum(i["price"] for i in items), 2) if items else 0.0
    freight_total_brl = round(sum(i["freight_value"] for i in items), 2) if items else 0.0
    payment_total_brl = round(sum(p["payment_value"] for p in payments), 2) if payments else 0.0

    payment_types = []
    for p in payments:
        ptype = p.get("payment_type")
        if ptype is not None and ptype not in payment_types:
            payment_types.append(ptype)

    if not items:
        expected_total_brl = None
        difference_brl = None
        reconciled = None
    else:
        expected_total_brl = round(item_total_brl + freight_total_brl, 2)
        difference_brl = round(payment_total_brl - expected_total_brl, 2)
        reconciled = abs(difference_brl) <= 0.10

    return {
        "item_total_brl": item_total_brl,
        "freight_total_brl": freight_total_brl,
        "expected_total_brl": expected_total_brl,
        "payment_total_brl": payment_total_brl,
        "difference_brl": difference_brl,
        "reconciled": reconciled,
        "payment_types": payment_types,
    }
