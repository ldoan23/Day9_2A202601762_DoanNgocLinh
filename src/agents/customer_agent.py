"""Customer Agent: summarizes customer identity and purchase history.

Calls the LLM (handoff step 1) and returns a small structured finding that
the Policy Agent will later consume alongside the other domain findings.
"""

from src.llm_client import call_llm_json

SYSTEM_PROMPT = """You are the Customer Agent in an e-commerce dispute \
investigation pipeline. You receive a customer's identity and their other \
order IDs (already verified from the database - do not invent any). \
Respond with ONLY a JSON object with exactly these keys:
{"repeat_customer": bool, "related_order_count": int, "notes": "<= 30 words, English or Vietnamese matching the input>"}
"repeat_customer" is true iff related_order_count > 0. Do not add any other keys or text."""


def run(customer: dict | None, related_order_ids: list[str]) -> dict:
    if customer is None:
        return {"repeat_customer": False, "related_order_count": 0, "notes": "Customer not found."}

    user_prompt = (
        f"customer_unique_id: {customer.get('customer_unique_id')}\n"
        f"related_order_ids ({len(related_order_ids)}): {related_order_ids}"
    )
    finding = call_llm_json(SYSTEM_PROMPT, user_prompt)
    finding["customer_unique_id"] = customer.get("customer_unique_id")
    return finding
