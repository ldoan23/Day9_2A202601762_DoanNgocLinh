import json
import glob

readme_top = ['case_id','case_assessment','affected_entities','customer_context',
              'product_context','delivery_analysis','payment_reconciliation',
              'root_cause_analysis','evidence_ids','financial_resolution','resolution_actions']
readme_ca = ['primary_issue','secondary_issues','case_status','confidence']
readme_ae = ['order_ids','item_ids','seller_ids','payment_ids']
readme_cc = ['customer_unique_id','related_order_ids']
readme_pc = ['product_ids','category_names']
readme_da = ['delivered_at','estimated_delivery_at','carrier_handoff_at',
             'delivery_variance_hours','seller_handoff_analysis','late_handoff_seller_ids']
readme_handoff = ['seller_id','shipping_limit_at','handoff_variance_hours','late_handoff']
readme_pr = ['currency','item_total_brl','freight_total_brl','expected_total_brl',
             'payment_total_brl','difference_brl','reconciled','payment_types']
readme_rca = ['ranked_causes','responsible_parties']
readme_fr = ['currency','recommended_refund_brl']

VALID_PRIMARY = {'canceled_order_paid','unavailable_order_paid','late_delivery_seller',
                 'late_delivery_logistics','valid_split_payment','unsupported_late_claim'}
VALID_SECONDARY = {'multi_item_order','multi_seller_order','split_payment',
                   'repeat_customer','multiple_categories'}
VALID_ACTIONS = {'issue_full_refund','refund_freight','explain_valid_split_payment',
                 'reject_late_refund','review_seller_handoff','review_carrier_delay',
                 'verify_refund_completion','coordinate_multi_seller_case','verify_payment_allocation'}
VALID_ROOT_CAUSE = {'SELLER_HANDOFF_AFTER_LIMIT','CARRIER_DELIVERED_AFTER_ESTIMATE',
                    'ORDER_CANCELED_AFTER_PAYMENT','ORDER_UNAVAILABLE_AFTER_PAYMENT',
                    'MULTIPLE_PAYMENTS_RECONCILED','DELIVERY_WITHIN_ESTIMATE'}

import re
EVIDENCE_RE = re.compile(r'^(order:[^:]+|item:[^:]+:\d+|payment:[^:]+:\d+|seller:[^:]+|policy:[A-Z_]+)$')

errors = []
warnings = []
files = sorted(glob.glob('output/EC_*.json'))

for fpath in files:
    fname = fpath.split('/')[-1].split('\\')[-1]
    d = json.load(open(fpath, encoding='utf-8'))

    # 1. Top-level key presence & order
    top_keys = list(d.keys())
    for k in readme_top:
        if k not in top_keys:
            errors.append(f'{fname}: MISSING top-level key [{k}]')
    extra = [k for k in top_keys if k not in readme_top]
    if extra:
        warnings.append(f'{fname}: extra top-level keys {extra}')
    if top_keys != readme_top:
        warnings.append(f'{fname}: key order mismatch')

    # 2. case_assessment
    ca = d.get('case_assessment', {})
    for k in readme_ca:
        if k not in ca:
            errors.append(f'{fname}: case_assessment missing [{k}]')
    if ca.get('primary_issue') not in VALID_PRIMARY:
        errors.append(f'{fname}: invalid primary_issue [{ca.get("primary_issue")}]')
    for si in ca.get('secondary_issues', []):
        if si not in VALID_SECONDARY:
            errors.append(f'{fname}: invalid secondary_issue [{si}]')
    if ca.get('case_status') not in {'action_required','no_action'}:
        errors.append(f'{fname}: invalid case_status [{ca.get("case_status")}]')
    conf = ca.get('confidence')
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        errors.append(f'{fname}: confidence out of range [{conf}]')

    # 3. affected_entities
    ae = d.get('affected_entities', {})
    for k in readme_ae:
        if k not in ae:
            errors.append(f'{fname}: affected_entities missing [{k}]')
    if len(ae.get('order_ids', [])) > 5:   errors.append(f'{fname}: order_ids > 5')
    if len(ae.get('item_ids', [])) > 5:    errors.append(f'{fname}: item_ids > 5')
    if len(ae.get('seller_ids', [])) > 3:  errors.append(f'{fname}: seller_ids > 3')
    if len(ae.get('payment_ids', [])) > 5: errors.append(f'{fname}: payment_ids > 5')

    # 4. customer_context
    cc = d.get('customer_context', {})
    for k in readme_cc:
        if k not in cc:
            errors.append(f'{fname}: customer_context missing [{k}]')
    if len(cc.get('related_order_ids', [])) > 5:
        errors.append(f'{fname}: related_order_ids > 5')

    # 5. product_context
    pc = d.get('product_context', {})
    for k in readme_pc:
        if k not in pc:
            errors.append(f'{fname}: product_context missing [{k}]')
    if len(pc.get('product_ids', [])) > 5:   errors.append(f'{fname}: product_ids > 5')
    if len(pc.get('category_names', [])) > 5: errors.append(f'{fname}: category_names > 5')

    # 6. delivery_analysis
    da = d.get('delivery_analysis', {})
    for k in readme_da:
        if k not in da:
            errors.append(f'{fname}: delivery_analysis missing [{k}]')
    for entry in da.get('seller_handoff_analysis', []):
        for k in readme_handoff:
            if k not in entry:
                errors.append(f'{fname}: seller_handoff entry missing [{k}]')

    # 7. payment_reconciliation
    pr = d.get('payment_reconciliation', {})
    for k in readme_pr:
        if k not in pr:
            errors.append(f'{fname}: payment_reconciliation missing [{k}]')
    if pr.get('currency') != 'BRL':
        errors.append(f'{fname}: payment.currency != BRL')

    # 8. root_cause_analysis
    rca = d.get('root_cause_analysis', {})
    for k in readme_rca:
        if k not in rca:
            errors.append(f'{fname}: root_cause_analysis missing [{k}]')
    if len(rca.get('ranked_causes', [])) > 3:   errors.append(f'{fname}: ranked_causes > 3')
    if len(rca.get('responsible_parties', [])) > 3: errors.append(f'{fname}: responsible_parties > 3')
    for cause in rca.get('ranked_causes', []):
        if cause.get('cause_code') not in VALID_ROOT_CAUSE:
            errors.append(f'{fname}: invalid cause_code [{cause.get("cause_code")}]')
        if 'rank' not in cause:
            errors.append(f'{fname}: ranked_cause missing [rank]')

    # 9. evidence_ids
    evids = d.get('evidence_ids', [])
    if len(evids) > 20:
        errors.append(f'{fname}: evidence_ids > 20')
    for ev in evids:
        if not EVIDENCE_RE.match(ev):
            errors.append(f'{fname}: bad evidence_id format [{ev}]')

    # 10. financial_resolution
    fr = d.get('financial_resolution', {})
    for k in readme_fr:
        if k not in fr:
            errors.append(f'{fname}: financial_resolution missing [{k}]')
    if fr.get('currency') != 'BRL':
        errors.append(f'{fname}: financial.currency != BRL')

    # 11. resolution_actions
    acts = d.get('resolution_actions', [])
    if len(acts) > 5:
        errors.append(f'{fname}: resolution_actions > 5')
    for act in acts:
        if act not in VALID_ACTIONS:
            errors.append(f'{fname}: invalid action [{act}]')

total = len(files)
print(f'=== Schema Check: {total} files ===')
if errors:
    print(f'ERRORS ({len(errors)}):')
    for e in errors:
        print(' ', e)
else:
    print('PASS: No schema errors across all', total, 'files')

if warnings:
    print(f'WARNINGS ({len(warnings)}):')
    for w in warnings[:5]:
        print(' ', w)
    if len(warnings) > 5:
        print(f'  ... and {len(warnings)-5} more')
else:
    print('No warnings')
