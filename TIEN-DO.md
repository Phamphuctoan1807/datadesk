# Tiến độ theo lộ trình (DataDesk_Development_Roadmap.md)

Phiên bản trong gói này: xem `VERSION` trong `server.py` (hiện ở góc trên giao diện và tại đường dẫn `/version`).

Trạng thái: **Giai đoạn 1, 2 và 3 đã xong theo tiêu chí nghiệm thu của lộ trình (mục 68 và 69), kèm các mục phụ của mục 3 đến 9, 44 đến 47, 50 đến 56, 59, 63 đến 67.**
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

## Kiểm thử (mục 63 đến 67)
`python tests/run_all.py` chạy 8 bộ: đơn vị, đáp án chuẩn (8 bộ dữ liệu mẫu trong `tests/golden` và `tests/datasets`), công thức (so sánh hai bộ tính trên 4.000 công thức ngẫu nhiên), quy tắc (3.000 bộ quy tắc ngẫu nhiên), quy trình, tích hợp qua API, lõi (hồi quy tính năng cũ, đăng nhập, khóa tạm) và giao diện thật bằng Chromium không đầu (cần Playwright, không có thì tự bỏ qua). Thêm `--fast` để bỏ phần đo hiệu năng 50.000 dòng. Đã chạy đạt cả khi có và khi không có bộ xử lý C++.

## Giới hạn và phần chưa làm
- Bộ tính công thức chạy bằng Python (C++ chỉ làm đọc số/ngày, sắp xếp, phát hiện trùng, so sánh số). Lộ trình ghi "nếu phù hợp"; với 50.000 dòng mất vài giây nên chưa cần. Chưa tối ưu cho trên 100.000 dòng (xuất kèm kiểm tra độc lập 50.000 dòng khoảng 12 đến 22 giây).
- Chưa có xử lý theo khối (streaming/chunk) và tinh chỉnh bộ nhớ cho 500.000 dòng trở lên (thuộc giai đoạn 10: kiểm toán hiệu năng).
- Bước dịch cú pháp công thức và dịch quy tắc sang cây điều kiện dùng chung giữa bộ xử lý chính và bộ kiểm tra độc lập, nên lỗi ở bước đó không bị bắt.
- Điều kiện chưa so sánh cột với cột, chưa có biểu thức chính quy, chưa lồng nhóm điều kiện (một cấp, VÀ hoặc HOẶC, có phủ định từng điều kiện).
- Các loại biến đổi còn lại trong `OP_TYPES` (FILTER, SORT, FILL_MISSING, NORMALIZE, ...), Smart Merge, mở rộng xuất file: thuộc các giai đoạn sau, chưa làm.
- Công thức cần dòng tiêu đề. Ngày giờ chỉ lấy phần ngày trong công thức.
- Đổi quy trình sẽ đặt lại các luật sắp xếp, tô màu, lọc, đánh dấu (vì vị trí cột thay đổi).
- Công thức ở bước sau đọc ô lỗi của công thức ở bước trước như chữ (mã lỗi), nên mã lỗi dây chuyền chỉ giữ nguyên trong cùng một nhóm công thức liền nhau.
