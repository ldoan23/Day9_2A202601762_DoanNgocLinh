import re
from decimal import Decimal, ROUND_HALF_UP

PRIMARY_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}

SECONDARY_ISSUES = {
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
}

CASE_STATUSES = {"action_required", "no_action"}

EVIDENCE_PATTERNS = [
    re.compile(r"^order:[^:]+$"),
    re.compile(r"^item:[^:]+:\d+$"),
    re.compile(r"^payment:[^:]+:\d+$"),
    re.compile(r"^seller:[^:]+$"),
    re.compile(r"^policy:[A-Z][A-Z_]*$"),
]

MONEY_FIELDS = [
    "item_total_brl",
    "freight_total_brl",
    "expected_total_brl",
    "payment_total_brl",
    "difference_brl",
]

ARRAY_LIMITS = {
    ("affected_entities", "order_ids"): 5,
    ("affected_entities", "item_ids"): 5,
    ("affected_entities", "seller_ids"): 3,
    ("affected_entities", "payment_ids"): 5,
    ("customer_context", "related_order_ids"): 5,
    ("product_context", "product_ids"): 5,
    ("product_context", "category_names"): 5,
    ("root_cause_analysis", "ranked_causes"): 3,
    ("root_cause_analysis", "responsible_parties"): 3,
    ("evidence_ids",): 20,
    ("resolution_actions",): 5,
}

REQUIRED_TOP_LEVEL = [
    "case_id",
    "case_assessment",
    "affected_entities",
    "customer_context",
    "product_context",
    "delivery_analysis",
    "payment_reconciliation",
    "root_cause_analysis",
    "evidence_ids",
    "financial_resolution",
    "resolution_actions",
]

REQUIRED_SECTIONS = {
    "case_assessment": ["primary_issue", "secondary_issues", "case_status", "confidence"],
    "affected_entities": ["order_ids", "item_ids", "seller_ids", "payment_ids"],
    "customer_context": ["customer_unique_id", "related_order_ids"],
    "product_context": ["product_ids", "category_names"],
    "delivery_analysis": [
        "delivered_at",
        "estimated_delivery_at",
        "carrier_handoff_at",
        "delivery_variance_hours",
        "seller_handoff_analysis",
        "late_handoff_seller_ids",
    ],
    "payment_reconciliation": [
        "currency",
        "item_total_brl",
        "freight_total_brl",
        "expected_total_brl",
        "payment_total_brl",
        "difference_brl",
        "reconciled",
        "payment_types",
    ],
    "root_cause_analysis": ["ranked_causes", "responsible_parties"],
    "financial_resolution": ["currency", "recommended_refund_brl"],
}


class ValidationError(Exception):
    pass


def _two_decimal_or_null(value, label):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("%s must be a number or null" % label)
    decimal_value = Decimal(str(value))
    if decimal_value != decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
        raise ValidationError("%s has more than 2 decimal places: %r" % (label, value))


def _check_evidence_id(value):
    if not isinstance(value, str):
        raise ValidationError("evidence id must be a string: %r" % (value,))
    if not any(pattern.match(value) for pattern in EVIDENCE_PATTERNS):
        raise ValidationError("evidence id does not match any allowed format: %r" % (value,))


def validate(payload):
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a dict")
    for key in REQUIRED_TOP_LEVEL:
        if key not in payload:
            raise ValidationError("missing required key: %s" % key)

    for section, keys in REQUIRED_SECTIONS.items():
        for key in keys:
            if key not in payload[section]:
                raise ValidationError("missing required key: %s.%s" % (section, key))

    for keys, limit in ARRAY_LIMITS.items():
        value = payload[keys[0]]
        for key in keys[1:]:
            value = value[key]
        if not isinstance(value, list):
            raise ValidationError("%s must be a list" % ".".join(keys))
        if len(value) > limit:
            raise ValidationError("%s exceeds limit %d: %d" % (".".join(keys), limit, len(value)))

    assessment = payload["case_assessment"]
    if assessment["primary_issue"] not in PRIMARY_ISSUES:
        raise ValidationError("unknown primary_issue: %s" % assessment["primary_issue"])
    for issue in assessment["secondary_issues"]:
        if issue not in SECONDARY_ISSUES:
            raise ValidationError("unknown secondary_issue: %s" % issue)
    if assessment["case_status"] not in CASE_STATUSES:
        raise ValidationError("invalid case_status: %s" % assessment["case_status"])
    confidence = assessment["confidence"]
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValidationError("confidence must be a number")
    if not (0 <= confidence <= 1):
        raise ValidationError("confidence out of range: %r" % (confidence,))

    for evidence in payload["evidence_ids"]:
        _check_evidence_id(evidence)

    delivery = payload["delivery_analysis"]
    _two_decimal_or_null(delivery["delivery_variance_hours"], "delivery_variance_hours")
    for entry in delivery["seller_handoff_analysis"]:
        for key in ("seller_id", "shipping_limit_at", "handoff_variance_hours", "late_handoff"):
            if key not in entry:
                raise ValidationError("seller_handoff entry missing key: %s" % key)
        _two_decimal_or_null(entry["handoff_variance_hours"], "handoff_variance_hours")

    reconciliation = payload["payment_reconciliation"]
    for field in MONEY_FIELDS:
        _two_decimal_or_null(reconciliation[field], field)

    _two_decimal_or_null(
        payload["financial_resolution"]["recommended_refund_brl"], "recommended_refund_brl"
    )

    for cause in payload["root_cause_analysis"]["ranked_causes"]:
        if not isinstance(cause.get("cause_code"), str) or "rank" not in cause:
            raise ValidationError("invalid ranked cause entry: %r" % (cause,))
    for party in payload["root_cause_analysis"]["responsible_parties"]:
        if "party_type" not in party or "party_id" not in party:
            raise ValidationError("invalid responsible party entry: %r" % (party,))
