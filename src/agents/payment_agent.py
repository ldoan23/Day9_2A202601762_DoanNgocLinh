"""Payment Agent: interprets the already-computed payment reconciliation
(src.calculations.compute_payment_reconciliation). The LLM never redoes the
arithmetic - it only confirms/narrates so numbers stay exact."""

from src.llm_client import call_llm_json

SYSTEM_PROMPT = """You are the Payment Agent in an e-commerce dispute \
investigation pipeline. You receive numbers already computed by a \
deterministic reconciliation engine - treat them as ground truth, do not \
recompute or contradict them. Respond with ONLY a JSON object with exactly \
these keys:
{"split_payment": bool, "reconciled_confirmed": bool, "notes": "<= 30 words"}
"split_payment" is true iff there are 2 or more payment rows. \
"reconciled_confirmed" must equal the "reconciled" value you were given. \
Do not add any other keys or text."""


def run(payments: list[dict], payment_result: dict) -> dict:
    user_prompt = (
        f"payment_row_count: {len(payments)}\n"
        f"item_total_brl: {payment_result['item_total_brl']}\n"
        f"freight_total_brl: {payment_result['freight_total_brl']}\n"
        f"expected_total_brl: {payment_result['expected_total_brl']}\n"
        f"payment_total_brl: {payment_result['payment_total_brl']}\n"
        f"difference_brl: {payment_result['difference_brl']}\n"
        f"reconciled: {payment_result['reconciled']}\n"
        f"payment_types: {payment_result['payment_types']}"
    )
    return call_llm_json(SYSTEM_PROMPT, user_prompt)
