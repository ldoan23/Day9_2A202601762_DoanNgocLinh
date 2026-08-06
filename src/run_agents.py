import glob
import json
import os
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from src import llm
from src.a2a.bus import MessageBus, TraceSink
from src.agents import AGENT_NAMES, ALL_TABLES
from src.agents.base import ScopedData
from src.agents.coordinator import CoordinatorAgent
from src.agents.customer import CustomerAgent
from src.agents.delivery import DeliveryAgent
from src.agents.order_product import OrderProductAgent
from src.agents.payment import PaymentAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent
from src.data_layer import OlistData

MAX_WORKERS = 3
TRACE_PATHS = ["logging/trace.jsonl", "trace.jsonl"]
METADATA_PATHS = ["logging/metadata.json", "metadata.json"]


def build_agents(bus, data, llm_client):
    agents = [
        CoordinatorAgent(bus, ScopedData(data, []), llm_client),
        CustomerAgent(bus, ScopedData(data, ["customers", "orders"]), llm_client),
        OrderProductAgent(
            bus, ScopedData(data, ["order_items", "products", "sellers"]), llm_client
        ),
        PaymentAgent(
            bus, ScopedData(data, ["order_payments", "order_items"]), llm_client
        ),
        DeliveryAgent(bus, ScopedData(data, ["orders", "order_items"]), llm_client),
        PolicyAgent(bus, ScopedData(data, []), llm_client),
        VerifierAgent(bus, ScopedData(data, list(ALL_TABLES)), llm_client),
    ]
    for agent in agents:
        bus.register(agent)
    return agents


def main():
    started_at = datetime.now(timezone.utc).isoformat()
    start_wall = time.time()
    os.makedirs("output", exist_ok=True)

    data = OlistData("data")
    trace_sink = TraceSink(TRACE_PATHS)
    bus = MessageBus(trace_sink=trace_sink)
    agents = build_agents(bus, data, llm)
    coordinator = next(a for a in agents if a.name == "CoordinatorAgent")

    input_files = sorted(glob.glob(os.path.join("input", "EC_*.json")))
    requests = []
    for path in input_files:
        with open(path, encoding="utf-8") as f:
            requests.append(json.load(f))

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {
            pool.submit(coordinator.process_case, req, "output"): req for req in requests
        }
        for future in as_completed(future_map):
            req = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append((req["case_id"], str(exc)))

    duration_seconds = round(time.time() - start_wall, 1)
    finished_at = datetime.now(timezone.utc).isoformat()
    llm_stats = llm.stats()
    degraded_cases = sum(1 for r in results if r["degraded"])
    mismatch_total = sum(r["mismatch_count"] for r in results)
    trace_lines = _count_lines(TRACE_PATHS[0])

    trace_sink.close()

    metadata = {
        "model": llm.MODEL_NAME,
        "parameter_size": llm.MODEL_PARAM_SIZE,
        "provider": llm.PROVIDER,
        "framework": "custom A2A message bus (Python stdlib + pandas)",
        "runtime": {
            "python": sys.version.split()[0],
            "os": platform.platform(),
        },
        "agents": list(AGENT_NAMES),
        "run": {
            "cases": len(requests),
            "llm_calls": llm_stats["llm_calls"],
            "degraded_cases": degraded_cases,
            "duration_seconds": duration_seconds,
            "started_at": started_at,
            "finished_at": finished_at,
        },
    }
    for path in METADATA_PATHS:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("=== RUN AGENTS SUMMARY ===")
    print("  cases_processed:      %d" % len(results))
    print("  error_cases:          %d" % len(errors))
    print("  llm_calls:            %d" % llm_stats["llm_calls"])
    print("  degraded_cases:       %d" % degraded_cases)
    print("  verifier_mismatches:  %d" % mismatch_total)
    print("  trace_lines:          %d" % trace_lines)
    print("  duration_seconds:     %.1f" % duration_seconds)
    if errors:
        print("=== ERROR CASES ===")
        for case_id, message in errors:
            print("  %s: %s" % (case_id, message))
    else:
        print("=== NO ERROR CASES ===")
    return 1 if errors else 0


def _count_lines(path):
    count = 0
    with open(path, encoding="utf-8") as f:
        for _line in f:
            count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
