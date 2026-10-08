# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Trạng thái: **Giai đoạn 1 và 2 đã làm phần cốt lõi. Chưa đạt Definition of Done của Giai đoạn 2, nên chưa được sang Giai đoạn 3.**

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

## Chạy kiểm thử (từ thư mục dự án)
```
python tests/test_formula.py       # đơn vị + so sánh hai bộ tính trên 4.000 công thức ngẫu nhiên
python tests/test_integration.py   # qua API: áp dụng, xuất, hoàn tác, vòng phụ thuộc, hiệu năng 50.000 dòng
python tests/test_core.py          # hồi quy tính năng cũ (đọc kết quả in ra)
```
(Cần `pip install -r requirements.txt`. Biên dịch C++ trước thì chạy cả đường C++.)

## Bước tiếp theo theo lộ trình
Giai đoạn 3: Quy tắc điều kiện (WHEN ... THEN ...), sau khi bạn xác nhận Giai đoạn 2.
