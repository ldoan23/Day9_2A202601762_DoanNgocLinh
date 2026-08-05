"""Load Olist CSV datasets and join them into a per-case data bundle."""

import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

_orders = pd.read_csv(os.path.join(DATA_DIR, "olist_orders_dataset.csv"))
_customers = pd.read_csv(os.path.join(DATA_DIR, "olist_customers_dataset.csv"))
_order_items = pd.read_csv(os.path.join(DATA_DIR, "olist_order_items_dataset.csv"))
_order_payments = pd.read_csv(os.path.join(DATA_DIR, "olist_order_payments_dataset.csv"))
_products = pd.read_csv(os.path.join(DATA_DIR, "olist_products_dataset.csv"))
_sellers = pd.read_csv(os.path.join(DATA_DIR, "olist_sellers_dataset.csv"))
_category_translation = pd.read_csv(os.path.join(DATA_DIR, "product_category_name_translation.csv"))

_products = _products.merge(_category_translation, on="product_category_name", how="left")

_ORDER_TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def _clean_order(order: dict) -> dict:
    """Replace pandas NaN with None for timestamp columns so the dict is
    directly JSON-serializable and matches the "null if missing" schema
    requirement."""
    cleaned = dict(order)
    for col in _ORDER_TIMESTAMP_COLUMNS:
        if col in cleaned and pd.isna(cleaned[col]):
            cleaned[col] = None
    return cleaned


def get_case_data(claimed_order_id: str) -> dict:
    """Fetch and join every row needed to investigate `claimed_order_id`.

    Returns a dict with keys: order, customer, items, payments, sellers,
    products, related_order_ids. `order` is None if the order_id does not
    exist in the dataset.
    """
    order_rows = _orders[_orders["order_id"] == claimed_order_id]
    if order_rows.empty:
        return {
            "order": None,
            "customer": None,
            "items": [],
            "payments": [],
            "sellers": [],
            "products": [],
            "related_order_ids": [],
        }

    order = _clean_order(order_rows.iloc[0].to_dict())

    customer_rows = _customers[_customers["customer_id"] == order["customer_id"]]
    customer = customer_rows.iloc[0].to_dict() if not customer_rows.empty else None

    items_df = _order_items[_order_items["order_id"] == claimed_order_id].sort_values("order_item_id")
    items = items_df.to_dict(orient="records")

    payments_df = _order_payments[_order_payments["order_id"] == claimed_order_id].sort_values(
        "payment_sequential"
    )
    payments = payments_df.to_dict(orient="records")

    seller_ids = items_df["seller_id"].dropna().unique().tolist()
    sellers = _sellers[_sellers["seller_id"].isin(seller_ids)].to_dict(orient="records")

    product_ids = items_df["product_id"].dropna().unique().tolist()
    products = _products[_products["product_id"].isin(product_ids)].to_dict(orient="records")

    related_order_ids = []
    if customer is not None:
        customer_unique_id = customer["customer_unique_id"]
        sibling_customer_ids = _customers[
            _customers["customer_unique_id"] == customer_unique_id
        ]["customer_id"]
        related_orders = _orders[
            _orders["customer_id"].isin(sibling_customer_ids)
            & (_orders["order_id"] != claimed_order_id)
        ]
        related_order_ids = related_orders["order_id"].tolist()

    return {
        "order": order,
        "customer": customer,
        "items": items,
        "payments": payments,
        "sellers": sellers,
        "products": products,
        "related_order_ids": related_order_ids,
    }
