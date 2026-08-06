import json
import glob

# So sanh chi tiet voi mau README
# Mau README: case_id=EC_001 (san pham mau), kiem tra format cac gia tri

print("=== CHI TIET SO SANH VOI MAU README ===\n")

# Doc 3 file mau
for fname in ['output/EC_001.json', 'output/EC_002.json', 'output/EC_003.json']:
    d = json.load(open(fname, encoding='utf-8'))
    print(f"--- {fname} ---")
    print(f"  case_id            : {d['case_id']}")
    ca = d['case_assessment']
    print(f"  primary_issue      : {ca['primary_issue']}")
    print(f"  secondary_issues   : {ca['secondary_issues']}")
    print(f"  case_status        : {ca['case_status']}")
    print(f"  confidence         : {ca['confidence']}")
    ae = d['affected_entities']
    print(f"  order_ids          : {ae['order_ids']}")
    print(f"  item_ids           : {ae['item_ids']}")
    print(f"  seller_ids         : {ae['seller_ids']}")
    print(f"  payment_ids        : {ae['payment_ids']}")
    cc = d['customer_context']
    print(f"  customer_unique_id : {cc['customer_unique_id']}")
    print(f"  related_order_ids  : {cc['related_order_ids']}")
    pc = d['product_context']
    print(f"  product_ids        : {pc['product_ids'][:2]}...")
    print(f"  category_names     : {pc['category_names']}")
    da = d['delivery_analysis']
    print(f"  delivered_at       : {da['delivered_at']}")
    print(f"  estimated_at       : {da['estimated_delivery_at']}")
    print(f"  carrier_handoff_at : {da['carrier_handoff_at']}")
    print(f"  delivery_variance  : {da['delivery_variance_hours']}")
    print(f"  seller_handoffs    : {len(da['seller_handoff_analysis'])} entries")
    if da['seller_handoff_analysis']:
        h = da['seller_handoff_analysis'][0]
        print(f"    first handoff    : seller_id={h['seller_id'][:8]}..., variance={h['handoff_variance_hours']}, late={h['late_handoff']}")
    print(f"  late_seller_ids    : {da['late_handoff_seller_ids']}")
    pr = d['payment_reconciliation']
    print(f"  currency           : {pr['currency']}")
    print(f"  item_total_brl     : {pr['item_total_brl']}")
    print(f"  freight_total_brl  : {pr['freight_total_brl']}")
    print(f"  expected_total_brl : {pr['expected_total_brl']}")
    print(f"  payment_total_brl  : {pr['payment_total_brl']}")
    print(f"  difference_brl     : {pr['difference_brl']}")
    print(f"  reconciled         : {pr['reconciled']}")
    print(f"  payment_types      : {pr['payment_types']}")
    rca = d['root_cause_analysis']
    print(f"  ranked_causes      : {rca['ranked_causes']}")
    print(f"  responsible_parties: {rca['responsible_parties']}")
    print(f"  evidence_ids       : {d['evidence_ids']}")
    fr = d['financial_resolution']
    print(f"  financial currency : {fr['currency']}")
    print(f"  recommended_refund : {fr['recommended_refund_brl']}")
    print(f"  resolution_actions : {d['resolution_actions']}")
    print()

# Kiem tra cac truong hop dac biet
print("=== KIEM TRA TRUONG HOP DAC BIET ===\n")

# 1. Null handling: order chua duoc giao (expected_total, difference, reconciled = null)
null_cases = []
for f in sorted(glob.glob('output/EC_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    pr = d['payment_reconciliation']
    if pr['item_total_brl'] is None:
        null_cases.append((d['case_id'], pr))
if null_cases:
    print(f"Cases with null item totals (no items): {len(null_cases)}")
    cid, pr = null_cases[0]
    print(f"  {cid}: item_total={pr['item_total_brl']}, expected={pr['expected_total_brl']}, diff={pr['difference_brl']}, reconciled={pr['reconciled']}")
else:
    print("No cases with null item totals (all have items)")

# 2. Cases with None delivery_variance (not yet delivered)
none_variance = []
for f in sorted(glob.glob('output/EC_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    if d['delivery_analysis']['delivery_variance_hours'] is None:
        none_variance.append(d['case_id'])
print(f"\nCases with null delivery_variance: {none_variance}")

# 3. Timestamp format check: YYYY-MM-DD HH:MM:SS or null
import re
ts_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
bad_ts = []
for f in sorted(glob.glob('output/EC_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    da = d['delivery_analysis']
    for field in ['delivered_at', 'estimated_delivery_at', 'carrier_handoff_at']:
        val = da.get(field)
        if val is not None and not ts_pattern.match(str(val)):
            bad_ts.append((d['case_id'], field, val))
if bad_ts:
    print(f"\nBAD timestamp format ({len(bad_ts)}):")
    for c, f, v in bad_ts[:5]:
        print(f"  {c}.{f} = {repr(v)}")
else:
    print("\nAll timestamps OK (YYYY-MM-DD HH:MM:SS or null)")

# 4. verify_payment_allocation NOT in actions when primary = valid_split_payment
vpa_error = []
for f in sorted(glob.glob('output/EC_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    if d['case_assessment']['primary_issue'] == 'valid_split_payment':
        if 'verify_payment_allocation' in d['resolution_actions']:
            vpa_error.append(d['case_id'])
if vpa_error:
    print(f"\nERROR: verify_payment_allocation present when valid_split_payment: {vpa_error}")
else:
    print("verify_payment_allocation rule for valid_split_payment: OK")

# 5. Stats per primary_issue
from collections import Counter
counts = Counter()
for f in sorted(glob.glob('output/EC_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    counts[d['case_assessment']['primary_issue']] += 1
print("\nPrimary issue distribution:")
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k:30s} {v}")
