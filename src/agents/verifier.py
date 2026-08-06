import os
import threading
import time
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from src.agents.base import ALL_TABLES, BaseAgent, elapsed_ms
from src.data_layer import CSV_FILES
from src.validator import validate

_MONEY_Q = Decimal("0.01")


def _quantize(value):
    return float(value.quantize(_MONEY_Q, rounding=ROUND_HALF_UP))


class VerifierAgent(BaseAgent):
    name = "VerifierAgent"
    role_description = (
        "Independently recomputes the payment total and the delivery variance directly "
        "from the raw CSV files and validates the assembled payload schema."
    )
    allowed_tables = list(ALL_TABLES)

    def __init__(self, bus, data, llm=None):
        super().__init__(bus, data, llm)
        self._csv_cache = {}
        self._cache_lock = threading.Lock()

    def _csv(self, name):
        with self._cache_lock:
            if name in self._csv_cache:
                return self._csv_cache[name]
        path = os.path.join(self.data.data_dir, CSV_FILES[name])
        df = pd.read_csv(path, dtype=str)
        df = df.where(pd.notnull(df), None)
        with self._cache_lock:
            self._csv_cache[name] = df
        return df

    def recompute_payment_total(self, order_id):
        df = self._csv("order_payments")
        rows = df[df["order_id"] == order_id]
        total = Decimal("0")
        for value in rows["payment_value"]:
            total += Decimal(str(value))
        return _quantize(total)

    def recompute_delivery_variance(self, order_id):
        df = self._csv("orders")
        matches = df[df["order_id"] == order_id]
        if matches.empty:
            return None
        row = matches.iloc[0]
        delivered = row["order_delivered_customer_date"]
        estimated = row["order_estimated_delivery_date"]
        if not delivered or not estimated:
            return None
        delivered_dt = pd.to_datetime(delivered)
        estimated_dt = pd.to_datetime(estimated)
        hours = (delivered_dt - estimated_dt).total_seconds() / 3600.0
        return _quantize(Decimal(str(hours)))

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "verification":
            raise ValueError("VerifierAgent only handles verification messages")
        order_id = msg.payload["order_id"]
        payload = msg.payload["payload"]

        recomputed_payment = self.recompute_payment_total(order_id)
        recomputed_variance = self.recompute_delivery_variance(order_id)

        mismatches = []
        reported_payment = payload["payment_reconciliation"]["payment_total_brl"]
        if recomputed_payment != reported_payment:
            mismatches.append(
                {
                    "field": "payment_total_brl",
                    "agent_value": reported_payment,
                    "verifier_value": recomputed_payment,
                }
            )
        reported_variance = payload["delivery_analysis"]["delivery_variance_hours"]
        if recomputed_variance != reported_variance:
            mismatches.append(
                {
                    "field": "delivery_variance_hours",
                    "agent_value": reported_variance,
                    "verifier_value": recomputed_variance,
                }
            )
        try:
            validate(payload)
        except Exception as exc:
            mismatches.append(
                {
                    "field": "schema_validation",
                    "agent_value": None,
                    "verifier_value": str(exc),
                }
            )

        verdict = {"agree": not mismatches, "mismatches": mismatches}
        return self._respond(
            msg,
            {
                "verdict": verdict,
                "recomputed": {
                    "payment_total_brl": recomputed_payment,
                    "delivery_variance_hours": recomputed_variance,
                },
            },
            msg_type="verdict",
            latency_ms=elapsed_ms(start),
            llm_used=False,
            degraded=False,
        )
