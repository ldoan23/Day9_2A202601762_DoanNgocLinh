import time

from src.agents.base import BaseAgent, elapsed_ms
from src.facts import order_product_facts


class OrderProductAgent(BaseAgent):
    name = "OrderProductAgent"
    role_description = (
        "Extracts items, sellers, products and category names for the claimed order "
        "from the order_items, products and sellers tables."
    )
    allowed_tables = ["order_items", "products", "sellers"]

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "request":
            raise ValueError("OrderProductAgent only handles request messages")
        self.assert_scope("order_items")
        self.assert_scope("products")
        self.assert_scope("sellers")
        order_id = msg.payload["order_id"]
        facts = order_product_facts(self.data, order_id)
        narrative, degraded = self.narrate(
            {
                "order_id": order_id,
                "item_ids": facts["item_ids"],
                "seller_ids": facts["seller_ids"],
                "n_items": facts["n_items"],
                "n_sellers": facts["n_sellers"],
                "n_categories": facts["n_categories"],
            }
        )
        return self._respond(
            msg,
            {"facts": facts, "narrative": narrative},
            latency_ms=elapsed_ms(start),
            llm_used=self.llm is not None,
            degraded=degraded,
        )
