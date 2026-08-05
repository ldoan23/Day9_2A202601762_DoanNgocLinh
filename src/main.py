"""Entry point: runs all EC_001..EC_050 cases through the coordinator
pipeline, writes one JSON per case to output/, and overwrites trace.jsonl
at the repo root with the full run's trace (not appended across runs, per
README section 8)."""

import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.agents.coordinator_agent import empty_case_result
from src.agents.coordinator_agent import run as run_case
from src.agents.verifier_agent import verify
from src.data_loader import get_case_data

INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TRACE_PATH = os.path.join(PROJECT_ROOT, "trace.jsonl")


def main():
    input_files = sorted(f for f in os.listdir(INPUT_DIR) if f.startswith("EC_") and f.endswith(".json"))
    all_trace_entries = []
    summary = []

    for filename in input_files:
        case_id = filename.replace(".json", "")
        input_path = os.path.join(INPUT_DIR, filename)
        with open(input_path, "r", encoding="utf-8") as f:
            case_input = json.load(f)

        start = time.time()
        try:
            result, trace_entries = run_case(case_input)
            data = get_case_data(case_input["customer_request"]["claimed_order_id"])
            problems = verify(result, data)
        except Exception as exc:
            # Never skip writing a file for this case - README requires
            # exactly 50 output files, so a pipeline failure still needs a
            # (low-confidence, no_action) placeholder rather than a missing
            # file, which would hard-gate the whole submission.
            print(f"[{case_id}] FAILED: {exc} - writing placeholder output")
            result = empty_case_result(case_id)
            trace_entries = [{"case_id": case_id, "agent": "coordinator", "error": str(exc)}]
            problems = ["pipeline exception - placeholder written, needs manual review"]

        elapsed = time.time() - start

        if problems:
            print(f"[{case_id}] VERIFIER FLAGGED {len(problems)} problem(s): {problems}")
            for p in problems:
                all_trace_entries.append({"case_id": case_id, "agent": "verifier_agent", "problem": p})
        else:
            print(f"[{case_id}] OK ({elapsed:.1f}s) primary_issue={result['case_assessment']['primary_issue']}")

        all_trace_entries.extend(trace_entries)
        summary.append((case_id, "OK" if not problems else "FLAGGED", result["case_assessment"]["primary_issue"]))

        output_path = os.path.join(OUTPUT_DIR, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    with open(TRACE_PATH, "w", encoding="utf-8") as f:
        for entry in all_trace_entries:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    ok_count = sum(1 for _, status, _ in summary if status == "OK")
    print(f"\nDone: {ok_count}/{len(summary)} cases OK. Trace written to {TRACE_PATH}")


if __name__ == "__main__":
    main()
