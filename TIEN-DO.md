# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Trạng thái: **Giai đoạn 1, 2 và 3 đã làm phần cốt lõi. Giai đoạn 2 chưa đạt đủ Definition of Done (xem mục "Chưa có"); Giai đoạn 3 được làm theo xác nhận "Tiếp tục" của chủ dự án. Chưa có giai đoạn nào được thử trên trình duyệt thật hay trên Render.**

## Giai đoạn 1: Data Model (xong phần nền)
- Dữ liệu gốc bất biến + nhật ký thao tác (`rec["ops"]`) + bảng dẫn xuất (`get_table`). Không bao giờ sửa dữ liệu gốc (có test).
- Schema luật: `id, type, target, expression, enabled`. Enum `OP_TYPES` đã khai báo đủ 15 loại, mới chạy loại `FORMULA`.
- Phản hồi thống nhất `success / warnings / errors / stats / data` cho các API mới.
- Hoàn tác / làm lại, đồ thị phụ thuộc giữa các công thức.

## Giai đoạn 2: Formula Engine
Đã có:
- Toán tử `+ - * / %`, nối chuỗi `&`, so sánh `= <> > < >= <=`.
- Toán: ABS, ROUND (làm tròn nửa lên), CEIL, FLOOR, MIN, MAX, SUM, AVERAGE, POWER, SQRT.
- Chuỗi: CONCAT, LEFT, RIGHT, MID, LEN, TRIM, LOWER, UPPER, REPLACE, SUBSTITUTE.
- Điều kiện: IF (tính lười, nên `IF(B=0,0,A/B)` không lỗi), AND, OR, NOT, ISEMPTY (thêm cho tiện xử lý ô trống).
- Ngày: YEAR, MONTH, DAY, ngày + N, ngày - N, ngày - ngày.
- Mã lỗi, không crash: ERROR_DIV_ZERO, ERROR_COLUMN, ERROR_SYNTAX, ERROR_TYPE, ERROR_DATE, ERROR_OVERFLOW, ERROR_NULL (ô lỗi hiện mã lỗi, không bị tính thành 0).
- Phát hiện vòng phụ thuộc; tự tính cột phụ thuộc theo đúng thứ tự.
- Giao diện: ô tên cột, ô công thức, chèn cột/toán tử/hàm, xem trước, sửa, xóa, bật tắt, đổi thứ tự, hoàn tác, làm lại.
- An toàn: DSL tự viết (không eval/exec), giới hạn độ dài 1.000 ký tự và độ sâu.
- Kiểm tra độc lập: sau khi xuất, đọc lại file và tính lại từng ô công thức bằng bộ tính Decimal riêng.

Chưa có (đúng theo lộ trình thì làm sau):
- Trợ lý AI viết công thức (mục 47), bộ tính hàng loạt bằng C++ (hiện tính bằng Python).
- `/api/transform/preview`, `/api/transform/apply` (chỉ có phần công thức), merge, export mở rộng.
- Trạng thái `SAFE / REVIEW_REQUIRED / UNSAFE`, nhật ký audit, provenance từng ô.

Giới hạn đã biết:
- Bộ tính chính và bộ kiểm tra dùng chung bước phân tích cú pháp (tách chuỗi thành cây), nên lỗi ở bước này không bị bắt bởi bước kiểm tra.
- Công thức cần dòng tiêu đề. Khi đang có công thức, ô "dòng đầu là tiêu đề" bị khóa.
- Ngày giờ chỉ lấy phần ngày trong công thức.
- Đổi công thức sẽ đặt lại luật sắp xếp, tô màu, lọc, đánh dấu (vì vị trí cột mới thay đổi).
- Tốc độ (Python): khoảng 10 giây cho 50.000 dòng với 3 công thức (xuất + kiểm tra độc lập). Chưa tối ưu cho trên 100.000 dòng.

## Giai đoạn 3: Quy tắc điều kiện (NẾU ... THÌ ... NGƯỢC LẠI ...)
Đã có:
- Điều kiện: =, khác, >, <, >=, <=, chứa, bắt đầu bằng, kết thúc bằng, để trống, không trống, bị trùng, duy nhất, thuộc danh sách, không thuộc danh sách (danh sách cách nhau bằng dấu `;`). Nhiều điều kiện nối bằng VÀ hoặc HOẶC, mỗi điều kiện có thể phủ định (NOT).
- Điều kiện có kiểu dữ liệu (số so như số, ngày so như ngày), dùng chung bộ tính của Formula Engine. Ô trống: "khác" và "không thuộc" là đúng, các phép còn lại là sai.
- Hành động ở nhánh THÌ và NGƯỢC LẠI (mỗi nhánh tối đa 6): điền hoặc ghi đè giá trị (chữ hoặc số, gõ tên mới để tạo cột), xóa dữ liệu, thay thế chữ, tô màu (cả dòng hoặc một ô), đánh dấu bằng nhãn (nối vào nhãn cũ, không lặp).
- Chạy tuần tự từ trên xuống: quy tắc sau thấy kết quả của quy tắc trước (kể cả cột do quy tắc trước tạo). Điều kiện của một quy tắc được tính trước khi quy tắc đó chạy, nên không phụ thuộc thứ tự dòng.
- Dòng không đánh giá được điều kiện (ví dụ ô chữ trong cột số) không chạy THÌ cũng không chạy NGƯỢC LẠI, được đếm và cảnh báo để người dùng kiểm tra.
- Xem trước (số dòng khớp, số ô thay đổi, cột mới sẽ tạo, trước → sau), cảnh báo ghi đè và **bắt xác nhận khi ghi đè ô đang có dữ liệu**. Sửa, xóa, bật tắt, đổi thứ tự, hoàn tác, làm lại.
- Không ghi đè cột công thức (báo PROTECTED_COLUMN). Bảng gốc không bao giờ bị sửa (có test).
- Kiểm tra độc lập: chạy lại toàn bộ chuỗi quy tắc từ dữ liệu gốc bằng bộ tính Decimal riêng, so với giá trị và màu đọc lại từ file xuất.

Giới hạn đã biết của Giai đoạn 3:
- Bước dịch quy tắc sang cây điều kiện dùng chung giữa bộ xử lý chính và bộ kiểm tra độc lập, nên lỗi ở bước dịch không bị bước kiểm tra bắt.
- Công thức chạy trước quy tắc: công thức không dùng được cột do quy tắc tạo hoặc giá trị quy tắc đã ghi đè.
- Chưa so sánh cột với cột, chưa có biểu thức chính quy (regex), chưa lồng nhóm điều kiện (chỉ VÀ hoặc HOẶC một cấp, có NOT từng điều kiện).
- "Đưa vào danh sách cần kiểm tra" hiện làm bằng hành động đánh dấu (nhãn ghi vào một cột), chưa có danh sách riêng.
- Giá trị so sánh số đọc theo quy ước của trang (ví dụ `1.234` hiểu là 1234, cách đọc số kiểu Việt Nam).
- Chậm hơn công thức: 50.000 dòng, 3 quy tắc mất khoảng 4 giây để áp dụng và khoảng 20 giây để xuất kèm kiểm tra độc lập. Chưa tối ưu cho trên 100.000 dòng.

## Chạy kiểm thử (từ thư mục dự án)
```
python tests/test_formula.py       # đơn vị + so sánh hai bộ tính trên 4.000 công thức ngẫu nhiên
python tests/test_integration.py   # qua API: áp dụng, xuất, hoàn tác, vòng phụ thuộc, hiệu năng 50.000 dòng
python tests/test_rules.py         # quy tắc điều kiện: đơn vị, API, so sánh hai bộ tính trên 3.000 bộ quy tắc ngẫu nhiên, hiệu năng
python tests/test_core.py          # hồi quy tính năng cũ (đọc kết quả in ra)
```
(Cần `pip install -r requirements.txt`. Biên dịch C++ trước thì chạy cả đường C++.)

## Bước tiếp theo theo lộ trình
Giai đoạn 4 theo lộ trình, sau khi bạn dùng thử Giai đoạn 2 và 3 trên dữ liệu thật và xác nhận.
