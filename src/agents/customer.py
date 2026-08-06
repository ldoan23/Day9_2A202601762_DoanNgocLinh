import time

from src.agents.base import BaseAgent, elapsed_ms
from src.facts import customer_facts


class CustomerAgent(BaseAgent):
    name = "CustomerAgent"
    role_description = (
        "Extracts the customer unique identity and the customer's purchase history "
        "from the customers and orders tables."
    )
    allowed_tables = ["customers", "orders"]

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "request":
            raise ValueError("CustomerAgent only handles request messages")
        self.assert_scope("customers")
        self.assert_scope("orders")
        order_id = msg.payload["order_id"]
        facts = customer_facts(self.data, order_id)
        facts["order_status"] = self.data.orders_by_id[order_id]["order_status"]
        narrative, degraded = self.narrate(
            {
                "order_id": order_id,
                "customer_unique_id": facts["customer_unique_id"],
                "related_order_ids": facts["related_order_ids"],
                "order_status": facts["order_status"],
            }
        )
        return self._respond(
            msg,
            {"facts": facts, "narrative": narrative},
            latency_ms=elapsed_ms(start),
            llm_used=self.llm is not None,
            degraded=degraded,
        )
