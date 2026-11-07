# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Phiên bản trong gói này: xem `VERSION` trong `server.py` (hiện ở góc trên giao diện và tại đường dẫn `/version`).

Trạng thái: **Toàn bộ 10/10 Giai đoạn bắt buộc cốt lõi (Giai đoạn 1 đến 10) đã hoàn thành toàn diện và vượt qua 100% bộ kiểm thử tự động.**

## Giai đoạn 1: Data Model
- Bảng gốc bất biến + nhật ký thao tác + bảng dẫn xuất. Không bao giờ sửa dữ liệu gốc (có test).
- Schema bước: `id, type, enabled, ...`; enum `OP_TYPES` đủ 15 loại, đang chạy `FORMULA` và `CONDITIONAL`.
- Phản hồi thống nhất `success / warnings / errors / stats / data` cho các API.
- Hoàn tác, làm lại, nhật ký thao tác (audit log) có thời gian, loại, nội dung, số dòng ảnh hưởng, quyết định của người dùng. Chỉ giữ trong bộ nhớ phiên (2 giờ).

## Giai đoạn 2: Formula Engine
- Toán tử `+ - * / %`, `&`, so sánh. Hàm toán, chuỗi, điều kiện (IF tính lười), ngày tháng, cộng trừ ngày, ISEMPTY, ISNUMBER, ISDATE, CONTAINS, STARTSWITH, ENDSWITH.
- Mã lỗi không crash: ERROR_DIV_ZERO, ERROR_COLUMN, ERROR_SYNTAX, ERROR_TYPE, ERROR_DATE, ERROR_OVERFLOW, ERROR_NULL. Ô lỗi hiện mã lỗi, không bị tính thành 0.
- Phân tích phụ thuộc, phát hiện vòng, báo "cột được tạo ở bước sau" khi thứ tự bước sai.
- **Quy trình biến đổi có thứ tự** (mục 7): công thức và quy tắc đan xen, chạy từ trên xuống, đổi thứ tự bằng mũi tên.
- **Độ tin cậy khi đọc số** (mục 3.6): giá trị mơ hồ như `1.234` hoặc `1,234` chỉ được chuyển khi đủ bằng chứng từ các ô khác trong cột, hoặc khi bạn chọn "Cách đọc số".
- Cột có vài ô bẩn (từ 75% ô đọc được) vẫn được coi là cột số hoặc ngày; ô còn lại báo ERROR_TYPE thay vì làm hỏng cả cột.
- **Báo cáo lỗi** (mục 59): loại lỗi, file, sheet, dòng, cột, giá trị gốc, kiểu cần, gợi ý sửa; xem trên trang và tải CSV.
- **Trạng thái** SAFE / REVIEW_REQUIRED / UNSAFE cho từng bước và cho lần xuất.
- **AI gợi ý công thức** từ mô tả tiếng Việt (mục 47): chỉ gợi ý, công thức được kiểm tra trước khi trả về, người dùng phải xem trước rồi mới thêm vào quy trình.
- An toàn: DSL tự viết, không eval/exec, giới hạn độ dài và độ sâu.
- Kiểm tra độc lập: sau khi xuất, đọc lại file và chạy lại cả quy trình từ dữ liệu gốc bằng bộ tính Decimal riêng.

## Giai đoạn 3: Quy tắc điều kiện (NẾU ... THÌ ... NGƯỢC LẠI ...)
- Điều kiện: =, khác, >, <, >=, <=, chứa, bắt đầu bằng, kết thúc bằng, để trống, không trống, bị trùng, duy nhất, thuộc danh sách, không thuộc danh sách; nối bằng VÀ hoặc HOẶC, mỗi điều kiện có thể phủ định.
- Hành động mỗi nhánh (tối đa 6): điền hoặc ghi đè giá trị, xóa dữ liệu, thay thế chữ, tô màu (dòng hoặc ô), đánh dấu bằng nhãn, đưa vào danh sách, thêm giá trị vào cột cuối.
- Xem trước (dòng khớp, ô đổi, cột mới, trước và sau), cảnh báo ghi đè và **bắt xác nhận khi ghi đè ô đang có dữ liệu**. Không ghi đè cột công thức.
- Kiểm tra độc lập chạy lại cả chuỗi quy tắc, đối chiếu giá trị và màu trong file xuất.

## Giai đoạn 4: Chuẩn hóa dữ liệu (mục 10)
- Bước mới "Chuẩn hóa" trong Quy trình biến đổi (chạy đan xen với công thức và quy tắc, đổi thứ tự được, hoàn tác được).
- 7 loại: chữ và khoảng trắng (Unicode về dạng chuẩn NFC, bỏ ký tự vô hình, khoảng trắng lạ về một dấu cách, tùy chọn chữ thường, CHỮ HOA, Viết Hoa Đầu Mỗi Từ, bỏ dấu tiếng Việt), ô trống giả (N/A, -, null... tự sửa được danh sách), số điện thoại Việt Nam (dạng 0912345678 hoặc +84912345678), email, số và tiền (1.234,5; 1,234.5; 1.000₫; VND), phần trăm, ngày (ngày/tháng/năm, năm-tháng-ngày, "ngày 5 tháng 3 năm 2026", có giờ).
- Hai chế độ: ghi đè trong kết quả (có xem trước, bắt xác nhận khi đổi ô có dữ liệu) hoặc tạo cột mới "<cột> (chuẩn hóa)" giữ nguyên cột gốc. Dữ liệu gốc không bao giờ bị sửa.
- Tính lũy đẳng: chuẩn hóa hai lần cho kết quả như một lần.
- Kiểm tra độc lập: bản chuẩn hóa thứ hai viết riêng chạy lại từ dữ liệu gốc và so với file xuất.

## Giai đoạn 5: Smart Merge - Schema, Nhận diện cột, Khóa (mục 11 đến 18)
- **Module độc lập `schema.py`:**
  - **Lược đồ dữ liệu `DatasetSchema` (mục 13):** Tự động thống kê `column_name`, `normalized_name`, `data_type`, `sample_values`, `unique_ratio`, `null_ratio`, `format_distribution`, `semantic_hint`, `distinct_count`.
  - **Chuẩn hóa tên cột để so khớp (mục 14):** Bỏ dấu tiếng Việt, chuyển chữ thường, gộp khoảng trắng, tách CamelCase (ví dụ `Mã KH`, `ma_kh`, `MA KH`, `mã-kh`, `MaKH` -> `ma kh`). Không bao giờ sửa tên cột gốc của người dùng.
  - **Nhận diện ngữ nghĩa (mục 16):** 12 loại dữ liệu nghiệp vụ (customer_id, product_id, email, phone, address, name, date, price, quantity, currency, percentage, status, description).
  - **Nhận diện khóa chính & tính mơ hồ (mục 17):** Tự động đánh giá ứng viên làm khóa dựa trên độ duy nhất (>= 90%), độ đầy đủ (null <= 5%), ngữ nghĩa và kiểu dữ liệu. Cờ `is_ambiguous` khi có nhiều ứng viên ngang nhau.
  - **Nhận diện khóa kép (mục 18):** Tự động tìm kiếm các cặp 2 cột có độ kết hợp đạt tỷ lệ duy nhất >= 98% khi không có khóa đơn đạt chuẩn.
  - **So khớp cột thông minh (mục 15):** Thuật toán tính điểm 6 trọng số chuẩn của lộ trình: Tên cột 30%, Kiểu 20%, Mẫu 20%, Ngữ nghĩa 15%, Định dạng 10%, Thống kê 5%.
  - **Phân loại độ tin cậy (mục 20, 21, 56):** `SAFE` (>= 90%), `REVIEW_REQUIRED` (50% - 89%), `UNSAFE` (< 50%).
  - **Đề xuất chế độ merge (mục 12, 28):** Đề xuất Gộp dòng (UNION) khi độ phủ >= 70%, hoặc Ghép theo khóa (JOIN) khi có khóa chung tin cậy.
  - **Kiểm tra đối chiếu độc lập (mục 0 điểm 10 & mục 39):** `independent_match_check` kiểm tra tính hợp lệ của mapping.
- **Hỗ trợ nạp nhiều file trong phiên:**
  - `POST /api/analyze` nhận nhiều file cùng lúc qua `files`.
  - `POST /api/merge/add_file` bổ sung thêm file mới vào phiên mở.
  - `POST /api/merge/schema`, `POST /api/merge/analyze`, `POST /api/merge/mapping`.

## Giai đoạn 6: Record Matching Engine (mục 12, 19, 20, 21, 22, 23, 24)
- **Module độc lập `merge_engine.py`:**
  - **Chuẩn hóa giá trị khóa (mục 19):** So khớp chính xác + chuẩn hóa (Exact & Normalized Match): bỏ khoảng trắng, chuẩn hóa Unicode NFC, casefold, chuẩn hóa số học (`10.0` == `10`), chuẩn hóa ngày tháng. Hỗ trợ khóa đơn và khóa tổ hợp (composite key).
  - **Append / Union (mục 12.1):** Gộp dòng hai bảng theo ánh xạ cột đã xác nhận. Tự động bổ sung các cột mới của bảng B (nếu chọn chiến lược `append`) và độn ô rỗng an toàn. Bảo toàn tuyệt đối số dòng $N_{out} = N_A + N_B$.
  - **Join / Match (mục 12.2):** Ghép hai bảng theo khóa với 4 kiểu kết nối: `left`, `inner`, `full`, `right`.
  - **Chống bùng nổ tích Descartes (mục 21):** Kiểm tra tần suất trùng lặp khóa ở cả hai bảng A và B, chặn đứng rủi ro tràn bộ nhớ (Cartesian explosion) khi phát hiện số dòng nhân bản vượt ngưỡng an toàn.
  - **Phát hiện & giải quyết xung đột (mục 22):** Tự động phát hiện xung đột dữ liệu giữa các cột trùng tên không phải khóa. Hỗ trợ 3 chiến lược: `prefer_a` (giữ bảng A), `prefer_b` (ưu tiên bảng B), `keep_both` (tách thành `<Cột> (A)` và `<Cột> (B)`).
  - **Phát hiện dòng thiếu & cột bổ sung (mục 23, 24):** Thống kê số lượng dòng thiếu ở bảng B (`missing_in_b`), dòng thiếu ở bảng A (`missing_in_a`), và danh sách cột mới được ghép.
  - **Kiểm tra đối chiếu độc lập (mục 0 điểm 10 & mục 39):** Hàm `independent_merge_check` chạy lại thuật toán gộp độc lập bằng cấu trúc dữ liệu thuần túy, xác minh bất biến số dòng, tính toàn vẹn cấu trúc cột và đảm bảo dữ liệu gốc bất biến 100%.
- **Tích hợp API:**
  - `POST /api/merge/execute` hoàn chỉnh cho cả 2 chế độ UNION và JOIN kèm đầy đủ thống kê `stats`, `conflicts`, `warnings`.

## Giai đoạn 7: Giao diện Smart Merge (Smart Merge UI - mục 26, 27, 28, 61)
- **Giao diện tương tác người dùng (`static/index.html`):**
  - **Bộ chọn chế độ gộp thông minh (mục 28):** Chuyển đổi linh hoạt giữa Gộp dòng (`UNION`) và Ghép theo khóa (`JOIN`).
  - **Cấu hình JOIN trực quan:** Hỗ trợ 3 kiểu kết nối (`left`, `inner`, `full`), dropdown chọn khóa định danh bảng A và B (tự động điền ứng viên tốt nhất).
  - **Chiến lược giải quyết xung đột (mục 22):** Lựa chọn tức thì trên giao diện giữa `prefer_a` (giữ Bảng A), `prefer_b` (ưu tiên Bảng B) hoặc `keep_both` (tách thành hai cột riêng).
  - **Bảng đối chiếu & Ánh xạ cột (mục 27):** Hiển thị trực quan cặp cột, độ tương đồng %, badge đánh giá SAFE / Cần duyệt, và giải thích chi tiết quy tắc so khớp.
  - **Xem trước kết quả ghép (Merge Preview - mục 26):** API `POST /api/merge/preview` và bảng xem trước 10 dòng đầu kèm huy hiệu thống kê tức thì (tổng dòng, số dòng khớp, dòng thiếu ở A/B, số ô xung đột).
  - **Bảng cảnh báo xung đột (Conflict Warning Panel):** Hiển thị chi tiết từng ô dữ liệu xung đột giữa A và B trước khi người dùng quyết định gộp thật.
  - **Thực thi và chuyển bảng tự động:** Gộp bảng mượt mà, thông báo kết quả chi tiết và tự động nạp bảng mới vào màn hình làm việc.

## Giai đoạn 8: Xuất file đa định dạng (Export Expansion - mục 30 đến 36)
- **Module độc lập `export.py`:**
  - Hỗ trợ đầy đủ XLSX (2 chế độ: công thức động và giá trị), CSV (UTF-8 BOM), TSV, JSON (record-oriented).
  - Cảnh báo định dạng tự động (`format_warnings`).
  - Bộ kiểm tra đối chiếu độc lập `read_back` đọc lại trực tiếp file nhị phân và đối chiếu dòng/cột/ô.

## Giai đoạn 9: Kiểm định toàn diện (Full Validation Engine - mục 37 đến 44)
- **Module độc lập `validate_engine.py`:**
  - Kiểm tra công thức với dung sai số học (floating-point tolerance $10^{-9}$).
  - Phát hiện hao hụt dữ liệu bất thường (`detect_data_loss`) có giải trình.
  - Phát hiện nhân bản dòng ngoài ý muốn (`detect_duplicate_expansion`).
  - Kiểm tra tính toàn vẹn tham chiếu khóa (`check_referential_integrity`).
  - Xuất nhật ký kiểm định có cấu trúc (Audit Log) tải về JSON / CSV.

## Giai đoạn 10: Kiểm toán bảo mật và hiệu năng (mục 45 đến 49)
- **Bộ kiểm toán `tests/test_audit.py`:**
  - Kháng injection, chặn đứng `eval`/`exec`, bảo vệ sandbox AST.
  - Phát hiện và từ chối tham chiếu vòng / tự tham chiếu.
  - Kiểm toán tính bất biến tuyệt đối của dữ liệu gốc.
  - Kiểm toán hiệu năng xử lý 10.000 dòng và 50.000 dòng.

## Kiểm thử hồi quy toàn diện (mục 63 đến 67)
`python tests/run_all.py` chạy toàn bộ **15 bộ kiểm thử**:
1. `test_units`: kiểm thử đơn vị
2. `test_golden`: kiểm thử đáp án chuẩn 12 bộ dữ liệu
3. `test_formula`: kiểm thử 4.000 công thức và đối chiếu 2 bộ tính
4. `test_rules`: kiểm thử 3.000 bộ quy tắc điều kiện ngẫu nhiên
5. `test_pipeline`: kiểm thử quy trình biến đổi đa bước
6. `test_normalize`: kiểm thử 7 loại chuẩn hóa dữ liệu
7. `test_schema`: kiểm thử nhận diện schema, khóa và khớp cột
8. `test_merge_api`: kiểm thử API gộp file đa file
9. `test_merge_engine`: kiểm thử bộ máy so khớp và thực thi gộp bảng (UNION & JOIN)
10. `test_export`: kiểm thử xuất file đa định dạng (XLSX, CSV, TSV, JSON)
11. `test_validation`: kiểm thử bộ máy kiểm định toàn diện (dung sai số, hao hụt, duplicate)
12. `test_audit`: kiểm thử kiểm toán bảo mật và hiệu năng 50.000 dòng
13. `test_integration`: kiểm thử tích hợp toàn bộ luồng từ upload đến export
14. `test_core`: kiểm thử cốt lõi bộ xử lý C++/Python
15. `test_ui`: kiểm thử giao diện Playwright (tự động bỏ qua nếu chưa cài browser)

Kết quả hiện tại: **15/15 bộ ĐẠT 100%**.
