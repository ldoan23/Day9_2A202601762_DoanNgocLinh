"""Domain-fact helpers used to prepare evidence for the Policy Agent.

IMPORTANT: this module intentionally contains NO if/elif branching that
decides primary_issue, secondary_issues, responsible_parties, refund or
resolution_actions - that classification is EC_POLICY_V2's actual judgment
call and must be made by the Policy Agent (LLM), not hard-coded here. This
file only tallies raw facts (counts, unique IDs) that are handed to the LLM
as evidence, exactly like calculations.py hands it exact numbers.
"""


def unique_seller_ids(items: list[dict]) -> list[str]:
    seen = []
    for item in items:
        sid = item.get("seller_id")
        if sid is not None and sid not in seen:
            seen.append(sid)
    return seen


def unique_categories(products: list[dict]) -> list[str]:
    seen = []
    for p in products:
        cat = p.get("product_category_name_english")
        if cat is not None and cat not in seen:
            seen.append(cat)
    return seen
