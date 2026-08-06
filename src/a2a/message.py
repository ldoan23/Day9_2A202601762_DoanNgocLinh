import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

VALID_MSG_TYPES = {"request", "response", "handoff", "verification", "verdict"}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class A2AMessage:
    conversation_id: str
    sender: str
    recipient: str
    msg_type: str
    payload: dict = field(default_factory=dict)
    msg_id: str = field(default_factory=lambda: str(uuid4()))
    seq: int = field(default=None)
    timestamp: str = field(default_factory=utc_now_iso)
    latency_ms: float = 0.0
    llm_used: bool = False
    degraded: bool = False

    def __post_init__(self):
        if self.msg_type not in VALID_MSG_TYPES:
            raise ValueError("invalid msg_type: %r" % (self.msg_type,))

    def to_json_line(self):
        return json.dumps(asdict(self), ensure_ascii=False)
