# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Phiên bản trong gói này: xem `VERSION` trong `server.py` (hiện ở góc trên giao diện và tại đường dẫn `/version`).

Trạng thái: **Giai đoạn 1, 2, 3, 4 và 5 đã xong phần cốt lõi theo lộ trình (tiêu chí nghiệm thu mục 68 và 69 cho công thức và quy tắc; mục 10 cho chuẩn hóa; mục 11 đến 18 cho schema, nhận diện cột và khóa của Smart Merge), kèm các mục phụ của mục 3 đến 9, 11 đến 18, 44 đến 47, 50 đến 56, 59, 63 đến 67.**
Còn lại chưa làm, ghi ở cuối. Chưa chạy thử trên Render thật và chưa gọi AI thật (chỉ thử bằng phản hồi giả lập).

## Giai đoạn 1: Data Model
- Bảng gốc bất biến + nhật ký thao tác + bảng dẫn xuất. Không bao giờ sửa dữ liệu gốc (có test).
- Schema bước: `id, type, enabled, ...`; enum `OP_TYPES` đủ 15 loại, đang chạy `FORMULA` và `CONDITIONAL`.
- Phản hồi thống nhất `success / warnings / errors / stats / data` cho các API mới.
- Hoàn tác, làm lại, nhật ký thao tác (audit log) có thời gian, loại, nội dung, số dòng ảnh hưởng, quyết định của người dùng. Chỉ giữ trong bộ nhớ phiên (2 giờ).

## Giai đoạn 2: Formula Engine
- Toán tử `+ - * / %`, `&`, so sánh. Hàm toán, chuỗi, điều kiện (IF tính lười), ngày tháng, cộng trừ ngày, ISEMPTY, ISNUMBER, ISDATE, CONTAINS, STARTSWITH, ENDSWITH.
- Mã lỗi không crash: ERROR_DIV_ZERO, ERROR_COLUMN, ERROR_SYNTAX, ERROR_TYPE, ERROR_DATE, ERROR_OVERFLOW, ERROR_NULL. Ô lỗi hiện mã lỗi, không bị tính thành 0.
- Phân tích phụ thuộc, phát hiện vòng, báo "cột được tạo ở bước sau" khi thứ tự bước sai.
- **Quy trình biến đổi có thứ tự** (mục 7): công thức và quy tắc đan xen, chạy từ trên xuống, đổi thứ tự bằng mũi tên. Ví dụ làm sạch ô "N/A" rồi mới tính thành tiền.
- **Độ tin cậy khi đọc số** (mục 3.6): giá trị mơ hồ như `1.234` hoặc `1,234` chỉ được chuyển khi đủ bằng chứng từ các ô khác trong cột, hoặc khi bạn chọn "Cách đọc số". Không đủ thì không tự chuyển và báo cần kiểm tra.
- Cột có vài ô bẩn (từ 75% ô đọc được) vẫn được coi là cột số hoặc ngày; ô còn lại báo ERROR_TYPE thay vì làm hỏng cả cột.
- **Báo cáo lỗi** (mục 59): loại lỗi, file, sheet, dòng, cột, giá trị gốc, kiểu cần, gợi ý sửa; xem trên trang và tải CSV.
- **Trạng thái** SAFE / REVIEW_REQUIRED / UNSAFE cho từng bước và cho lần xuất.
- **AI gợi ý công thức** từ mô tả tiếng Việt (mục 47): chỉ gợi ý, công thức được kiểm tra trước khi trả về, người dùng phải xem trước rồi mới thêm vào quy trình. AI chỉ nhận mô tả, tên cột, kiểu và tối đa 6 dòng mẫu.
- Giao diện hàm nội bộ (mục 50): `parse_formula`, `validate_formula`, `evaluate_formula`, `evaluate_batch`.
- API (mục 54): `/api/formula/validate|preview|apply|suggest`, `/api/transform/preview|apply|undo|redo|update|settings|state`, `/api/rule/validate|preview|apply`, `/api/validate`, `/api/validate/report`.
- An toàn: DSL tự viết, không eval/exec, giới hạn độ dài và độ sâu.
- Kiểm tra độc lập: sau khi xuất, đọc lại file và chạy lại cả quy trình từ dữ liệu gốc bằng bộ tính Decimal riêng.

## Giai đoạn 3: Quy tắc điều kiện (NẾU ... THÌ ... NGƯỢC LẠI ...)
- Điều kiện: =, khác, >, <, >=, <=, chứa, bắt đầu bằng, kết thúc bằng, để trống, không trống, bị trùng, duy nhất, thuộc danh sách, không thuộc danh sách; nối bằng VÀ hoặc HOẶC, mỗi điều kiện có thể phủ định. So sánh có kiểu dữ liệu.
- Hành động mỗi nhánh (tối đa 6): điền hoặc ghi đè giá trị (chữ hoặc số, tên mới thì tạo cột), xóa dữ liệu, thay thế chữ, tô màu (dòng hoặc ô), đánh dấu bằng nhãn, đưa vào danh sách (cột "Danh sách"), thêm giá trị vào cột cuối (không tạo cột mới).
- Quy tắc chạy tuần tự; điều kiện của mỗi quy tắc tính trước khi quy tắc đó chạy. Dòng không đánh giá được điều kiện không chạy THÌ lẫn NGƯỢC LẠI, được đếm và đưa vào báo cáo lỗi.
- Xem trước (dòng khớp, ô đổi, cột mới, trước và sau), cảnh báo ghi đè và **bắt xác nhận khi ghi đè ô đang có dữ liệu**. Không ghi đè cột công thức.
- Kiểm tra độc lập chạy lại cả chuỗi quy tắc, đối chiếu giá trị và màu trong file xuất.

## Giai đoạn 4: Chuẩn hóa dữ liệu (mục 10)
- Bước mới "Chuẩn hóa" trong Quy trình biến đổi (chạy đan xen với công thức và quy tắc, đổi thứ tự được, hoàn tác được). Ví dụ làm sạch cột rồi mới tính công thức.
- 7 loại: chữ và khoảng trắng (Unicode về dạng chuẩn NFC, bỏ ký tự vô hình, khoảng trắng lạ về một dấu cách, tùy chọn chữ thường, CHỮ HOA, Viết Hoa Đầu Mỗi Từ, bỏ dấu tiếng Việt), ô trống giả (N/A, -, null... tự sửa được danh sách), số điện thoại Việt Nam (dạng 0912345678 hoặc +84912345678, tự thêm số 0 bị Excel làm mất, nhận cả số bàn 02x), email (bỏ khoảng trắng, chữ thường, kiểm tra cấu trúc), số và tiền (1.234,5; 1,234.5; 1.000₫; VND), phần trăm (10% thành 0,1 kèm định dạng %), ngày (ngày/tháng/năm, năm-tháng-ngày, "ngày 5 tháng 3 năm 2026", có giờ).
- Không đoán khi thiếu bằng chứng: số kiểu 1.234 và ngày kiểu 05/03/2026 chỉ được đổi khi các ô khác trong cột đủ để suy ra cách đọc, hoặc khi người dùng chọn cách đọc; không thì để nguyên ô và báo cần kiểm tra (REVIEW_REQUIRED). Ô không chuẩn hóa được cũng giữ nguyên và vào báo cáo lỗi kèm gợi ý sửa.
- Hai chế độ: ghi đè trong kết quả (có xem trước, bắt xác nhận khi đổi ô có dữ liệu) hoặc tạo cột mới "<cột> (chuẩn hóa)" giữ nguyên cột gốc. Dữ liệu gốc không bao giờ bị sửa.
- Gợi ý chuẩn hóa theo dữ liệu từng cột (bấm để điền sẵn biểu mẫu); chưa có gợi ý bằng AI (`suggest_normalization` ghi "có thể" trong lộ trình).
- Tính lũy đẳng: chuẩn hóa hai lần cho kết quả như một lần (có test ngẫu nhiên).
- Kiểm tra độc lập: bản chuẩn hóa thứ hai viết riêng chạy lại từ dữ liệu gốc và so với file xuất (cùng cơ chế như công thức và quy tắc).

Giới hạn của Giai đoạn 4:
- Chuẩn hóa chạy bằng Python (C++ chỉ đọc số, ngày và so sánh; lộ trình ghi "nếu phù hợp").
- Số điện thoại chỉ hỗ trợ Việt Nam. Tiền chỉ lấy phần số, chưa tách mã tiền tệ. Năm 2 chữ số chưa hỗ trợ (báo không hợp lệ).
- Chuẩn hóa chữ gộp cả xuống dòng thành dấu cách. Bỏ dấu tiếng Việt làm đổi dữ liệu nên chỉ dùng khi cần so sánh hoặc làm khóa.
- Chưa chuẩn hóa tên cột (thuộc Giai đoạn 5) và chưa chuẩn hóa địa chỉ, trùng lặp mờ (thuộc phần tương lai).
- Không chuẩn hóa được cột công thức (hãy sửa công thức).

## Giai đoạn 5: Smart Merge - Schema, Nhận diện cột, Khóa (mục 11 đến 18)
- **Module độc lập `schema.py`:**
  - **Lược đồ dữ liệu `DatasetSchema` (mục 13):** Tự động thống kê `column_name`, `normalized_name`, `data_type`, `sample_values`, `unique_ratio`, `null_ratio`, `format_distribution`, `semantic_hint`, `distinct_count`.
  - **Chuẩn hóa tên cột để so khớp (mục 14):** Bỏ dấu tiếng Việt, chuyển chữ thường, gộp khoảng trắng, tách CamelCase, chuyển ký tự phân cách thành khoảng trắng (ví dụ `Mã KH`, `ma_kh`, `MA KH`, `mã-kh`, `MaKH` -> `ma kh`). Không bao giờ sửa tên cột gốc của người dùng.
  - **Nhận diện ngữ nghĩa (mục 16):** 12 loại dữ liệu nghiệp vụ (customer_id, product_id, email, phone, address, name, date, price, quantity, currency, percentage, status, description).
  - **Nhận diện khóa chính & tính mơ hồ (mục 17):** Tự động đánh giá ứng viên làm khóa dựa trên độ duy nhất (unique ratio >= 90%), độ đầy đủ (null ratio <= 5%), loại ngữ nghĩa và kiểu dữ liệu. Phát hiện cờ `is_ambiguous` khi có nhiều ứng viên điểm ngang nhau để không tự quyết định thay người dùng.
  - **Nhận diện khóa kép (mục 18):** Tự động tìm kiếm các cặp 2 cột có độ kết hợp đạt tỷ lệ duy nhất >= 98% khi không có khóa đơn đạt chuẩn (ví dụ `Mã chi nhánh` + `Mã sản phẩm`).
  - **So khớp cột thông minh (mục 15):** Thuật toán tính điểm theo 6 trọng số chuẩn của lộ trình: Tên cột 30%, Kiểu dữ liệu 20%, Mẫu giá trị 20%, Ngữ nghĩa 15%, Định dạng 10%, Thống kê 5%.
  - **Phân loại độ tin cậy (mục 20, 21, 56):** `SAFE` (>= 90%, tự động ghép), `REVIEW_REQUIRED` (50% - 89%, đề xuất và yêu cầu người dùng duyệt), `UNSAFE` (< 50%, không tự ghép). Bắt buộc cảnh báo khi lệch kiểu số vs ngày.
  - **Đề xuất chế độ merge (mục 12, 28):** Tự động đề xuất Gộp dòng (UNION) khi độ phủ cột >= 70%, hoặc Ghép theo khóa (JOIN) khi tìm thấy khóa chung tin cậy, hoặc báo Cần xem xét kèm lý do giải thích.
  - **Kiểm tra đối chiếu độc lập (mục 0 điểm 10 & mục 39):** Hàm `independent_match_check` kiểm tra tính hợp lệ của mapping, chặn ghép sai kiểu số vs ngày, chặn gán trùng lặp và chặn gán sai cờ SAFE cho điểm < 90%.
- **Hỗ trợ nạp nhiều file trong phiên:**
  - Nâng cấp `POST /api/analyze` nhận nhiều file cùng lúc qua danh sách `files`.
  - Thêm API `POST /api/merge/add_file` cho phép bổ sung thêm file mới vào phiên làm việc đang mở mà không làm mất dữ liệu cũ.
  - Thêm API `POST /api/merge/schema`, `POST /api/merge/analyze`, `POST /api/merge/mapping`.
- **Giao diện người dùng (Mục 61):** Thêm card "Gộp file & So khớp cột thông minh" hiển thị danh sách bảng trong phiên, nút tải thêm file, bộ chọn bảng A/B, bảng so khớp cột trực quan và thông tin khóa ứng viên.

## Kiểm thử (mục 63 đến 67)
`python tests/run_all.py` chạy 11 bộ: đơn vị (`test_units`), đáp án chuẩn (`test_golden`), công thức (`test_formula`), quy tắc (`test_rules`), quy trình (`test_pipeline`), chuẩn hóa (`test_normalize`), lược đồ và khớp cột (`test_schema`), API gộp file (`test_merge_api`), tích hợp API (`test_integration`), lõi và bảo mật (`test_core`), giao diện Playwright (`test_ui`). Đạt **11/11 bộ** cả khi chạy nhanh (`--fast`) và chạy toàn diện hiệu năng 50.000 dòng.

## Nhật ký sửa lỗi sau bản gd4.0
- gd4.1: sửa lỗi giao diện im lặng khi phiên làm việc trong bộ nhớ bị mất (máy chủ khởi động lại hoặc quá 2 giờ): thao tác thêm công thức, quy tắc, chuẩn hóa lúc đó không báo gì và gây lỗi JavaScript; nay hiện thông báo "Phiên làm việc đã hết hạn, hãy tải file lên lại." (có kiểm thử trong `tests/test_ui.py`).

## Giới hạn và phần chưa làm
- Bộ tính công thức chạy bằng Python (C++ chỉ làm đọc số/ngày, sắp xếp, phát hiện trùng, so sánh số). Lộ trình ghi "nếu phù hợp"; với 50.000 dòng mất vài giây nên chưa cần. Chưa tối ưu cho trên 100.000 dòng (xuất kèm kiểm tra độc lập 50.000 dòng khoảng 12 đến 22 giây).
- Chưa có xử lý theo khối (streaming/chunk) và tinh chỉnh bộ nhớ cho 500.000 dòng trở lên (thuộc giai đoạn 10: kiểm toán hiệu năng).
- Bước dịch cú pháp công thức và dịch quy tắc sang cây điều kiện dùng chung giữa bộ xử lý chính và bộ kiểm tra độc lập, nên lỗi ở bước đó không bị bắt.
- Điều kiện chưa so sánh cột với cột, chưa có biểu thức chính quy, chưa lồng nhóm điều kiện (một cấp, VÀ hoặc HOẶC, có phủ định từng điều kiện).
- Các loại biến đổi còn lại trong `OP_TYPES` (FILTER, SORT, FILL_MISSING, TYPE_CONVERT, MERGE_COLUMN, SPLIT_COLUMN), Smart Merge, mở rộng xuất file: thuộc các giai đoạn sau, chưa làm.
- Công thức cần dòng tiêu đề. Ngày giờ chỉ lấy phần ngày trong công thức.
- Đổi quy trình sẽ đặt lại các luật sắp xếp, tô màu, lọc, đánh dấu (vì vị trí cột thay đổi).
- Công thức ở bước sau đọc ô lỗi của công thức ở bước trước như chữ (mã lỗi), nên mã lỗi dây chuyền chỉ giữ nguyên trong cùng một nhóm công thức liền nhau.
