# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Phiên bản trong gói này: xem `VERSION` trong `server.py` (hiện ở góc trên giao diện và tại đường dẫn `/version`).

Trạng thái: **10/10 Giai đoạn bắt buộc cốt lõi đã hoàn thành 100%. Đang triển khai Giai đoạn C (Future Roadmap). Milestone C1 (Saved Workflow / Presets), Milestone C2 (Advanced Data Cleaning), và Milestone C3 (Data Quality Score) đã hoàn thành xuất sắc và đạt 100% kiểm thử.**

## Giai đoạn C: Lộ trình tương lai (Stage C - Future Roadmap)

### Milestone C1: Saved Workflow / Presets Engine & UI (Mục 74)
- **Module độc lập `preset_engine.py`:**
  - Lưu và nạp preset quy trình vào file an toàn `data/presets.json`.
  - Hỗ trợ đầy đủ nghiệp vụ: lưu mới, lấy chi tiết, danh sách, xóa, nhân bản.
  - Phân tích phụ thuộc cột trong preset: trích xuất cột từ công thức `[Cột]`, chuẩn hóa và quy tắc.
  - Kiểm tra tính tương thích giữa preset và cấu trúc bảng (`validate_preset_for_dataset`), tự động tìm kiếm cột tương ứng theo tên chuẩn hóa, cảnh báo các cột còn thiếu.
  - Thích ứng bước xử lý (`adapt_steps_with_mapping`): tự động viết lại tham chiếu cột khi áp dụng sang bảng có tên cột khác nhau.
  - Xuất & Nhập file JSON độc lập (`export_preset_json`, `import_preset_json`) để chia sẻ quy trình giữa các máy.
- **Tích hợp API và Giao diện:**
  - Bộ API `GET /api/preset/list`, `POST /api/preset/save`, `POST /api/preset/validate`, `POST /api/preset/apply`, `POST /api/preset/delete`, `POST /api/preset/export`, `POST /api/preset/import`.
  - Giao diện trực quan trong thẻ "Quy trình biến đổi": nút "💾 Lưu thành mẫu" và "📂 Mở mẫu có sẵn", modal danh sách preset, xem số bước, áp dụng quy trình, tải file JSON và tải file JSON lên.
  - Đã tích hợp bộ kiểm thử `test_preset.py` (6/6 bài test) vào `run_all.py`.

### Milestone C2: Advanced Data Cleaning Engine & UI (Mục 75)
- **Module độc lập `cleaning_engine.py`:**
  - **Chuẩn hóa văn bản chuyên sâu:** trim, gộp khoảng trắng thừa (`\s+`), Title Case, UPPERCASE, lowercase, Sentence case, Unicode NFC/NFD, loại bỏ ký tự vô hình/BOM/Zero-width space (`\u200B`, `\uFEFF`), loại bỏ dấu tiếng Việt chuẩn hóa ASCII.
  - **Chuẩn hóa số điện thoại:** Nhận diện 10 số đầu 03/05/07/08/09, đầu số quốc tế `+84`, `84`, `0084`, hỗ trợ đa định dạng hiển thị (`vn_standard`, `vn_grouped` 4-3-3, `e164`, `intl_grouped`, `national`).
  - **Chuẩn hóa Email:** trim, lowercase, loại bỏ ngoặc bao quanh `<user@domain>`, kiểm tra định dạng RFC, tự động sửa lỗi chính tả tên miền phổ biến (`@gmai.com`, `@gmial.com`, `@hotmial.com` -> `@gmail.com`, `@hotmail.com`).
  - **Chuẩn hóa Số, Tiền tệ, Phần trăm:** Tự động nhận diện dấu phân cách hàng nghìn / thập phân kiểu Việt Nam/Châu Âu (`1.234.567,89`) và Quốc tế (`1,234,567.89`), tách đơn vị tiền tệ (VND, đ, $, USD, EUR), chuẩn hóa tỷ lệ phần trăm.
  - **Tìm kiếm & Thay thế an toàn (Safe Find & Replace):** Hỗ trợ khớp chính xác (Exact), chứa chuỗi (Contains), biểu thức chính quy an toàn (Safe Regex kháng ReDoS, chặn lặp lồng nhau), xem trước (Preview) số ô khớp và mẫu thay thế trước khi thực thi.
  - **Quản lý trùng lặp nâng cao (Duplicate Management):** 3 chế độ nhận diện: Trùng chính xác (Exact), Trùng sau chuẩn hóa (Normalized), và Trùng mờ (Fuzzy Levenshtein kết hợp Token Sort Ratio với ngưỡng tương đồng tuỳ chọn 60% - 98%). Hỗ trợ 3 chiến lược: Giữ dòng đầu (Keep First), Giữ dòng cuối (Keep Last), Xóa toàn bộ (Remove All).
  - **Bộ kiểm tra đối chiếu độc lập `independent_cleaning_check`:** Xác minh bất biến số cột, bảo toàn cấu trúc dữ liệu và kiểm tra tính toàn vẹn.
- **Tích hợp API và Giao diện:**
  - Bộ API: `POST /api/clean/find_replace/preview`, `POST /api/clean/find_replace/apply`, `POST /api/clean/duplicates/detect`, `POST /api/clean/duplicates/remove`, `POST /api/clean/format/apply`.
  - Giao diện trực quan "Làm sạch chuyên sâu (Stage C - Future 2)": tab chuyển đổi tức thì Tìm & Thay thế, Lọc trùng lặp, Chuẩn hóa nhanh; hỗ trợ tạo bảng mới hoặc ghi đè an toàn kèm hoàn tác.
  - Đã tích hợp bộ kiểm thử `test_cleaning_engine.py` (10/10 bài test) vào `run_all.py`.

### Milestone C3: Data Quality Score Engine & UI (Mục 76)
- **Module độc lập `quality_engine.py`:**
  - **Tính điểm chất lượng toàn diện (0-100):** Tích hợp 4 trụ cột chất lượng chuẩn quốc tế:
    - **Completeness (30%):** Tỷ lệ ô có dữ liệu thực tế ($1 - \text{null\_ratio}$).
    - **Consistency (25%):** Tỷ lệ dữ liệu nhất quán kiểu (phát hiện ô chữ trong cột số, hỗn hợp kiểu).
    - **Validity (25%):** Độ hợp lệ định dạng nghiệp vụ (kiểm tra SĐT Việt Nam, Email RFC, dải số hợp lệ).
    - **Uniqueness (20%):** Độ duy nhất của các bản ghi ($1 - \text{duplicate\_ratio}$).
  - **Bảng giải trình điểm số chi tiết (Explainable Deductions):** Tuyệt đối không phán đoán mơ hồ; mỗi điểm trừ đều giải thích rõ: mục đánh giá, cột vi phạm, số dòng ảnh hưởng, lý do chi tiết và gợi ý khắc phục cụ thể.
  - **Bộ kiểm tra đối chiếu độc lập `independent_quality_check`:** Kiểm tra đối chiếu độc lập toán học đảm bảo tính chuẩn xác và phân loại trạng thái (SAFE / REVIEW_REQUIRED / UNSAFE).
- **Tích hợp API và Giao diện:**
  - Tuyến API `GET /api/quality/score` trả về điểm tổng thể, 4 chỉ số con và danh sách giải trình.
  - Giao diện Huy hiệu Chất lượng (Quality Banner) hiển thị điểm số hình tròn nổi bật ngay dưới phần Kết quả rà soát, kèm nút mở rộng xem toàn bộ bảng giải trình chi tiết.
  - Đã tích hợp bộ kiểm thử `test_quality_engine.py` (7/7 bài test) vào `run_all.py`.

### Milestone C4: Business Validation Rules Engine & UI (Mục 77)
- **Module độc lập `business_rules.py`:**
  - Thiết lập và đánh giá quy tắc nghiệp vụ/ràng buộc dữ liệu tùy chỉnh:
    - So sánh số với giá trị: [Tuổi] >= 18, [Số lượng] >= 0
    - So sánh giữa 2 cột: [Ngày kết thúc] >= [Ngày bắt đầu], [Giá bán] >= [Giá vốn]
    - Ràng buộc định dạng: Email hợp lệ RFC, Số điện thoại Việt Nam hợp lệ, Không để trống
    - Ràng buộc tính duy nhất: Mã định danh không được trùng lặp
  - Thống kê tỷ lệ dòng hợp lệ (%), số dòng vi phạm, và danh sách vi phạm chi tiết từng dòng (Click to inspect actual value vs reason).
  - Bộ kiểm tra đối chiếu độc lập `independent_rules_check`.
- **Tích hợp API và Giao diện:**
  - Tuyến API `POST /api/business_rules/validate`.
  - Giao diện thẻ "Quy tắc kiểm định nghiệp vụ": thêm/xóa quy tắc linh hoạt, nút kiểm tra quy tắc, huy hiệu xanh/đỏ thống kê và bảng chi tiết vi phạm.
  - Đã tích hợp bộ kiểm thử `test_business_rules.py` (5/5 bài test) vào `run_all.py`.

### Milestone C5: Data Lineage & Explainability Engine (Mục 78 & 80)
- **Module độc lập `lineage_engine.py`:**
  - Theo vết nguồn gốc dữ liệu (Data Lineage) và giải trình biến đổi (Explainability) tới từng ô:
    - Giá trị hiện tại (Current Value)
    - Nguồn gốc gốc rễ: File gốc, Sheet, Dòng, Cột
    - Chuỗi biến đổi (Lineage Chain): Gốc -> Chuẩn hóa -> Công thức -> Quy tắc điều kiện -> Merge
    - Giải trình chi tiết lý do thay đổi giá trị (Explainability).
  - Tự động suy diễn chuỗi biến đổi dựa trên Pipeline steps khi không có seed log.
- **Tích hợp API:**
  - Tuyến API `GET /api/lineage/cell` phục vụ tính năng Cyber Eye / Dossier trace.
  - Đã tích hợp bộ kiểm thử `test_lineage.py` (3/3 bài test) vào `run_all.py`.

### Milestone C6: Version History Engine (Mục 79)
- **Module độc lập `version_engine.py`:**
  - Quản lý lịch sử phiên bản của dataset theo các mốc quan trọng (Original, Cleaned, Merged, Transformed, Final).
  - Lưu trữ snapshot an toàn kèm nhãn phiên bản, số dòng, số cột, thời gian tạo.
  - Hỗ trợ so sánh (Compare) sự khác biệt giữa hai phiên bản bất kỳ (cột thêm/bớt, biến động dòng, mẫu ô thay đổi).
  - Hỗ trợ khôi phục (Restore) về phiên bản trước đó kèm lưu vết Undo.
  - Bộ kiểm tra đối chiếu độc lập `independent_version_check`.
- **Tích hợp API:**
  - Tuyến API `POST /api/version/create`, `GET /api/version/list`, `POST /api/version/compare`, `POST /api/version/restore`.
  - Đã tích hợp bộ kiểm thử `test_version_engine.py` (2/2 bài test) vào `run_all.py`.

### Milestone C7: Quick Analysis & Dashboard Engine (Mục 81)
- **Module độc lập `analysis_engine.py`:**
  - Tự động nhận diện kiểu cột: numeric, categorical, date.
  - Tính toán các chỉ số KPI tổng hợp: Tổng số bản ghi, Tổng (Sum), Trung bình (Avg), Lớn nhất (Max), Nhỏ nhất (Min).
  - Tự động sinh cấu hình biểu đồ thông minh:
    - Bar chart: Top nhóm, số lượng theo phân loại (e.g. Doanh thu theo sản phẩm)
    - Line chart: Xu hướng theo thời gian (e.g. Doanh thu theo ngày/tháng)
    - Pie / Donut chart: Cơ cấu phân loại
    - Histogram: Phân bố tần suất giá trị số
  - Bộ kiểm tra đối chiếu độc lập `independent_analysis_check`.
- **Tích hợp API:**
  - Tuyến API `GET /api/analysis/dashboard`.
  - Đã tích hợp bộ kiểm thử `test_analysis_engine.py` (2/2 bài test) vào `run_all.py`.

### Milestone C8: Automation & Batch Processing Engine (Mục 82, 84, 85)
- **Module độc lập `automation_engine.py`:**
  - **AI Workflow Planner (Mục 82):** Chuyển đổi mô tả yêu cầu tự nhiên (tiếng Việt) thành kế hoạch các bước tất định (Merge, Deduplicate, Normalize, Formula, Conditional, Export).
  - **Batch Processing (Mục 85):** Thực thi một Preset trên hàng loạt file với báo cáo tổng hợp phân loại Succeeded, Review Required, Failed.
  - **Scheduled Processing (Mục 84):** Quản lý lịch chạy tự động quy trình định kỳ (daily, weekly, on_new_file).
  - Bộ kiểm tra đối chiếu độc lập `independent_automation_check`.
- **Tích hợp API:**
  - Tuyến API `POST /api/automation/plan`, `POST /api/automation/batch`, `POST /api/automation/schedule`, `GET /api/automation/schedules`.
  - Đã tích hợp bộ kiểm thử `test_automation_engine.py` (4/4 bài test) vào `run_all.py`.

### Milestone C9: Multi-User & Role-Based Access Control (RBAC) Engine (Mục 86)
- **Module độc lập `rbac_engine.py`:**
  - Hệ thống tài khoản người dùng và phân quyền chi tiết với 4 vai trò chuẩn:
    - ADMIN: Toàn quyền hệ thống, quản lý người dùng, cài đặt hệ thống.
    - MANAGER: Phê duyệt quy trình, duyệt xung đột (Review conflicts), xử lý trùng lặp.
    - EDITOR: Tải file, biến đổi, làm sạch, gộp bảng, xuất file.
    - VIEWER: Xem dữ liệu, xem trước, tải báo cáo/file đã duyệt.
  - Cơ chế băm mật khẩu bảo mật PBKDF2-HMAC-SHA256 kết hợp Salt ngẫu nhiên.
  - Bộ kiểm tra đối chiếu độc lập `independent_rbac_check`.
- **Tích hợp API:**
  - Tuyến API `GET /api/auth/users`, `POST /api/auth/users`, `POST /api/auth/login_user`.
  - Đã tích hợp bộ kiểm thử `test_rbac_engine.py` (3/3 bài test) vào `run_all.py`.

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
`python tests/run_all.py` chạy toàn bộ **24 bộ kiểm thử**:
1. `test_units`: kiểm thử đơn vị
2. `test_golden`: kiểm thử đáp án chuẩn 12 bộ dữ liệu
3. `test_formula`: kiểm thử 4.000 công thức và đối chiếu 2 bộ tính
4. `test_rules`: kiểm thử 3.000 bộ quy tắc điều kiện ngẫu nhiên
5. `test_pipeline`: kiểm thử quy trình biến đổi đa bước
6. `test_preset`: kiểm thử bộ máy lưu trữ và quản lý preset workflow (Stage C - Future 1)
7. `test_cleaning_engine`: kiểm thử bộ máy làm sạch chuyên sâu (Stage C - Future 2)
8. `test_quality_engine`: kiểm thử bộ máy chấm điểm chất lượng dữ liệu (Stage C - Future 3)
9. `test_business_rules`: kiểm thử bộ quy tắc kiểm định nghiệp vụ (Stage C - Future 4)
10. `test_lineage`: kiểm thử theo vết nguồn gốc và giải trình ô (Stage C - Future 5 & 7)
11. `test_version_engine`: kiểm thử quản lý lịch sử phiên bản (Stage C - Future 6)
12. `test_analysis_engine`: kiểm thử phân tích và bảng biểu đồ thông minh (Stage C - Future 8)
13. `test_automation_engine`: kiểm thử tự động hóa, xử lý hàng loạt và lập lịch (Stage C - Future 9, 11, 12)
14. `test_rbac_engine`: kiểm thử phân quyền người dùng theo vai trò RBAC (Stage C - Future 13)
15. `test_normalize`: kiểm thử 7 loại chuẩn hóa dữ liệu
16. `test_schema`: kiểm thử nhận diện schema, khóa và khớp cột
17. `test_merge_api`: kiểm thử API gộp file đa file
18. `test_merge_engine`: kiểm thử bộ máy so khớp và thực thi gộp bảng (UNION & JOIN)
19. `test_export`: kiểm thử xuất file đa định dạng (XLSX, CSV, TSV, JSON)
20. `test_validation`: kiểm thử bộ máy kiểm định toàn diện (dung sai số, hao hụt, duplicate)
21. `test_audit`: kiểm thử kiểm toán bảo mật và hiệu năng 50.000 dòng
22. `test_integration`: kiểm thử tích hợp toàn bộ luồng từ upload đến export
23. `test_core`: kiểm thử cốt lõi bộ xử lý C++/Python
24. `test_ui`: kiểm thử giao diện Playwright (tự động bỏ qua nếu chưa cài browser)

Kết quả hiện tại: **Toàn bộ 24/24 bộ kiểm thử ĐẠT 100% SẠCH LỖI**.

## Tối ưu hóa & Hoàn thiện tương tác giao diện người dùng (UI Interaction Polish)
- **Làm sạch chuyên sâu (`card-cleaning`):**
  - Khắc phục triệt để lỗi mất dữ liệu ô nhập (Find/Replace text) khi bấm "Xem trước" hoặc chuyển tab nhờ lưu trữ hai chiều (`input`/`change`) vào `ST.clean`.
  - Khắc phục thanh trượt ngưỡng tương đồng (`clean-dup-thresh`): cập nhật nhãn phần trăm thời gian thực và đồng bộ vào tham số quét trùng lặp mờ.
  - Bổ sung tùy chọn chi tiết theo ngữ cảnh cho Chuẩn hóa nhanh: Chữ hoa đầu từ/In hoa/In thường/Bỏ dấu tiếng Việt, định dạng số điện thoại chuẩn VN/nhóm 4-3-3/E.164, sửa typo email.
- **Quy tắc kiểm định nghiệp vụ (`card-business-rules`):**
  - Khắc phục lỗi ẩn cột so sánh thứ 2 khi chọn loại quy tắc `compare_columns`: tự động chuyển đổi hiển thị động giữa ô giá trị và dropdown cột mục tiêu.
  - Ẩn các trường không cần thiết khi kiểm tra Email/SĐT/Không trống/Duy nhất để giao diện gọn gàng, tránh nhầm lẫn.
- **Không gian công nghệ Node Graph & Con Mắt Cyber Eye (`#tech-space`):**
  - Chống xung đột kéo thả: ngăn chặn thao tác rê chuột vào nút phóng to (`col-expand-btn`), ô tìm kiếm cột hoặc nút đóng Dock kích hoạt nhầm thao tác kéo node.
  - Sửa chỉ số hàng tuyệt đối khi đánh dấu hồ sơ đối tượng từ Dossier (`(ST.grid.start||0) + rowIdx`), đảm bảo đánh dấu chính xác khi ở trang phân trang > 1.
  - Tối ưu hóa quản lý sự kiện chuột: loại bỏ hiện tượng gắn trùng lặp các listener `mousemove`/`mouseup` trên `window` sau mỗi lần render.
  - Bổ sung đóng modal linh hoạt: nhấp ra vùng tối (backdrop) hoặc nhấn phím `Escape` để đóng ngay Dossier Modal và Preset Modal.
- **Tích hợp giao diện người dùng cho các tính năng Stage C mới:**
  - Bổ sung Card Quản lý phiên bản dữ liệu (`card-versioning`): Tạo bản chụp snapshot kèm tên/mô tả, xem danh sách và khôi phục (Restore) tức thì.
  - Bổ sung Card Phân tích thống kê & Báo cáo nhanh (`card-analysis`): Chạy phân tích tự động, hiển thị các thẻ KPI (Tổng, Trung bình, Min, Max), nhận diện kiểu cột.
  - Bổ sung Card Truy vết nguồn gốc (`card-lineage`): Tra cứu nguồn gốc từng ô dữ liệu qua toàn bộ các bước biến đổi trong quy trình.


## 🦾 Nâng cấp Siêu Giao diện Không gian Công nghệ: J.A.R.V.I.S. Hologram Edition
Đã hoàn thành xuất sắc việc hiện thực hóa toàn bộ bản thiết kế không gian tương tác vũ trụ dữ liệu 3D/2.5D (J.A.R.V.I.S. Hologram Canvas) lấy cảm hứng từ Iron Man HUD, biến mọi tính năng trong Roadmap thành các module điều khiển tương tác trực quan:

1. **Ngôn ngữ Thiết kế Stark HUD & Bảng Màu Quang Học:**
   - **Bioluminescent Palette:** `#030712` Deep Void Canvas kết hợp `#00f0ff` (Arc Cyan), `#2457f5` (Tesseract Blue), `#a855f7` (Quantum Purple), `#f59e0b` (Amber Synapse), `#ff2a5f` (Crimson Alert), `#00ff9d` (Emerald Verified).
   - **Chamfered Tech Borders:** Khung vát góc $45^\circ$ (`clip-path: polygon(...)`) trên toàn bộ Node cột, Lõi trung tâm, Thanh HUD, Bản đồ chiến thuật và các Modal.
   - **Reticle Corner Brackets & Scanlines:** Vạch chia độ viền ở 4 góc và hiệu ứng quét sáng scanline quang học.
   - **Micro-Telemetry HUD Banner:** Hiển thị tọa độ chuột thời gian thực $(X, Y)$, bộ đếm FPS ($60.0$), số lượng cáp năng lượng hoạt động và trạng thái động cơ `C++ v2026 Core | Python Validator Ready | Status: NOMINAL`.
   - **Web Audio Synthesizer (`AudioFX`):** Xây dựng bộ tổng hợp âm thanh thuần bằng Web Audio API của trình duyệt (không tải bất kỳ file MP3 ngoài nào) với các hiệu ứng `beep` (tần số cao), `hum` (nạp điện cáp), `lock` (khóa ngàm cơ khí), `scan` (quét laser), `shield` (hợp âm kiểm chứng kép) và `alarm` (báo động xung đột). Đi kèm công tắc bật/tắt âm thanh `SFX BẬT/TẮT` có ghi nhớ trạng thái.

2. **Lò Phản Ứng Hồ Quang (Arc Reactor Core) & Hố Đen Hút File:**
   - Trước khi tải file, vùng kéo thả `#drop` hiển thị Lò phản ứng gồm 3 vòng tròn đồng tâm xoay ngược chiều kèm các ký hiệu toán học ($\sum, \Delta, \pi, \infty, \lambda, 01$).
   - Khi kéo file lại gần tâm: Lò phản ứng tăng tốc độ xoay gấp 3 lần, phát sáng rực rỡ và tạo lực hút từ trường kéo các hạt số liệu xung quanh tụ về tâm rơi.
   - Khi thả file: Kích hoạt **J.A.R.V.I.S. Diagnostic Bubble 3 lớp** quét radar $360^\circ$ và hiệu ứng giải mã ký tự Matrix: `[ĐANG ĐỌC CẤU TRÚC VẬT LÝ...]` ➔ `[BỘ XỬ LÝ C++ ĐANG LẬP CHỈ MỤC...]` ➔ `[HOÀN TẤT RÀ SOÁT]`.

3. **Node Cột Không Bao Giờ Đứt Dây & Vật Lý Nghiêng 3D (Elastic Streams & 3D Tilt):**
   - Trạng thái thu gọn: Hiển thị viên nang công nghệ với Tên cột, Kiểu dữ liệu và Huy hiệu tỷ lệ giá trị duy nhất `% Unique Ratio` (Mục 13).
   - Trạng thái mở rộng: Trượt dài xuống theo chiều dọc với hiệu ứng xuất hiện tuần tự các phần tử `[STT] ── [Tên Cột] ── [Giá trị]`.
   - Kéo thả vật lý nghiêng 3D: Khi nắm kéo cột đi khắp không gian, cột tự động nghiêng theo gia tốc kéo (`perspective(600px) rotateX(...) rotateY(...) scale(1.04)`) và nảy đàn hồi về trạng thái phẳng khi thả chuột.
   - Đường dây điện SVG Bezier năng lượng nối từ Lõi file trung tâm tới ổ cắm cột tự động uốn cong mềm mại với xung điện chạy rần rật, tuyệt đối không bao giờ đứt dây.

4. **Công Cụ "Con Mắt Thần" (Cyber-Eye Inspector) & "Kính Lúp Lượng Tử" (Quantum Magnifier):**
   - **Cyber-Eye:** Kéo thả hoặc bấm để khóa ngàm hít từ tính vào đầu cột bất kỳ, trượt ra thanh quét Laser. Gõ ký tự tới đâu, các dòng không khớp sẽ thu gọn chiều cao về $0$ và tan biến dần dần theo từng phím gõ.
   - **Quantum Magnifier & Cross-Column Synapse:** Nhập từ khóa truy tìm, các tia điện màu Vàng Hoàng Kim (`#f59e0b`) tự động phóng xuyên không gian nối các ô khớp nhau giữa các cột đang mở. Bấm `[TRUY TÌM]` triệu hồi **Bảng Hồ Sơ 3D (3D Entity Dossier)** liệt kê chi tiết mọi thuộc tính và lịch sử nguồn gốc.

5. **Bộ Module Thí Nghiệm & Đồ Chơi Công Nghệ (Iron Man Gadgets):**
   - **Lò Rèn Công Thức (Formula Forge):** Đấu nối cáp dữ liệu từ 2 cột nguồn vào ổ cắm, xoay Vòng đĩa toán tử (`*`, `+`, `-`, `/`, `CONCAT`, `ROUND`, `IF`) kèm cảnh báo tự động khi chia cho 0 (`DIV_ZERO`). Bấm `[RÈN CÔNG THỨC]` tạo ngay cột mới vào `ST.formulas` và bảng dữ liệu.
   - **Trạm Phân Luồng Logic (Prism Logic Gate):** Thiết kế lăng kính quang học tách luồng dữ liệu thành 2 nhánh `THEN` (xanh lục) và `ELSE` (tím), cập nhật thời gian thực số lượng dòng thỏa mãn và kích hoạt quy tắc vào `ST.rules`.
   - **Buồng Khử Nhiễm Dữ Liệu (Decontamination Chamber):** Tùy chọn chuẩn hóa Họ tên, Số điện thoại, Khoảng trắng thừa và ô trống giả. Bấm kích hoạt sẽ phóng **Tia Laser Quét Dọc Không Gian** làm sạch dữ liệu và hiện thông báo Hologram Toast.
   - **Trục Thời Gian Năng Lượng (Time-Stream Conduit):** Thanh trục năng lượng ở đáy màn hình hiển thị toàn bộ tiến trình biến đổi, tích hợp đèn báo phụ thuộc vòng (`CIRCULAR DEPENDENCY`) và nút Hoàn tác/Làm lại trực tiếp.
   - **Khiên Kiểm Chứng Độc Lập (Twin-Engine Verification Shield):** Khi bấm `[Xuất file]`, hiển thị màn hình 2 Lõi Động Cơ Đối Xứng (**C++ Core** và **Python Validator**) chạy qua danh sách kiểm tra đối chiếu số dòng, số cột, sai số từng ô ($< 10^{-9}$), bảo toàn màu sắc và đóng dấu chứng nhận `100% SAFE - VERIFIED` trước khi tải file.

6. **Các Tiện Ích Bổ Trợ (Sci-Fi Utilities):**
   - **Bản Đồ Radar Thu Nhỏ (Tactical Minimap):** Hiển thị ở góc dưới bên phải với tọa độ Lõi trung tâm, các Node cột và khung nhìn camera; hỗ trợ bấm vào minimap để lia nhanh không gian.
   - **Nút "Dàn Đội Hình" (Auto-Formation Layout):** Một chạm đưa toàn bộ các cột bay về xếp theo hình **Vòng Cung (Arc Formation)** hoặc **Ma Trận Lưới (Matrix Grid)** trật tự.
   - **Trợ Lý Lệnh Nhanh J.A.R.V.I.S. (`Ctrl+K`):** Thanh lệnh nổi ở đỉnh màn hình với sóng âm thanh Hologram và các chip lệnh gợi ý tự động.
   - **Chuyển Đổi Không Gian "Nghiêm Túc" ⟷ "Công Nghệ" (Dimension Shift):** Gạt công tắc chuyển đổi mượt mà giữa chế độ bảng biểu văn phòng truyền thống và không gian Hologram, đồng bộ dữ liệu `ST` tuyệt đối 100%.
