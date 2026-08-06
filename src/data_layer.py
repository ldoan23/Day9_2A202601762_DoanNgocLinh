import os

import pandas as pd

CSV_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

ORDER_DT_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

ITEM_DT_COLS = ["shipping_limit_date"]


class OlistData:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.orders_by_id = {}
        self.orders_dt_by_id = {}
        self.order_items_by_order = {}
        self.item_shipping_dt = {}
        self.order_payments_by_order = {}
        self.customers_by_id = {}
        self.products_by_id = {}
        self.sellers_by_id = {}
        self.customer_unique_by_customer = {}
        self.orders_by_customer_unique = {}
        self._load()

    def _read(self, key):
        path = os.path.join(self.data_dir, CSV_FILES[key])
        df = pd.read_csv(path, dtype=str)
        return df.where(pd.notnull(df), None)

    def _load(self):
        orders_df = self._read("orders")
        items_df = self._read("order_items")
        payments_df = self._read("order_payments")
        customers_df = self._read("customers")
        products_df = self._read("products")
        sellers_df = self._read("sellers")

        order_ids = orders_df["order_id"].tolist()
        for col in ORDER_DT_COLS:
            series = pd.to_datetime(orders_df[col], errors="coerce")
            for oid, val in zip(order_ids, series):
                self.orders_dt_by_id.setdefault(oid, {})[col] = (
                    None if pd.isna(val) else val.to_pydatetime()
                )

        item_ids = list(zip(items_df["order_id"], items_df["order_item_id"]))
        item_ts = pd.to_datetime(items_df["shipping_limit_date"], errors="coerce")
        for key, val in zip(item_ids, item_ts):
            self.item_shipping_dt[key] = None if pd.isna(val) else val.to_pydatetime()

        items = items_df.to_dict("records")

        for rec in orders_df.to_dict("records"):
            oid = rec["order_id"]
            self.orders_by_id[oid] = rec

        item_groups = {}
        for rec in items:
            item_groups.setdefault(rec["order_id"], []).append(rec)
        for oid in item_groups:
            item_groups[oid].sort(key=lambda r: int(r["order_item_id"]))
        self.order_items_by_order = item_groups

        payment_groups = {}
        for rec in payments_df.to_dict("records"):
            payment_groups.setdefault(rec["order_id"], []).append(rec)
        for oid in payment_groups:
            payment_groups[oid].sort(key=lambda r: int(r["payment_sequential"]))
        self.order_payments_by_order = payment_groups

        for rec in customers_df.to_dict("records"):
            cid = rec["customer_id"]
            self.customers_by_id[cid] = rec
            self.customer_unique_by_customer[cid] = rec["customer_unique_id"]

        for rec in products_df.to_dict("records"):
            self.products_by_id[rec["product_id"]] = rec

        for rec in sellers_df.to_dict("records"):
            self.sellers_by_id[rec["seller_id"]] = rec

        cust_orders = {}
        for oid, rec in self.orders_by_id.items():
            cust_orders.setdefault(rec["customer_id"], []).append(
                (rec["order_purchase_timestamp"] or "", oid)
            )
        uid_orders = {}
        for cid, lst in cust_orders.items():
            uid = self.customer_unique_by_customer.get(cid)
            if uid is None:
                continue
            uid_orders.setdefault(uid, []).extend(lst)
        for uid, lst in uid_orders.items():
            lst.sort()
            self.orders_by_customer_unique[uid] = [(oid, ts) for ts, oid in lst]
