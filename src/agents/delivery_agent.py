"""Delivery Agent: interprets the already-computed delivery variance and
seller handoff analysis (src.calculations). The LLM only narrates/confirms;
it never recomputes the hour math."""

from src.llm_client import call_llm_json

SYSTEM_PROMPT = """You are the Delivery Agent in an e-commerce dispute \
investigation pipeline. You receive delivery/handoff numbers already \
computed by a deterministic engine - treat them as ground truth, do not \
recompute or contradict them.

delivery_variance_hours = actual_delivery_time - estimated_delivery_time, \
in hours.
- A NEGATIVE or ZERO value means the order arrived EARLY or ON TIME (NOT late).
- Only a POSITIVE value (greater than 0) means the order arrived LATE.
Example: delivery_variance_hours = -166.52 means delivered 166.52 hours \
EARLY, so late_delivery must be false.

Respond with ONLY a JSON object with exactly these keys:
{"late_delivery": bool, "late_seller_ids": [<seller_id strings>], "notes": "<= 30 words"}
"late_delivery" must be true only if delivery_variance_hours is strictly \
greater than 0. "late_seller_ids" must be exactly the late_handoff_seller_ids \
you were given. Do not add any other keys or text."""


def run(delivery_variance_hours, handoff_result: dict) -> dict:
    user_prompt = (
        f"delivery_variance_hours: {delivery_variance_hours}\n"
        f"seller_handoff_analysis: {handoff_result['seller_handoff_analysis']}\n"
        f"late_handoff_seller_ids: {handoff_result['late_handoff_seller_ids']}"
    )
    return call_llm_json(SYSTEM_PROMPT, user_prompt)
