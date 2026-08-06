import glob
import json
import os

from src.builder import build_payload
from src.data_layer import OlistData
from src.validator import validate

TABLE_ORDER = [
    "late_delivery_seller",
    "late_delivery_logistics",
    "unsupported_late_claim",
    "canceled_order_paid",
    "valid_split_payment",
    "unavailable_order_paid",
]


def main():
    data = OlistData("data")
    os.makedirs("output", exist_ok=True)

    counts = {}
    errors = []
    input_files = sorted(glob.glob(os.path.join("input", "EC_*.json")))

    for path in input_files:
        with open(path, encoding="utf-8") as f:
            request = json.load(f)
        case_id = request["case_id"]
        order_id = request["customer_request"]["claimed_order_id"]
        try:
            payload = build_payload(data, order_id, case_id)
            validate(payload)
            out_path = os.path.join("output", os.path.basename(path))
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            primary = payload["case_assessment"]["primary_issue"]
            counts[primary] = counts.get(primary, 0) + 1
        except Exception as exc:
            errors.append((case_id, str(exc)))

    print("=== PRIMARY ISSUE COUNTS ===")
    for key in TABLE_ORDER:
        print("  %-24s %d" % (key, counts.get(key, 0)))
    total = sum(counts.values())
    print("  %-24s %d" % ("TOTAL", total))

    if errors:
        print("=== ERROR CASES ===")
        for case_id, message in errors:
            print("  %s: %s" % (case_id, message))
    else:
        print("=== NO ERROR CASES ===")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
