import json
import os

from src.a2a.message import A2AMessage
from src.agents.base import BaseAgent
from src.builder import _build_evidence_ids
from src.validator import validate

WORKER_AGENTS = ("CustomerAgent", "OrderProductAgent", "PaymentAgent", "DeliveryAgent")


def _assemble_payload(facts, policy, order_id, case_id):
    evidence_ids = _build_evidence_ids(
        order_id,
        facts["item_ids"],
        facts["payment_ids"],
        policy["responsible_parties"],
        policy["ranked_causes"][0]["cause_code"],
    )
    return {
        "case_id": case_id,
        "case_assessment": {
            "primary_issue": policy["primary_issue"],
            "secondary_issues": policy["secondary_issues"],
            "case_status": policy["case_status"],
            "confidence": policy["confidence"],
        },
        "affected_entities": {
            "order_ids": [order_id],
            "item_ids": facts["item_ids"],
            "seller_ids": facts["seller_ids"],
            "payment_ids": facts["payment_ids"],
        },
        "customer_context": {
            "customer_unique_id": facts["customer_unique_id"],
            "related_order_ids": facts["related_order_ids"],
        },
        "product_context": {
            "product_ids": facts["product_ids"],
            "category_names": facts["category_names"],
        },
        "delivery_analysis": {
            "delivered_at": facts["delivered_at"],
            "estimated_delivery_at": facts["estimated_delivery_at"],
            "carrier_handoff_at": facts["carrier_handoff_at"],
            "delivery_variance_hours": facts["delivery_variance_hours"],
            "seller_handoff_analysis": facts["seller_handoff_analysis"],
            "late_handoff_seller_ids": facts["late_handoff_seller_ids"],
        },
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": facts["item_total_brl"],
            "freight_total_brl": facts["freight_total_brl"],
            "expected_total_brl": facts["expected_total_brl"],
            "payment_total_brl": facts["payment_total_brl"],
            "difference_brl": facts["difference_brl"],
            "reconciled": facts["reconciled"],
            "payment_types": facts["payment_types"],
        },
        "root_cause_analysis": {
            "ranked_causes": policy["ranked_causes"],
            "responsible_parties": policy["responsible_parties"],
        },
        "evidence_ids": evidence_ids,
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": policy["recommended_refund_brl"],
        },
        "resolution_actions": policy["resolution_actions"],
    }


class CoordinatorAgent(BaseAgent):
    name = "CoordinatorAgent"
    role_description = (
        "Orchestrates the full dispute investigation: dispatches extraction requests, "
        "handoffs merged facts to policy, verifies the assembled payload and writes the output."
    )
    allowed_tables = []

    def handle(self, msg):
        raise NotImplementedError("CoordinatorAgent drives cases via process_case")

    def process_case(self, request, output_dir):
        case_id = request["case_id"]
        order_id = request["customer_request"]["claimed_order_id"]
        degraded = False

        def send(recipient, msg_type, payload):
            return self.bus.send(
                A2AMessage(
                    conversation_id=case_id,
                    sender=self.name,
                    recipient=recipient,
                    msg_type=msg_type,
                    payload=payload,
                )
            )

        facts = {}
        for recipient in WORKER_AGENTS:
            response = send(recipient, "request", {"order_id": order_id})
            facts.update(response.payload["facts"])
            degraded = degraded or response.degraded

        facts["order_id"] = order_id

        policy_response = send("PolicyAgent", "handoff", {"facts": facts})
        policy = policy_response.payload["policy"]
        degraded = degraded or policy_response.degraded

        payload = _assemble_payload(facts, policy, order_id, case_id)

        verdict_message = send(
            "VerifierAgent", "verification", {"order_id": order_id, "payload": payload}
        )
        verdict = verdict_message.payload["verdict"]
        mismatch_count = len(verdict["mismatches"])
        if not verdict["agree"]:
            recomputed = verdict_message.payload.get("recomputed", {})
            mismatch_fields = {m["field"] for m in verdict["mismatches"]}
            if "payment_total_brl" in mismatch_fields:
                payload["payment_reconciliation"]["payment_total_brl"] = recomputed[
                    "payment_total_brl"
                ]
            if "delivery_variance_hours" in mismatch_fields:
                payload["delivery_analysis"]["delivery_variance_hours"] = recomputed[
                    "delivery_variance_hours"
                ]

        validate(payload)

        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, case_id + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return {
            "case_id": case_id,
            "degraded": degraded,
            "mismatch_count": mismatch_count,
        }
