# Kiến trúc Day09 — Multi-Agent E-commerce Dispute Resolution

## Mục tiêu

Dự án Day09 được xây dựng để đọc các case đầu vào từ thư mục input, xử lý dữ liệu Olist, tạo payload đánh giá dispute và ghi ra các file JSON trong thư mục output. Hiện tại, luồng chạy chính của Day09 là pipeline deterministic, không dựa vào LLM để quyết định nội dung cuối cùng.

## Cấu trúc thực tế của dự án

### 1. Data layer
- [src/data_layer.py](src/data_layer.py) đọc 9 file CSV của Olist và xây dựng các index theo order, customer, seller, product và payment.
- Dữ liệu được load một lần và dùng lại cho toàn bộ quá trình xử lý từng case.

### 2. Facts layer
- [src/facts.py](src/facts.py) tạo các tập facts cho từng order, bao gồm customer context, order/product context, payment summary và delivery summary.
- Đây là lớp chuẩn bị dữ liệu trước khi build payload cuối cùng.

### 3. Policy layer
- [src/policy.py](src/policy.py) là module quyết định nghiệp vụ chính hiện tại.
- Các rule được implement bằng logic deterministic theo EC_POLICY_V2:
  - xác định primary issue
  - xác định secondary issues
  - xác định responsible parties
  - tính recommended refund
  - xác định resolution actions và confidence

### 4. Payload builder
- [src/builder.py](src/builder.py) gom các facts và policy output thành cấu trúc JSON chuẩn của bài lab.
- Module này tạo các section:
  - case_assessment
  - affected_entities
  - customer_context
  - product_context
  - delivery_analysis
  - payment_reconciliation
  - root_cause_analysis
  - evidence_ids
  - financial_resolution
  - resolution_actions

### 5. Validator
- [src/validator.py](src/validator.py) kiểm tra schema, giới hạn mảng, format evidence, số tiền có đúng 2 chữ số thập phân và các giá trị taxonomy hợp lệ.
- Validator giúp đảm bảo output có cấu trúc nhất quán trước khi ghi file.

### 6. Runner
- [src/run_core.py](src/run_core.py) là entrypoint chạy chính của Day09.
- Nó duyệt toàn bộ file trong input/EC_*.json, tạo output tương ứng trong output/ và ghi kết quả tổng hợp ra console.

## Luồng xử lý một case

```text
input/EC_XXX.json
  -> OlistData đọc CSV
  -> facts.py chuẩn bị dữ liệu cho order
  -> policy.py quyết định issue/refund/actions
  -> builder.py tạo payload JSON
  -> validator.py kiểm tra cấu trúc
  -> output/EC_XXX.json
```

## Điểm cần ghi nhớ

- Mặc dù thư mục src/agents có các agent class và file A2A, luồng chạy thực tế hiện tại của Day09 được thực hiện qua [src/run_core.py](src/run_core.py) và logic policy deterministic trong [src/policy.py](src/policy.py).
- Việc đồng bộ từ thư mục mẫu K4 giúp Day09 có cấu trúc source code tương đồng và có thể chạy ổn định trên 50 case.
- Kết quả chạy thực tế đã được xác minh bằng lệnh:
  - python -m compileall src
  - python -m src.run_core
