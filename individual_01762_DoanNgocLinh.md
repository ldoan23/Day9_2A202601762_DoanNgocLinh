# Báo cáo cá nhân — Đoàn Ngọc Linh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đoàn Ngọc Linh |
| MSSV | 2A202601762 |
| Khóa/Lớp | K4 |
| Vai trò chính | Source sync & pipeline runner cho Day09 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc chính

| Module / deliverable | File liên quan | Vai trò thực hiện | Trạng thái |
| --- | --- | --- | --- |
| Đồng bộ mã nguồn Day09 với thư mục mẫu K4 | [src](src), [src/agents](src/agents), [src/builder.py](src/builder.py), [src/data_layer.py](src/data_layer.py), [src/policy.py](src/policy.py), [src/validator.py](src/validator.py) | Đảm bảo cấu trúc source code và module chính được đồng bộ đúng với thư mục mẫu | Hoàn thành |
| Xây dựng và chạy pipeline output cho 50 case | [src/run_core.py](src/run_core.py) | Duyệt các file input, tạo payload và ghi output JSON vào thư mục output | Hoàn thành |
| Kiểm tra tính khả thi của mã nguồn | [src](src) | Chạy compileall và chạy chương trình để xác nhận không có lỗi cú pháp và pipeline chạy thành công | Hoàn thành |

### Kết quả bàn giao

- Tạo được 50 file output JSON tương ứng với 50 case input.
- Đảm bảo thư mục output có thể dùng để nộp bài.
- Xác nhận chương trình chạy thành công bằng lệnh sau:
  - python -m compileall src
  - python -m src.run_core

## 3. Cách làm và logic hiện tại của dự án

Dự án Day09 hiện tại được triển khai theo hướng pipeline deterministic:

1. [src/data_layer.py](src/data_layer.py) đọc dữ liệu từ các file CSV Olist.
2. [src/facts.py](src/facts.py) chuẩn bị các facts cần thiết cho từng order.
3. [src/policy.py](src/policy.py) áp dụng logic quyết định theo EC_POLICY_V2 để xác định:
   - primary issue
   - secondary issues
   - responsible parties
   - recommended refund
   - resolution actions
   - confidence
4. [src/builder.py](src/builder.py) tạo payload JSON cuối cùng.
5. [src/validator.py](src/validator.py) kiểm tra cấu trúc và giới hạn dữ liệu trước khi ghi file.
6. [src/run_core.py](src/run_core.py) duyệt toàn bộ case và xuất output.

## 4. Kết quả đã đạt được

- Chương trình chạy thành công trên 50 case.
- Không có lỗi cú pháp trong toàn bộ thư mục src.
- Các file output đã được sinh ra trong thư mục output của Day09.

## 5. Một số ghi chú kỹ thuật

- Mặc dù thư mục src/agents tồn tại, luồng chạy chính hiện tại của Day09 không cần LLM để tạo output cuối cùng; nó dùng logic deterministic trong [src/policy.py](src/policy.py).
- Việc đồng bộ mã nguồn từ thư mục mẫu K4 giúp Day09 có cấu trúc source code rõ ràng hơn và dễ chạy ổn định.
- Mục tiêu cuối cùng là đảm bảo output đúng đắn, đủ số lượng và có thể dùng để nộp bài.

## 6. Xác nhận

- [x] Tôi đã kiểm tra lại cấu trúc mã nguồn và cập nhật phù hợp với thực tế hiện tại.
- [x] Tôi đã chạy chương trình và xác nhận output được tạo thành công.
- [x] Tôi đã ghi nhận đúng vai trò và phần việc của mình trong bài lab này.
