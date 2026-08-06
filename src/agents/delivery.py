import time

from src.agents.base import BaseAgent, elapsed_ms
from src.facts import delivery_facts


class DeliveryAgent(BaseAgent):
    name = "DeliveryAgent"
    role_description = (
        "Computes delivery variance and per-seller handoff variance from the "
        "orders and order_items tables."
    )
    allowed_tables = ["orders", "order_items"]

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "request":
            raise ValueError("DeliveryAgent only handles request messages")
        self.assert_scope("orders")
        self.assert_scope("order_items")
        order_id = msg.payload["order_id"]
        facts = delivery_facts(self.data, order_id)
        narrative, degraded = self.narrate(
            {
                "order_id": order_id,
                "delivery_variance_hours": facts["delivery_variance_hours"],
                "late_handoff_seller_ids": facts["late_handoff_seller_ids"],
            }
        )
        return self._respond(
            msg,
            {"facts": facts, "narrative": narrative},
            latency_ms=elapsed_ms(start),
            llm_used=self.llm is not None,
            degraded=degraded,
        )
