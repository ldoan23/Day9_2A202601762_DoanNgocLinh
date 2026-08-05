"""Policy Agent: THE decision-maker for EC_POLICY_V2 classification.

Per team decision (2026-08-05), classification (primary_issue,
secondary_issues, responsible_parties, refund amount, resolution_actions)
must NOT be hard-coded as Python if/elif - it has to be the LLM's own
judgment call over the verified evidence. Python only supplies exact
computed numbers (calculations.py) and assembles/orders the LLM's own
boolean judgments into arrays (evidence_builder.canonicalize_order) - it
never decides inclusion/exclusion itself.

Split into 4 focused LLM calls instead of one mega-prompt: a 7B model is
far more reliable answering one judgment at a time than juggling many
decisions in a single response (verified empirically - the single-prompt
version dropped required fields, miscounted list lengths, and mixed up
rule priority). The 4 calls are: classify_primary, classify_secondary,
classify_bonus_actions, classify_ambiguity (confidence signal only).
"""

from src.llm_client import call_llm_json

# --- Call 1: primary classification -----------------------------------

CLASSIFY_SYSTEM_PROMPT = """You are the Policy Agent applying policy \
EC_POLICY_V2 in an e-commerce dispute investigation pipeline. All numbers \
below were computed by a deterministic engine from verified database \
records - treat them as ground truth, do not recompute them, do not \
invent any ID that is not listed.

Evaluate in this priority order, pick the FIRST rule that fits:
1. canceled_order_paid: order_status is "canceled" AND payment_total_brl > 0
   -> responsible: [{"party_type":"platform","party_id":"OLIST_PLATFORM"}]
   -> refund = payment_total_brl ; root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
   -> primary_action = "issue_full_refund"
2. unavailable_order_paid: order_status is "unavailable" AND payment_total_brl > 0
   -> responsible: [{"party_type":"platform","party_id":"OLIST_PLATFORM"}]
   -> refund = payment_total_brl ; root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
   -> primary_action = "issue_full_refund"
3. late_delivery_seller: delivery_variance_hours > 0 AND late_handoff_seller_ids is non-empty
   -> responsible: one entry per seller in late_handoff_seller_ids, {"party_type":"seller","party_id":"<seller_id>"}
   -> refund = freight_total_brl ; root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
   -> primary_action = "refund_freight"
4. late_delivery_logistics: delivery_variance_hours > 0 AND late_handoff_seller_ids is empty
   -> responsible: [{"party_type":"logistics_provider","party_id":"LOGISTICS_PROVIDER"}]
   -> refund = freight_total_brl ; root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
   -> primary_action = "refund_freight"
5. valid_split_payment: delivery_variance_hours <= 0 (or null) AND reconciled is true AND payment_count is 2 or greater.
   -> responsible: [] ; refund = 0 ; root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
   -> primary_action = "explain_valid_split_payment"
6. unsupported_late_claim: delivery_variance_hours <= 0 (or null) AND reconciled is true AND payment_count is exactly 1.
   -> responsible: [] ; refund = 0 ; root_cause_code = "DELIVERY_WITHIN_ESTIMATE"
   -> primary_action = "reject_late_refund"
Note: delivery_variance_hours is (actual - estimated) in hours. A NEGATIVE number (e.g. -367.3) means the order was delivered EARLY, which means it is NOT late.

CRITICAL - check rules in order, do not skip ahead:
- FIRST check if delivery_variance_hours > 0 (strictly positive). If it is strictly positive, the \
answer is rule 3 or rule 4 (late_delivery_seller / late_delivery_logistics) \
- this is true NO MATTER how many payment rows there are or whether they \
reconcile. Rules 3/4 always win over rule 5/6 when the delivery is late.
- ONLY if delivery is NOT late (delivery_variance_hours <= 0, or negative, or null) do \
you move on to rule 5 vs rule 6. Between those two: if payment_count is 2 or greater \
AND reconciled is true, pick rule 5 "valid_split_payment". Only pick rule 6 \
"unsupported_late_claim" when payment_count is exactly 1 (a single payment row).

Respond with ONLY a JSON object with exactly these keys:
{
  "primary_issue": "<one of: canceled_order_paid, unavailable_order_paid, late_delivery_seller, late_delivery_logistics, valid_split_payment, unsupported_late_claim>",
  "root_cause_code": "<matching code from the rule you picked>",
  "primary_action": "<matching primary_action from the rule you picked>",
  "responsible_parties": [{"party_type": "...", "party_id": "..."}],
  "recommended_refund_brl": <number, copy the exact value specified by the rule you picked>
}
Do not add any other keys or text."""

# --- Call 4 (separate from classification, so it can't degrade rule 3/4
# accuracy): ambiguity flags used to derive `confidence` arithmetically. ---

AMBIGUITY_SYSTEM_PROMPT = """You are the Policy Agent double-checking how \
unambiguous a classification decision was, given the same evidence. Flag \
concrete signs of ambiguity:
- "near_late_threshold": true if delivery_variance_hours is within 24 hours of 0 (close call between late/early)
- "near_reconciliation_edge": true if difference_brl is within 0.05 BRL of the 0.10 tolerance edge (close call between reconciled/not)
- "missing_data": true if any value below is null

Respond with ONLY a JSON object with exactly these 3 boolean keys:
{"near_late_threshold": bool, "near_reconciliation_edge": bool, "missing_data": bool}
Do not add any other keys or text."""


def classify_ambiguity(case_id: str, delivery_variance_hours, difference_brl) -> dict:
    user_prompt = (
        f"case_id: {case_id}\n"
        f"delivery_variance_hours: {delivery_variance_hours}\n"
        f"difference_brl: {difference_brl}"
    )
    return call_llm_json(AMBIGUITY_SYSTEM_PROMPT, user_prompt)


def classify_primary(case_id: str, order_status: str, payment_result: dict, payment_count: int, delivery_variance_hours, handoff_result: dict) -> dict:
    user_prompt = (
        f"case_id: {case_id}\n"
        f"order_status: {order_status}\n"
        f"payment_total_brl: {payment_result.get('payment_total_brl')}\n"
        f"payment_count: {payment_count}\n"
        f"reconciled: {payment_result.get('reconciled')}\n"
        f"delivery_variance_hours: {delivery_variance_hours}\n"
        f"late_handoff_seller_ids: {handoff_result.get('late_handoff_seller_ids')}\n"
    )
    return call_llm_json(CLASSIFY_SYSTEM_PROMPT, user_prompt)


# --- Call 2: secondary issues (5 independent yes/no judgments) --------

SECONDARY_SYSTEM_PROMPT = """You are the Policy Agent checking secondary \
issue flags for an e-commerce dispute case. You are given exact counts \
computed by a deterministic engine - use ONLY these counts, do not guess.

Answer these 5 independent yes/no questions. WARNING: four of them use \
threshold 2, but repeat_customer uses a DIFFERENT threshold of 1 - do not \
apply the same ">= 2" rule to all five, read each threshold carefully:
- multi_item_order: is item_count >= 2 ?
- multi_seller_order: is distinct_seller_count >= 2 ?
- split_payment: is payment_count >= 2 ?
- repeat_customer: is related_order_count >= 1 ? (threshold is 1, NOT 2 - if related_order_count is 1, the answer is true)
- multiple_categories: is distinct_category_count >= 2 ?

Worked example: item_count=1, distinct_seller_count=1, payment_count=1, \
related_order_count=1, distinct_category_count=1 ->
{"multi_item_order": false, "multi_seller_order": false, "split_payment": false, "repeat_customer": true, "multiple_categories": false}
(repeat_customer is the ONLY true value here, because 1 >= 1 even though the other four need 1 >= 2 which is false.)

Respond with ONLY a JSON object with exactly these 5 boolean keys:
{"multi_item_order": bool, "multi_seller_order": bool, "split_payment": bool, "repeat_customer": bool, "multiple_categories": bool}
Do not add any other keys or text."""


def classify_secondary(case_id: str, item_count: int, seller_count: int, payment_count: int, related_order_count: int, category_count: int) -> dict:
    user_prompt = (
        f"case_id: {case_id}\n"
        f"item_count: {item_count}\n"
        f"distinct_seller_count: {seller_count}\n"
        f"payment_count: {payment_count}\n"
        f"related_order_count: {related_order_count}\n"
        f"distinct_category_count: {category_count}"
    )
    return call_llm_json(SECONDARY_SYSTEM_PROMPT, user_prompt)


# --- Call 3: bonus resolution actions (beyond the primary action) -----

ACTIONS_SYSTEM_PROMPT = """You are the Policy Agent deciding which BONUS \
resolution actions apply, in addition to the primary action already \
chosen. Your decision must follow these strict logic mappings:

1. review_seller_handoff: true if and only if primary_issue is "late_delivery_seller". Otherwise false.
2. review_carrier_delay: true if and only if primary_issue is "late_delivery_logistics". Otherwise false.
3. verify_refund_completion: true if and only if primary_issue is one of: "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller", "late_delivery_logistics". Otherwise false.
4. coordinate_multi_seller_case: true if and only if multi_seller_order is true. Otherwise false.
5. verify_payment_allocation: true if split_payment is true, BUT it must be false if primary_issue is "valid_split_payment". Otherwise false.

IMPORTANT: If primary_issue is "valid_split_payment", verify_payment_allocation MUST be false.

Respond with ONLY a JSON object with exactly these 5 boolean keys:
{"review_seller_handoff": bool, "review_carrier_delay": bool, "verify_refund_completion": bool, "coordinate_multi_seller_case": bool, "verify_payment_allocation": bool}
Do not add any other keys or text."""


def classify_bonus_actions(case_id: str, primary_issue: str, multi_seller_order: bool, split_payment: bool) -> dict:
    user_prompt = (
        f"case_id: {case_id}\n"
        f"primary_issue: {primary_issue}\n"
        f"multi_seller_order: {multi_seller_order}\n"
        f"split_payment: {split_payment}"
    )
    return call_llm_json(ACTIONS_SYSTEM_PROMPT, user_prompt)


def run(
    case_id: str,
    order_status: str,
    payment_result: dict,
    payment_count: int,
    delivery_variance_hours,
    handoff_result: dict,
    item_count: int,
    seller_ids: list[str],
    related_order_count: int,
    category_names: list[str],
) -> dict:
    classification = classify_primary(case_id, order_status, payment_result, payment_count, delivery_variance_hours, handoff_result)

    secondary_flags = classify_secondary(
        case_id, item_count, len(seller_ids), payment_count, related_order_count, len(category_names),
    )
    secondary_issues = [label for label, is_set in secondary_flags.items() if is_set]

    primary_issue = classification.get("primary_issue")
    action_flags = classify_bonus_actions(
        case_id,
        primary_issue,
        secondary_flags.get("multi_seller_order", False),
        secondary_flags.get("split_payment", False),
    )
    resolution_actions = [classification.get("primary_action")]
    resolution_actions += [label for label, is_set in action_flags.items() if is_set]

    ambiguity = classify_ambiguity(case_id, delivery_variance_hours, payment_result["difference_brl"])

    # confidence = 1.0 minus a penalty per ambiguity flag the LLM itself
    # raised - arithmetic on the LLM's own judgment, not a classification
    # decision, so it stays out of the "no hard-coded logic" ban.
    confidence = 1.0
    if ambiguity.get("near_late_threshold"):
        confidence -= 0.15
    if ambiguity.get("near_reconciliation_edge"):
        confidence -= 0.15
    if ambiguity.get("missing_data"):
        confidence -= 0.3
    confidence = round(max(0.0, min(1.0, confidence)), 2)

    return {
        "primary_issue": primary_issue,
        "root_cause_code": classification.get("root_cause_code"),
        "responsible_parties": classification.get("responsible_parties", []),
        "recommended_refund_brl": classification.get("recommended_refund_brl", 0),
        "confidence": confidence,
        "secondary_issues": secondary_issues,
        "resolution_actions": resolution_actions,
    }
