import json
import time

from src.a2a.message import A2AMessage

ALL_TABLES = [
    "orders",
    "order_items",
    "order_payments",
    "customers",
    "products",
    "sellers",
    "product_category_name_translation",
]


class ScopedData:
    TABLE_ATTRS = {
        "orders": {"orders_by_id", "orders_dt_by_id"},
        "customers": {
            "customers_by_id",
            "customer_unique_by_customer",
            "orders_by_customer_unique",
        },
        "order_items": {"order_items_by_order", "item_shipping_dt"},
        "order_payments": {"order_payments_by_order"},
        "products": {"products_by_id"},
        "sellers": {"sellers_by_id"},
        "product_category_name_translation": {"product_category_name_translation"},
    }

    def __init__(self, data, allowed_tables):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_allowed", set(allowed_tables))

    def _table_for_attr(self, attr):
        for table, attrs in self.TABLE_ATTRS.items():
            if attr in attrs:
                return table
        return None

    def __getattr__(self, name):
        table = self._table_for_attr(name)
        if table is not None and table not in self._allowed:
            raise PermissionError(
                "scoped read denied: attribute %r belongs to table %r but allowed tables are %r"
                % (name, table, sorted(self._allowed) or "none")
            )
        return getattr(self._data, name)


class BaseAgent:
    name = "base"
    role_description = ""
    allowed_tables = []

    def __init__(self, bus, data, llm=None):
        self.bus = bus
        self.data = data
        self.llm = llm

    def assert_scope(self, table):
        if table not in self.allowed_tables:
            raise PermissionError(
                "agent %r attempted to access table %r but is only allowed %r"
                % (self.name, table, self.allowed_tables)
            )

    def narrate(self, facts_summary):
        if self.llm is None:
            return {"assessment": "", "flags": []}, True
        system = (
            "You are %s. %s "
            'Respond with ONLY a JSON object: {"assessment": "<one sentence summary>", '
            '"flags": ["<string>", ...]}.'
            % (self.name, self.role_description)
        )
        user = "Evidence summary (JSON):\n%s" % json.dumps(
            facts_summary, ensure_ascii=False
        )
        result = self.llm.chat_json(system, user)
        if result is None or not isinstance(result, dict):
            return {"assessment": "", "flags": []}, True
        assessment = result.get("assessment")
        if not isinstance(assessment, str):
            assessment = str(assessment) if assessment is not None else ""
        flags = result.get("flags")
        if not isinstance(flags, list):
            flags = []
        return {"assessment": assessment, "flags": [str(f) for f in flags]}, False

    def _respond(
        self,
        msg,
        payload,
        msg_type="response",
        latency_ms=0.0,
        llm_used=False,
        degraded=False,
    ):
        return A2AMessage(
            conversation_id=msg.conversation_id,
            sender=self.name,
            recipient=msg.sender,
            msg_type=msg_type,
            payload=payload,
            latency_ms=round(latency_ms, 1),
            llm_used=llm_used,
            degraded=degraded,
        )

    def handle(self, msg):
        raise NotImplementedError("%s does not implement handle" % self.name)


def elapsed_ms(start):
    return (time.time() - start) * 1000.0
