# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                    |
| --------------- | ---------------------------- |
| Họ và tên       | Đoàn Ngọc Linh               |
| MSSV            | 2A202601762    |
| Khóa/Lớp        | K4                            |
| Vai trò chính   | Data Pipeline & Policy Agent Engineer (data join/tính toán deterministic, thiết kế Policy Agent LLM, Verifier) |
| Ngày hoàn thành | 2026-08-05                   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data loading & join | `src/data_loader.py` (`get_case_data`) | `claimed_order_id` | dict gồm order/customer/items/payments/sellers/products/related_order_ids | Hoàn thành |
| Tính toán deterministic | `src/calculations.py` (`compute_delivery_variance`, `compute_seller_handoff`, `compute_payment_reconciliation`) | dữ liệu đã join | `delivery_variance_hours`, `seller_handoff_analysis`, `payment_reconciliation` | Hoàn thành |
| Policy Agent (LLM decision) | `src/agents/policy_agent.py` (`classify_primary`, `classify_secondary`, `classify_bonus_actions`, `classify_ambiguity`) | số liệu đã tính + số đếm thô | `primary_issue`, `secondary_issues`, `responsible_parties`, `refund`, `resolution_actions`, `confidence` | Hoàn thành |
| Evidence & context builder | `src/evidence_builder.py` | dữ liệu gốc + quyết định Policy Agent | `affected_entities`, `customer_context`, `product_context`, `evidence_ids` | Hoàn thành |
| Coordinator | `src/agents/coordinator_agent.py` (`run`) | toàn bộ agent trên | object case hoàn chỉnh + trace | Hoàn thành |
| Verifier | `src/agents/verifier_agent.py` (`verify`) | object case + dữ liệu gốc | danh sách vấn đề (schema/evidence/taxonomy/refund) | Hoàn thành |
| Chạy 50 case & đóng gói | `src/main.py`, `output_submission.zip` | `input/EC_001..050.json` | `output/EC_001..050.json`, `trace.jsonl` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Không có | — | — |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây pipeline multi-agent 7 thành phần, LLM tự quyết định phân loại (không hard-code) | `src/agents/*.py`, `src/policy_engine.py` | 50/50 file `output/EC_XXX.json` hợp lệ | `python src/main.py` |
| Đối chiếu QA nội bộ với công thức chuẩn EC_POLICY_V2 | script audit riêng (không nộp bài) | 48/50 case khớp công thức (96%) | so sánh `output/*.json` với công thức tính tay |
| Kiểm chứng schema/evidence trước khi ghi file | `src/agents/verifier_agent.py` | 0 case bị gắn cờ vấn đề trên 50 case | `grep -c '"problem"' trace.jsonl` → 0 |

Output cụ thể: `output/EC_002.json` — case `late_delivery_seller`, `responsible_parties` trỏ đúng `seller_id` thật lấy từ `olist_sellers_dataset.csv`, `recommended_refund_brl = 18.27` khớp chính xác `freight_total_brl` tính từ `order_items.csv`, `resolution_actions` đúng thứ tự `["refund_freight", "review_seller_handoff", "verify_refund_completion", "verify_payment_allocation"]`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Làm sao để **Policy Agent (LLM 7B tham số)** tự đưa ra quyết định phân loại `primary_issue`/`secondary_issues`/`responsible_parties`/`refund`/`resolution_actions` đúng theo `EC_POLICY_V2`, mà **không dùng if/elif Python** quyết định thay (yêu cầu bắt buộc từ mentor), trong khi vẫn đảm bảo độ chính xác đủ cao trên cả 50 case.

### Cách triển khai

Thay vì nhồi toàn bộ quyết định vào 1 lời gọi LLM duy nhất (dễ khiến model 7B bỏ sót field hoặc đếm sai), tôi tách Policy Agent thành **4 lời gọi LLM chuyên biệt**, mỗi lời gọi chỉ trả lời 1 loại phán đoán:
1. `classify_primary` — chọn `primary_issue`, `root_cause_code`, `primary_action`, `responsible_parties`, `refund` (gộp vì các trường này phụ thuộc chặt vào nhau).
2. `classify_secondary` — 5 câu hỏi yes/no độc lập cho `secondary_issues`, dựa trên số đếm cho sẵn thay vì list dài (tránh model đếm sai độ dài).
3. `classify_bonus_actions` — sử dụng mệnh đề logic tương đương chặt chẽ (`must be true if and only if` kèm đánh số) thay vì các câu hỏi yes/no lỏng lẻo để mô hình 7B ánh xạ chính xác 100% các hành động bổ sung.
4. `classify_ambiguity` — 3 cờ mơ hồ (gần ngưỡng trễ giao, gần ngưỡng đối soát, thiếu dữ liệu) để Python tính `confidence` bằng công thức cộng trừ điểm — đây là phép tính số học trên phán đoán của LLM, không phải "chọn primary_issue" nên không vi phạm quy tắc không hard-code.

Mọi lời gọi này đều được truyền thêm `case_id` vào prompt để phá cache API Gateway từ phía nhà cung cấp, ép LLM chạy fresh cho từng case.
Số liệu đưa vào các lời gọi này (`delivery_variance_hours`, `payment_total_brl`, `reconciled`...) đều do `calculations.py` tính bằng công thức thuần Python cho sẵn trong README — LLM không được tự tính lại, chỉ diễn giải/quyết định dựa trên số đã có.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `case_id`, `order_status`, `payment_result` (dict từ `calculations.py`), `delivery_variance_hours`, `handoff_result`, số đếm item/seller/payment/category/related_order |
| Output | dict `{primary_issue, root_cause_code, responsible_parties, recommended_refund_brl, confidence, secondary_issues, resolution_actions}` |
| Module phụ thuộc | `src/llm_client.py` (gọi Qwen2.5-VL-7B-Instruct qua FPT AI Marketplace), `src/calculations.py`, `src/policy_engine.py` (hàm đếm thô) |
| Module sử dụng output | `src/agents/coordinator_agent.py` (gộp thành object cuối), `src/evidence_builder.py` (build evidence từ `root_cause_code`/`responsible_parties`) |
| Điều kiện lỗi cần xử lý | LLM trả JSON không hợp lệ (retry 3 lần trong `llm_client.py`); `primary_issue` ngoài taxonomy 6 loại (fallback về `unsupported_late_claim`, Verifier gắn cờ); toàn bộ pipeline lỗi (ghi placeholder hợp lệ thay vì bỏ trống file) |

### Cách xác minh

```bash
python src/main.py
grep -c '"problem"' trace.jsonl   # kỳ vọng 0
```

- **Kết quả mong đợi:** 50/50 file `output/EC_XXX.json` hợp lệ, 0 case bị Verifier gắn cờ.
- **Kết quả thực tế:** Đúng như kỳ vọng — 50/50 file, 0 vấn đề Verifier; đối chiếu với công thức chuẩn (công cụ QA nội bộ, không nộp bài) cho thấy 48/50 case (96%) khớp chính xác `primary_issue`.
- **Artifact/log:** `output/EC_001.json` .. `output/EC_050.json`, `trace.jsonl` (root repo).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Ban đầu tôi triển khai `policy_engine.py` bằng if/elif Python thuần theo đúng bảng `EC_POLICY_V2` — chính xác tuyệt đối vì là công thức tường minh. Sau khi mentor xác nhận **không được hard-code logic phân loại**, phải chuyển toàn bộ quyết định (`primary_issue`, `secondary_issues`, `responsible_parties`, `refund`, `resolution_actions`) sang cho LLM tự suy luận.
- **Các phương án đã cân nhắc:**
  1. Giữ nguyên if/elif, chỉ dùng LLM để cross-check độc lập (ảnh hưởng `confidence`, không quyết định nội dung).
  2. Xoá if/elif hoàn toàn, để 1 lời gọi LLM duy nhất tự quyết định tất cả 6 trường trong 1 prompt.
  3. Xoá if/elif hoàn toàn, nhưng **tách Policy Agent thành 4 lời gọi LLM chuyên biệt**, mỗi lời gọi 1 loại phán đoán.
- **Phương án đã chọn:** Phương án 3.
- **Lý do:** Phương án 1 không tuân thủ đúng yêu cầu "LLM phải tự quyết định". Phương án 2 khi test thực tế cho thấy model 7B bỏ sót field, đếm sai list, nhầm thứ tự ưu tiên rule (case đáng lẽ `valid_split_payment` bị chọn nhầm `unsupported_late_claim`). Phương án 3 giảm độ phức tạp mỗi lời gọi, giúp model tập trung vào đúng 1 quyết định nên chính xác hơn hẳn.
- **Bằng chứng quyết định phù hợp:** Đối chiếu với công thức chuẩn tăng từ khoảng 82% (bản 1 lời gọi) lên 96% (bản 4 lời gọi) trên 50 case; số case bị Verifier gắn cờ luôn = 0 ở cả 2 bản (khác biệt nằm ở độ chính xác nội dung, không phải lỗi cấu trúc).

## 6. Một số lỗi hoặc blocker đã xử lý

### Lỗi 1: Delivery Agent đọc sai dấu của delivery_variance_hours
- **Triệu chứng/lỗi nguyên văn:** Delivery Agent trả về `{"late_delivery": true, ...}` cho case có `delivery_variance_hours: -166.52` — một số âm (nghĩa là giao SỚM hơn ước tính 166.52 giờ), nhưng model kết luận là "trễ".
- **Lệnh hoặc bước tái hiện:**
  ```bash
  python -c "from src.agents.coordinator_agent import run; ..."
  # xem trace: delivery_agent -> {'late_delivery': True, 'late_seller_ids': [], ...}
  ```
- **Nguyên nhân gốc:** Prompt ban đầu chỉ giải thích công thức `delivery_variance_hours = actual - estimated` mà không nói rõ ý nghĩa của **dấu âm/dương** — model 7B suy luận sai, coi số có độ lớn tuyệt đối cao (kể cả âm) là "càng trễ", không hiểu số âm nghĩa là sớm hơn.
- **Cách xử lý:** Viết lại prompt, thêm ví dụ cụ thể: *"delivery_variance_hours = -166.52 means delivered 166.52 hours EARLY, so late_delivery must be false"*, và nhấn mạnh rule "chỉ số dương (>0) mới là trễ" bằng chữ in hoa.
- **Cách xác minh sau khi sửa:** Chạy lại cùng case, `late_delivery` trả về `false` đúng — test thêm với `delivery_variance_hours` dương thật (case có giao trễ) để chắc không phá hướng còn lại.
- **Điều học được:** Model nhỏ (7B) không tự suy luận đúng ý nghĩa dấu số trong bối cảnh nghiệp vụ nếu không được ví dụ minh hoạ tường minh — luôn cần test cả 2 chiều (số âm và dương) sau khi sửa prompt.

### Lỗi 2: Thiếu nhất quán và bỏ sót bonus actions (ví dụ: verify_refund_completion)
- **Triệu chứng/lỗi nguyên văn:** Một số case hoàn tiền (như `EC_006` trễ seller hoặc `EC_023` trễ logistics) bị thiếu mất hành động `verify_refund_completion` trong `resolution_actions`. Hơn nữa, xuất hiện sự không nhất quán giữa các case có cùng dữ liệu số đếm giống nhau (như `EC_003` và `EC_023`) khi một case có nhãn đúng và case kia có nhãn sai.
- **Lệnh hoặc bước tái hiện:**
  ```bash
  python src/main.py
  # Xem file output/EC_023.json thiếu 'verify_refund_completion' trong resolution_actions
  ```
- **Nguyên nhân gốc:**
  1. Prompt bonus actions cũ sử dụng cụm từ `"should apply only if"` lỏng lẻo khiến mô hình 7B thỉnh thoảng bỏ sót nhãn.
  2. API Gateway phía provider có cơ chế cache kết quả dựa trên user prompt. Vì các case có các tham số số đếm đầu vào giống nhau, API Gateway tự động trả về kết quả cache từ lượt chạy trước (khi chưa tinh chỉnh prompt).
- **Cách xử lý:**
  1. Tinh chỉnh prompt `ACTIONS_SYSTEM_PROMPT` thành dạng mệnh đề logic số học nghiêm ngặt (`must be true if and only if` kèm đánh số).
  2. Bổ sung tham số `case_id` vào user prompt của cả 4 cuộc gọi LLM trong Policy Agent để bẻ gãy (bypass) cơ chế cache API Gateway, buộc API Gateway gửi yêu cầu fresh lên LLM.
- **Cách xác minh sau khi sửa:** Chạy lại `python src/main.py`, 100% case hoàn tiền đều có `verify_refund_completion` ổn định và nhất quán, 50/50 file output đạt trạng thái OK.
- **Điều học được:** Khi làm việc với mô hình nhỏ qua API Gateway bên thứ ba, ngoài thiết kế prompt logic boolean chặt chẽ, bắt buộc phải chèn một định danh duy nhất (như `case_id`) để tránh cache và đảm bảo tính nhất quán của kết quả.

### Lỗi 3: Khai báo luật nhưng quên truyền giá trị biến vào user_prompt
- **Triệu chứng/lỗi nguyên văn:** Một số case như `EC_015`, `EC_041` có từ 2 payment trở lên nhưng LLM vẫn phân loại sai thành `unsupported_late_claim` thay vì `valid_split_payment`.
- **Nguyên nhân gốc:** Policy Agent định nghĩa luật có dùng `payment_count`, nhưng trong chuỗi `user_prompt` gửi lên LLM lại... quên không nhúng biến `payment_count` vào. Do đó, mô hình hoàn toàn mù tịt về số lượng payment.
- **Cách xử lý:** Bổ sung `f"payment_count: {payment_count}\n"` vào chuỗi `user_prompt` trong hàm `classify_primary`.
- **Điều học được:** Không bao giờ được mặc định LLM tự biết các dữ liệu mà mình quên truyền vào prompt. Luôn đối chiếu các biến cần thiết trong rule với dữ liệu thực tế được đưa vào user_prompt.

### Lỗi 4: Mô hình nhỏ hiểu lầm toán tử so sánh (>, ==)
- **Triệu chứng/lỗi nguyên văn:** Mặc dù đã truyền `payment_count`, các case có đúng 1 payment (như `EC_001`) vẫn bị LLM phân loại sai thành `valid_split_payment` (đòi hỏi `>= 2`).
- **Nguyên nhân gốc:** LLM 7B kém trong việc đọc hiểu các toán tử lập trình như `>= 2` và `== 1`, dẫn tới việc đối chiếu logic sai lệch.
- **Cách xử lý:** Đổi hoàn toàn các toán tử toán học trong `CLASSIFY_SYSTEM_PROMPT` sang tiếng Anh tường minh. Ví dụ: đổi `>= 2` thành `"is 2 or greater"`, đổi `== 1` thành `"is exactly 1"`.
- **Điều học được:** Tránh dùng ngôn ngữ lập trình hoặc ký hiệu toán học thuần tuý khi viết prompt cho các LLM nhỏ; ngôn ngữ tự nhiên tường minh mang lại độ tin cậy và hiểu đúng cao hơn rất nhiều.

## 7. Hiểu biết về luồng end-to-end

> Lưu ý: 5 câu hỏi mẫu trong template gốc (về Crossref, vector index, retrieval) thuộc về một bài lab khác, không khớp với đề bài E-commerce Dispute Resolution này. Thay bằng 5 câu tương đương đúng với luồng thật của bài:
> 1. Dữ liệu đi từ CSV đến output JSON như thế nào?
> 2. Vì sao pipeline không được để LLM tự tính số?
> 3. Vì sao phải tách Policy Agent thành nhiều lời gọi nhỏ thay vì 1 lời gọi lớn?
> 4. Verifier Agent kiểm tra gì và tại sao không chặn ghi file khi phát hiện lỗi?
> 5. Kết quả cuối cùng được xem là đáng tin cậy dựa trên gì?

**Câu trả lời:**

1. `claimed_order_id` từ input → `data_loader.py` đọc & join 9 CSV Olist → `calculations.py` tính `delivery_variance_hours`/`payment_reconciliation` bằng công thức thuần → 4 domain agent (LLM) sinh finding cho trace → Policy Agent (LLM, 4 lời gọi) quyết định phân loại dựa trên số liệu đã tính → `evidence_builder.py` build evidence/context từ dữ liệu thật → Verifier kiểm tra → ghi `output/EC_XXX.json`.
2. Vì các công thức (giờ chênh lệch, tổng tiền, ngưỡng đối soát 0.10 BRL) đã cho sẵn tường minh trong README — để LLM tự cộng trừ dễ sai số, không tái lập được; Python tính đảm bảo chính xác 100%, LLM chỉ dùng số đó để suy luận nghiệp vụ.
3. Vì thử nghiệm cho thấy model 7B khi phải quyết định 6+ trường cùng lúc dễ bỏ sót/đếm sai — tách theo nguyên tắc "1 agent, 1 phán đoán" giúp tăng độ chính xác đáng kể (~82% → ~96%).
4. Verifier kiểm schema, giới hạn mảng, evidence có tồn tại thật trong CSV không, `primary_issue`/`root_cause_code` có hợp lệ không, `refund` có khớp số liệu thật không. Không chặn ghi file vì đề bài yêu cầu nộp **đúng 50 file** — thiếu 1 file cũng đủ bị loại (hard gate) — nên case có vấn đề vẫn ghi ra nhưng được log riêng để soát thủ công.
5. Không có đáp án chính thức để đối chiếu (vì cấm hard-code), nên tự viết 1 script audit riêng (không nộp bài) tính lại theo đúng công thức `EC_POLICY_V2` để so sánh — đạt 96% khớp trên 50 case, cùng với 0 case bị Verifier gắn cờ vấn đề cấu trúc/evidence.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đoàn Ngọc Linh
**Ngày xác nhận:** 2026-08-05
