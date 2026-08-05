"""Order & Product Agent: summarizes items, sellers, products and category
spread for the claimed order. Calls the LLM (handoff step 2)."""

from src.llm_client import call_llm_json

SYSTEM_PROMPT = """You are the Order & Product Agent in an e-commerce \
dispute investigation pipeline. You receive verified order items, sellers \
and products (already joined from the database - do not invent any IDs). \
Respond with ONLY a JSON object with exactly these keys:
{"multi_item": bool, "multi_seller": bool, "multiple_categories": bool, "notes": "<= 30 words"}
Do not add any other keys or text."""


def run(items: list[dict], sellers: list[dict], products: list[dict]) -> dict:
    if not items:
        return {
            "multi_item": False,
            "multi_seller": False,
            "multiple_categories": False,
            "notes": "Order has no item rows.",
        }

    seller_ids = list({i["seller_id"] for i in items if i.get("seller_id")})
    categories = list({p["product_category_name_english"] for p in products if p.get("product_category_name_english")})

    user_prompt = (
        f"item_count: {len(items)}\n"
        f"seller_ids: {seller_ids}\n"
        f"product_ids: {[p['product_id'] for p in products]}\n"
        f"category_names: {categories}"
    )
    return call_llm_json(SYSTEM_PROMPT, user_prompt)
