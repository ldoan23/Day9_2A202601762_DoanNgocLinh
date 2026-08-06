from decimal import Decimal, ROUND_HALF_UP

_MONEY_Q = Decimal("0.01")


def _to_decimal(value):
    return Decimal(str(value))


def _quantize_money(decimal_value):
    return float(decimal_value.quantize(_MONEY_Q, rounding=ROUND_HALF_UP))


def _sum_money(records, key):
    total = Decimal("0")
    for rec in records:
        total += _to_decimal(rec[key])
    return _quantize_money(total)


def _hours_between(a, b):
    if a is None or b is None:
        return None
    hours = (a - b).total_seconds() / 3600.0
    return _quantize_money(Decimal(str(hours)))


def customer_facts(data, order_id):
    order = data.orders_by_id[order_id]
    uid = data.customer_unique_by_customer.get(order["customer_id"])
    related = []
    if uid in data.orders_by_customer_unique:
        for oid, _ts in data.orders_by_customer_unique[uid]:
            if oid == order_id:
                continue
            related.append(oid)
            if len(related) >= 5:
                break
    return {
        "customer_unique_id": uid,
        "related_order_ids": related,
    }


def order_product_facts(data, order_id):
    items = data.order_items_by_order.get(order_id, [])
    sellers = []
    products = []
    categories = []
    for rec in items:
        sid = rec["seller_id"]
        if sid and sid not in sellers:
            sellers.append(sid)
        pid = rec["product_id"]
        if pid and pid not in products:
            products.append(pid)
        product = data.products_by_id.get(rec["product_id"])
        pcat = product.get("product_category_name") if product else None
        if pcat and pcat not in categories:
            categories.append(pcat)
    return {
        "item_ids": ["%s:%s" % (order_id, r["order_item_id"]) for r in items][:5],
        "seller_ids": sellers[:3],
        "product_ids": products[:5],
        "category_names": categories[:5],
        "n_items": len(items),
        "n_sellers": len(sellers),
        "n_categories": len(categories),
    }


def payment_facts(data, order_id):
    payments = data.order_payments_by_order.get(order_id, [])
    items = data.order_items_by_order.get(order_id, [])
    payment_total = Decimal("0")
    for rec in payments:
        payment_total += _to_decimal(rec["payment_value"])
    payment_total_brl = _quantize_money(payment_total)

    payment_types = []
    for rec in payments:
        ptype = rec["payment_type"]
        if ptype not in payment_types:
            payment_types.append(ptype)

    if items:
        item_total = Decimal("0")
        freight_total = Decimal("0")
        for rec in items:
            item_total += _to_decimal(rec["price"])
            freight_total += _to_decimal(rec["freight_value"])
        item_total_brl = _quantize_money(item_total)
        freight_total_brl = _quantize_money(freight_total)
        expected_total_brl = _quantize_money(item_total + freight_total)
        difference_brl = _quantize_money(payment_total - (item_total + freight_total))
        reconciled = abs(payment_total - (item_total + freight_total)) <= Decimal("0.10")
    else:
        item_total_brl = None
        freight_total_brl = None
        expected_total_brl = None
        difference_brl = None
        reconciled = None

    return {
        "payment_ids": ["%s:%s" % (order_id, r["payment_sequential"]) for r in payments][:5],
        "payment_types": payment_types,
        "item_total_brl": item_total_brl,
        "freight_total_brl": freight_total_brl,
        "expected_total_brl": expected_total_brl,
        "payment_total_brl": payment_total_brl,
        "difference_brl": difference_brl,
        "reconciled": reconciled,
        "n_payments": len(payments),
    }


def delivery_facts(data, order_id):
    order = data.orders_by_id[order_id]
    dt = data.orders_dt_by_id[order_id]
    items = data.order_items_by_order.get(order_id, [])

    delivered_at = order["order_delivered_customer_date"]
    estimated_delivery_at = order["order_estimated_delivery_date"]
    carrier_handoff_at = order["order_delivered_carrier_date"]
    variance = _hours_between(
        dt["order_delivered_customer_date"], dt["order_estimated_delivery_date"]
    )

    sellers = []
    for rec in items:
        if rec["seller_id"] not in sellers:
            sellers.append(rec["seller_id"])

    handoff = []
    late_ids = []
    for sid in sellers:
        seller_items = [r for r in items if r["seller_id"] == sid]
        ship_dt = None
        ship_raw = None
        for r in seller_items:
            d = data.item_shipping_dt.get((order_id, r["order_item_id"]))
            raw = r["shipping_limit_date"]
            if d is not None and (ship_dt is None or d < ship_dt):
                ship_dt = d
                ship_raw = raw
        handoff_variance = _hours_between(dt["order_delivered_carrier_date"], ship_dt)
        late = bool(handoff_variance is not None and handoff_variance > 0)
        entry = {
            "seller_id": sid,
            "shipping_limit_at": ship_raw,
            "handoff_variance_hours": handoff_variance,
            "late_handoff": late,
        }
        handoff.append(entry)
        if late:
            late_ids.append(sid)

    return {
        "delivered_at": delivered_at,
        "estimated_delivery_at": estimated_delivery_at,
        "carrier_handoff_at": carrier_handoff_at,
        "delivery_variance_hours": variance,
        "seller_handoff_analysis": handoff,
        "late_handoff_seller_ids": late_ids,
    }
