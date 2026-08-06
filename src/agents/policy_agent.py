import time

from src.agents.base import BaseAgent, elapsed_ms
from src.policy import apply_policy


class PolicyAgent(BaseAgent):
    name = "PolicyAgent"
    role_description = (
        "Applies the EC_POLICY_V2 decision table to the handoff facts and explains "
        "why the primary issue was selected. This agent never reads raw CSV tables."
    )
    allowed_tables = []

    def handle(self, msg):
        start = time.time()
        if msg.msg_type != "handoff":
            raise ValueError("PolicyAgent only handles handoff messages")
        facts = msg.payload["facts"]
        policy = apply_policy(facts)
        narrative, degraded = self.narrate(
            {
                "order_id": facts.get("order_id"),
                "order_status": facts.get("order_status"),
                "primary_issue": policy["primary_issue"],
                "secondary_issues": policy["secondary_issues"],
                "recommended_refund_brl": policy["recommended_refund_brl"],
            }
        )
        return self._respond(
            msg,
            {"policy": policy, "narrative": narrative},
            latency_ms=elapsed_ms(start),
            llm_used=self.llm is not None,
            degraded=degraded,
        )
