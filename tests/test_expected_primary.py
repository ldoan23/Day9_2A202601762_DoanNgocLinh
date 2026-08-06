import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.builder import build_payload
from src.data_layer import OlistData
from src.validator import validate

EXPECTED_PRIMARY = {
    "EC_004": "canceled_order_paid",
    "EC_009": "canceled_order_paid",
    "EC_011": "canceled_order_paid",
    "EC_024": "canceled_order_paid",
    "EC_026": "canceled_order_paid",
    "EC_028": "canceled_order_paid",
    "EC_030": "canceled_order_paid",
    "EC_047": "canceled_order_paid",
    "EC_012": "unavailable_order_paid",
    "EC_031": "unavailable_order_paid",
    "EC_033": "unavailable_order_paid",
    "EC_034": "unavailable_order_paid",
    "EC_035": "unavailable_order_paid",
    "EC_043": "unavailable_order_paid",
    "EC_002": "late_delivery_seller",
    "EC_006": "late_delivery_seller",
    "EC_013": "late_delivery_seller",
    "EC_019": "late_delivery_seller",
    "EC_020": "late_delivery_seller",
    "EC_032": "late_delivery_seller",
    "EC_039": "late_delivery_seller",
    "EC_042": "late_delivery_seller",
    "EC_046": "late_delivery_seller",
    "EC_048": "late_delivery_seller",
    "EC_003": "late_delivery_logistics",
    "EC_005": "late_delivery_logistics",
    "EC_007": "late_delivery_logistics",
    "EC_014": "late_delivery_logistics",
    "EC_016": "late_delivery_logistics",
    "EC_017": "late_delivery_logistics",
    "EC_023": "late_delivery_logistics",
    "EC_027": "late_delivery_logistics",
    "EC_037": "late_delivery_logistics",
    "EC_040": "late_delivery_logistics",
    "EC_008": "valid_split_payment",
    "EC_010": "valid_split_payment",
    "EC_015": "valid_split_payment",
    "EC_022": "valid_split_payment",
    "EC_029": "valid_split_payment",
    "EC_036": "valid_split_payment",
    "EC_041": "valid_split_payment",
    "EC_049": "valid_split_payment",
    "EC_001": "unsupported_late_claim",
    "EC_018": "unsupported_late_claim",
    "EC_021": "unsupported_late_claim",
    "EC_025": "unsupported_late_claim",
    "EC_038": "unsupported_late_claim",
    "EC_044": "unsupported_late_claim",
    "EC_045": "unsupported_late_claim",
    "EC_050": "unsupported_late_claim",
}

NO_ITEM_CASES = {"EC_012", "EC_031", "EC_033", "EC_034", "EC_035", "EC_043"}

EC002_EXPECTED = {
    "delivery_variance_hours": 87.39,
    "item_total_brl": 194.0,
    "freight_total_brl": 18.27,
    "expected_total_brl": 212.27,
    "payment_total_brl": 212.27,
    "difference_brl": 0.0,
}

EXPECTED_RELATED_ORDER_IDS = {
    "EC_001": ["65bbd0719855fe808bb19f62dfa9f42c"],
    "EC_003": ["9cf677fc6e42f8256b310109fe5f2333"],
    "EC_006": ["af7de7cc75eb2f7d0eff2e383eccf083"],
    "EC_012": ["dee008fbad3f3868874dd10ab5977b88"],
    "EC_014": ["c53b15af645d91a057ddba9d0e1f21c7"],
    "EC_017": ["fdaf98feac227eb978d8f33f36e0231d"],
    "EC_019": ["3ce16e50c1842ad30631811796a31afc", "c7c28a159a907d1d0ff580856daffa72"],
    "EC_023": ["1534abac962760cbb058568f7dffc105"],
    "EC_027": ["9165d656c399c6eac7a6a00dd6e02e7f"],
    "EC_031": ["b6b73b9c0cab8ac7a2b02a49623d4cfe"],
    "EC_038": ["44d14514a06127f72cd96745ed0eed21"],
    "EC_039": ["6af5d028aa14031c4afa3b5dd2d427ab"],
    "EC_042": ["765d8e5f6a9d496c895d21bb271ff1e8"],
    "EC_043": ["ceb533871105f7cda81fafc19e1ee38e"],
    "EC_048": ["ed7cabc96de8c36774b894e98aa73dc2"],
}


def run():
    data = OlistData("data")
    checked = 0
    related_nonempty = 0
    repeat_customer_cases = 0
    for case_id, expected in EXPECTED_PRIMARY.items():
        with open(os.path.join("input", case_id + ".json"), encoding="utf-8") as f:
            request = json.load(f)
        order_id = request["customer_request"]["claimed_order_id"]
        payload = build_payload(data, order_id, case_id)
        validate(payload)

        actual = payload["case_assessment"]["primary_issue"]
        assert actual == expected, "primary mismatch %s: got %s expected %s" % (
            case_id,
            actual,
            expected,
        )

        related = payload["customer_context"]["related_order_ids"]
        if related:
            related_nonempty += 1
        if "repeat_customer" in payload["case_assessment"]["secondary_issues"]:
            repeat_customer_cases += 1

        if case_id in EXPECTED_RELATED_ORDER_IDS:
            assert related == EXPECTED_RELATED_ORDER_IDS[case_id], (
                "related_order_ids mismatch %s: got %r expected %r"
                % (case_id, related, EXPECTED_RELATED_ORDER_IDS[case_id])
            )

        if case_id == "EC_002":
            delivery = payload["delivery_analysis"]
            reconciliation = payload["payment_reconciliation"]
            checks = {
                "delivery_variance_hours": delivery["delivery_variance_hours"],
                "item_total_brl": reconciliation["item_total_brl"],
                "freight_total_brl": reconciliation["freight_total_brl"],
                "expected_total_brl": reconciliation["expected_total_brl"],
                "payment_total_brl": reconciliation["payment_total_brl"],
                "difference_brl": reconciliation["difference_brl"],
            }
            for field, value in EC002_EXPECTED.items():
                assert checks[field] == value, "EC_002 %s: got %r expected %r" % (
                    field,
                    checks[field],
                    value,
                )

        if case_id in NO_ITEM_CASES:
            reconciliation = payload["payment_reconciliation"]
            assert reconciliation["expected_total_brl"] is None
            assert reconciliation["difference_brl"] is None
            assert reconciliation["reconciled"] is None
            assert payload["affected_entities"]["item_ids"] == []
            assert payload["affected_entities"]["seller_ids"] == []
            assert payload["product_context"]["product_ids"] == []
            assert payload["product_context"]["category_names"] == []
            assert payload["delivery_analysis"]["seller_handoff_analysis"] == []
            assert payload["delivery_analysis"]["late_handoff_seller_ids"] == []
            assert isinstance(reconciliation["payment_total_brl"], (int, float))
            assert reconciliation["payment_total_brl"] > 0

        checked += 1

    assert checked == 50, "expected 50 cases, checked %d" % checked
    assert related_nonempty == 26, "expected 26 cases with related_order_ids, got %d" % related_nonempty
    assert repeat_customer_cases == 26, (
        "expected 26 cases with repeat_customer secondary, got %d" % repeat_customer_cases
    )
    print("ALL TESTS PASSED (%d cases, %d related, %d repeat_customer)" % (
        checked,
        related_nonempty,
        repeat_customer_cases,
    ))


if __name__ == "__main__":
    run()
