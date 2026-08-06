import time

from src.agents.base import BaseAgent, elapsed_ms
from src.facts import payment_facts


class PaymentAgent(BaseAgent):
    name = "PaymentAgent"
    role_description = (
        "Sums payment rows and reconciles them against item price plus freight "
        "from the order_payments and order_items tables."
    )
    allowed_tables = ["order_payments", "order_items"]

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "request":
            raise ValueError("PaymentAgent only handles request messages")
        self.assert_scope("order_payments")
        self.assert_scope("order_items")
        order_id = msg.payload["order_id"]
        facts = payment_facts(self.data, order_id)
        narrative, degraded = self.narrate(
            {
                "order_id": order_id,
                "payment_total_brl": facts["payment_total_brl"],
                "expected_total_brl": facts["expected_total_brl"],
                "difference_brl": facts["difference_brl"],
                "reconciled": facts["reconciled"],
                "n_payments": facts["n_payments"],
            }
        )
        return self._respond(
            msg,
            {"facts": facts, "narrative": narrative},
            latency_ms=elapsed_ms(start),
            llm_used=self.llm is not None,
            degraded=degraded,
        )
