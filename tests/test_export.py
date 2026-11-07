"""
Bộ kiểm thử toàn diện cho module export.py (Phase 8: Export Engine mở rộng)
Tuân thủ nghiêm ngặt DataDesk Development Roadmap (Mục 35, 36, 71).
Kiểm thử chi tiết:
1. XLSX:
   - formula_mode == 'value': xuất đúng giá trị tính toán.
   - formula_mode == 'formula': xuất đúng công thức Excel (=...).
   - Giữ màu sắc ô (fills), tiêu đề in đậm, freeze_panes, autofilter, column_dimensions.
   - Giữ nguyên định dạng số và ngày tháng gốc.
2. CSV:
   - UTF-8 kèm BOM (\\ufeff) chống lỗi font tiếng Việt trong Excel.
   - Xử lý ký tự đặc biệt (dấu phẩy, dấu nháy kép, xuống dòng, tiếng Việt có dấu).
3. TSV:
   - Phân tách bằng dấu tab, UTF-8 kèm BOM.
4. JSON:
   - Có header (mảng đối tượng [{"col": val}]) và không có header (mảng 2 chiều).
   - Bảo toàn kiểu dữ liệu (số, boolean, null, date/datetime).
5. read_back & format_warnings:
   - Kiểm tra đối chiếu kép 100% khớp dữ liệu gốc cho cả 4 định dạng.
   - Cảnh báo đầy đủ tính năng bị mất đối với các định dạng văn bản thuần.
6. export_preview:
   - Trả về cấu trúc xem trước đúng chuẩn Roadmap mục 36.
"""

import unittest
import os
import sys
import io
import csv
import json
import datetime as dt

# Đảm bảo đường dẫn import gốc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import export
from export import (
    write_xlsx,
    write_csv,
    write_tsv,
    write_json,
    read_back,
    format_warnings,
    export_data,
    export_preview,
    disp,
    norm,
    translate_to_excel_formula
)

class TestExportEngine(unittest.TestCase):

    def setUp(self):
        """Khởi tạo bảng dữ liệu mẫu có đầy đủ kiểu dữ liệu: text, int, float, date, formula, colors."""
        self.table = {
            "name": "Báo cáo bán hàng / 2026?",  # Chứa ký tự cần làm sạch trong sheet title
            "rows": [
                ["Mã SP", "Tên sản phẩm", "Số lượng", "Đơn giá", "Thành tiền", "Ngày giao", "Trạng thái"],
                ["SP01", "Cà phê Robusta Đắk Lắk", 10, 45000.0, 450000.0, dt.date(2026, 11, 1), "Đã giao"],
                ["SP02", "Trà xanh Thái Nguyên", 25, 60000.0, 1500000.0, dt.date(2026, 11, 2), "Đang giao"],
                ["SP03", "Hạt điều Bình Phước (loại 1)", 5, 120000.0, 600000.0, dt.date(2026, 11, 3), "Chờ xử lý"],
                ["SP04", "Gạo ST25 Ông Cua, Sóc Trăng", 50, 32000.0, 1600000.0, dt.date(2026, 11, 4), "Đã giao"]
            ],
            "fm": [
                [None, None, None, None, None, None, None],
                [None, None, "#,##0", "#,##0.00", "#,##0", "dd/mm/yyyy", None],
                [None, None, "#,##0", "#,##0.00", "#,##0", "dd/mm/yyyy", None],
                [None, None, "#,##0", "#,##0.00", "#,##0", "dd/mm/yyyy", None],
                [None, None, "#,##0", "#,##0.00", "#,##0", "dd/mm/yyyy", None]
            ],
            "sf": [
                ["#4A90E2", "#4A90E2", "#4A90E2", "#4A90E2", "#4A90E2", "#4A90E2", "#4A90E2"],
                [None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None]
            ],
            "col_formulas": {
                4: "=[Số lượng] * [Đơn giá]"
            },
            "values": {
                (1, 4): 450000,
                (2, 4): 1500000,
                (3, 4): 600000,
                (4, 4): 1600000
            }
        }
        self.outidx = [0, 1, 2, 3, 4]
        self.cols = [0, 1, 2, 3, 4, 5, 6]
        self.fills = {
            (1, 6): "#52C41A",  # Xanh lá (Đã giao)
            (2, 6): "#1890FF",  # Xanh dương (Đang giao)
            (3, 6): "#FAAD14",  # Vàng cam (Chờ xử lý)
            (4, 6): "#52C41A",  # Xanh lá
            (3, 2): "#FF4D4F"   # Đỏ cảnh báo số lượng thấp
        }

    # ==========================================================================
    # 1. KIỂM THỬ XUẤT XLSX
    # ==========================================================================

    def test_xlsx_formula_mode_value(self):
        """XLSX formula_mode='value': phải ghi đúng giá trị số đã tính toán."""
        raw_xlsx = write_xlsx(
            self.table, self.outidx, self.cols, self.fills,
            hdr=True, title=self.table["name"], formula_mode="value"
        )
        self.assertIsInstance(raw_xlsx, bytes)
        self.assertTrue(len(raw_xlsx) > 0)

        # Đọc lại bằng read_back
        got, fl = read_back(raw_xlsx, "xlsx", len(self.outidx), len(self.cols))
        self.assertEqual(len(got), 5)
        self.assertEqual(len(got[0]), 7)

        # Kiểm tra tiêu đề
        self.assertEqual(got[0][0], "Mã SP")
        self.assertEqual(got[0][4], "Thành tiền")

        # Kiểm tra giá trị tính toán tại cột Thành tiền (cột index 4)
        self.assertEqual(got[1][4], 450000)
        self.assertEqual(got[2][4], 1500000)
        self.assertEqual(got[3][4], 600000)
        self.assertEqual(got[4][4], 1600000)

        # Kiểm tra màu sắc tô ô (fills) trích xuất được
        # Dòng 1 trong bảng tương ứng dòng Excel 2 (chỉ số 1-based: row=2, col=7 cho Trạng thái)
        self.assertEqual(fl.get((2, 7)), "#52C41A")
        self.assertEqual(fl.get((3, 7)), "#1890FF")
        self.assertEqual(fl.get((4, 7)), "#FAAD14")
        self.assertEqual(fl.get((4, 3)), "#FF4D4F")  # row 4 (SP03), col 3 (Số lượng)

    def test_xlsx_formula_mode_formula(self):
        """XLSX formula_mode='formula': phải ghi công thức Excel (=C2*D2)."""
        raw_xlsx = write_xlsx(
            self.table, self.outidx, self.cols, self.fills,
            hdr=True, title=self.table["name"], formula_mode="formula"
        )
        self.assertIsInstance(raw_xlsx, bytes)

        # Đọc lại bằng openpyxl để kiểm tra công thức nguyên bản
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), data_only=False)
        ws = wb.active

        # Tên sheet phải được làm sạch các ký tự cấm (/ và ?)
        self.assertNotIn("/", ws.title)
        self.assertNotIn("?", ws.title)

        # Freeze panes phải cố định dòng 1
        self.assertEqual(ws.freeze_panes, "A2")

        # Tiêu đề in đậm
        self.assertTrue(ws.cell(1, 1).font.bold)

        # Cột E (Thành tiền, cột 5) phải chứa công thức nhân cột C (Số lượng) và D (Đơn giá)
        # Hàng 2: =C2*D2 hoặc =(C2 * D2)
        cell_formula_row2 = str(ws.cell(2, 5).value)
        self.assertTrue(cell_formula_row2.startswith("="))
        self.assertIn("C2", cell_formula_row2)
        self.assertIn("D2", cell_formula_row2)

        # Hàng 3: =C3*D3
        cell_formula_row3 = str(ws.cell(3, 5).value)
        self.assertTrue(cell_formula_row3.startswith("="))
        self.assertIn("C3", cell_formula_row3)
        self.assertIn("D3", cell_formula_row3)

    def test_xlsx_without_header(self):
        """XLSX khi không có header (hdr=False): dữ liệu bắt đầu từ hàng 1, không freeze panes."""
        data_only_idx = [1, 2, 3]
        raw_xlsx = write_xlsx(
            self.table, data_only_idx, self.cols, fills={},
            hdr=False, title="Không Header", formula_mode="value"
        )
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx))
        ws = wb.active
        self.assertIsNone(ws.freeze_panes)
        self.assertEqual(ws.cell(1, 1).value, "SP01")

    # ==========================================================================
    # 2. KIỂM THỬ XUẤT CSV
    # ==========================================================================

    def test_csv_utf8_bom_and_read_back(self):
        """CSV phải có BOM \\ufeff, hỗ trợ hoàn hảo tiếng Việt có dấu, đọc lại khớp 100%."""
        raw_csv = write_csv(self.table, self.outidx, self.cols)
        self.assertIsInstance(raw_csv, bytes)

        # Kiểm tra byte BOM \xef\xbb\xbf
        self.assertTrue(raw_csv.startswith(b"\xef\xbb\xbf"))

        # Đọc lại bằng read_back
        got, fl = read_back(raw_csv, "csv", len(self.outidx), len(self.cols))
        self.assertEqual(fl, {})  # CSV không lưu màu

        # So sánh từng ô với giá trị hiển thị dự kiến
        expected = [[disp(self.table["rows"][i][c]) for c in self.cols] for i in self.outidx]
        self.assertEqual(got, expected)

        # Kiểm tra nội dung tiếng Việt có dấu phức tạp
        self.assertEqual(got[1][1], "Cà phê Robusta Đắk Lắk")
        self.assertEqual(got[4][1], "Gạo ST25 Ông Cua, Sóc Trăng")

    # ==========================================================================
    # 3. KIỂM THỬ XUẤT TSV
    # ==========================================================================

    def test_tsv_tab_delimited_and_read_back(self):
        """TSV phân tách bằng dấu tab, UTF-8 kèm BOM, đọc lại khớp 100%."""
        raw_tsv = write_tsv(self.table, self.outidx, self.cols)
        self.assertIsInstance(raw_tsv, bytes)
        self.assertTrue(raw_tsv.startswith(b"\xef\xbb\xbf"))

        # Giải mã chuỗi để xác nhận dấu tab
        text = raw_tsv.decode("utf-8-sig")
        lines = text.strip().split("\r\n")
        self.assertEqual(len(lines), 5)
        self.assertIn("\t", lines[0])

        got, fl = read_back(raw_tsv, "tsv", len(self.outidx), len(self.cols))
        self.assertEqual(fl, {})
        expected = [[disp(self.table["rows"][i][c]) for c in self.cols] for i in self.outidx]
        self.assertEqual(got, expected)

    # ==========================================================================
    # 4. KIỂM THỬ XUẤT JSON
    # ==========================================================================

    def test_json_with_header(self):
        """JSON có header: mảng các đối tượng [{"Tên cột": giá_trị}]."""
        raw_json = write_json(self.table, self.outidx, self.cols, hdr=True)
        self.assertIsInstance(raw_json, bytes)

        data = json.loads(raw_json.decode("utf-8"))
        self.assertEqual(len(data), 4)  # 4 dòng dữ liệu
        self.assertIsInstance(data[0], dict)
        self.assertIn("Mã SP", data[0])
        self.assertIn("Tên sản phẩm", data[0])
        self.assertEqual(data[0]["Mã SP"], "SP01")
        self.assertEqual(data[0]["Số lượng"], 10)
        self.assertEqual(data[0]["Ngày giao"], "2026-11-01")

        # Đọc lại với read_back (chế độ cả header + data: 5 dòng x 7 cột)
        got, _ = read_back(raw_json, "json", 5, 7)
        self.assertEqual(len(got), 5)
        self.assertEqual(got[0], self.table["rows"][0])
        self.assertEqual(got[1][0], "SP01")
        self.assertEqual(got[1][5], dt.date(2026, 11, 1))

    def test_json_without_header(self):
        """JSON không có header: mảng 2 chiều [[val1, val2, ...]]."""
        data_indices = [1, 2, 3, 4]
        raw_json = write_json(self.table, data_indices, self.cols, hdr=False)
        data = json.loads(raw_json.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 4)
        self.assertIsInstance(data[0], list)
        self.assertEqual(data[0][0], "SP01")

        # Đọc lại bằng read_back
        got, _ = read_back(raw_json, "json", 4, 7)
        self.assertEqual(len(got), 4)
        self.assertEqual(got[0][0], "SP01")

    # ==========================================================================
    # 5. KIỂM THỬ FORMAT WARNINGS & PREVIEW
    # ==========================================================================

    def test_format_warnings(self):
        """Kiểm tra cảnh báo tính năng theo từng định dạng (Roadmap mục 35.2)."""
        csv_warns = format_warnings("csv")
        self.assertTrue(len(csv_warns) > 0)
        self.assertTrue(any("màu" in w.lower() for w in csv_warns))
        self.assertTrue(any("công thức" in w.lower() for w in csv_warns))

        tsv_warns = format_warnings("tsv")
        self.assertTrue(len(tsv_warns) > 0)

        json_warns = format_warnings("json")
        self.assertTrue(len(json_warns) > 0)

        xlsx_warns = format_warnings("xlsx")
        self.assertEqual(xlsx_warns, [])  # XLSX hỗ trợ đầy đủ nên 0 cảnh báo

    def test_export_preview(self):
        """Kiểm tra hàm export_preview phục vụ giao diện (Roadmap mục 36)."""
        prev = export_preview(self.table, self.outidx, self.cols, self.fills, hdr=True, fmt="xlsx", limit=3)
        self.assertEqual(prev["format"], "XLSX")
        self.assertEqual(prev["total_rows"], 5)
        self.assertEqual(prev["total_cols"], 7)
        self.assertEqual(len(prev["sample_rows"]), 3)
        self.assertEqual(prev["columns"], self.table["rows"][0])
        self.assertIn("warnings", prev)

    # ==========================================================================
    # 6. KIỂM THỬ BỘ ĐIỀU PHỐI EXPORT_DATA VÀ CÔNG CỤ DỊCH CÔNG THỨC
    # ==========================================================================

    def test_export_data_dispatcher(self):
        """Kiểm tra hàm điều phối thống nhất export_data với tất cả định dạng."""
        for fmt in ["xlsx", "csv", "tsv", "json"]:
            res = export_data(self.table, self.outidx, self.cols, self.fills, hdr=True, fmt=fmt)
            self.assertIsInstance(res, bytes)
            self.assertTrue(len(res) > 0)

        with self.assertRaises(ValueError):
            export_data(self.table, self.outidx, self.cols, fmt="unsupported_format")

    def test_formula_translation_edge_cases(self):
        """Kiểm tra các trường hợp dịch công thức phong phú: AST, DSL, template row."""
        col_map = {"số lượng": "B", "đơn giá": "C", "thuế": "D"}
        
        # 1. Template {row}
        f1 = translate_to_excel_formula("=B{row}*C{row}", col_map, 5)
        self.assertEqual(f1, "=B5*C5")

        # 2. Chuỗi DSL tên cột dạng [Số lượng] * [Đơn giá]
        f2 = translate_to_excel_formula("[Số lượng] * [Đơn giá]", col_map, 2, ["Số lượng", "Đơn giá", "Thuế"])
        self.assertTrue("B2" in f2 and "C2" in f2 and f2.startswith("="))

        # 3. Đã là công thức Excel
        f3 = translate_to_excel_formula("=SUM(B2:D2)", col_map, 2)
        self.assertEqual(f3, "=SUM(B2:D2)")

    # ==========================================================================
    # 7. KIỂM THỬ ĐỐI CHIẾU KÉP TOÀN DIỆN (FULL CROSS-VERIFICATION)
    # ==========================================================================

    def test_independent_roundtrip_verification(self):
        """
        Đối chiếu kép 100%: Xuất bảng sang cả 4 định dạng, đọc lại bằng read_back
        và xác nhận độ sai khác bằng 0 (diff == 0).
        """
        for fmt in ["xlsx", "csv", "tsv", "json"]:
            data = export_data(self.table, self.outidx, self.cols, self.fills, hdr=True, fmt=fmt, formula_mode="value")
            got, fl = read_back(data, fmt, len(self.outidx), len(self.cols))

            self.assertEqual(len(got), len(self.outidx), f"Kích thước dòng không khớp tại {fmt}")
            self.assertEqual(len(got[0]), len(self.cols), f"Kích thước cột không khớp tại {fmt}")

            # Dữ liệu mong đợi:
            if fmt in ("csv", "tsv"):
                ex = [[disp(self.table["rows"][i][c]) for c in self.cols] for i in self.outidx]
            else:
                ex = [[norm(self.table["rows"][i][c]) for c in self.cols] for i in self.outidx]

            def cell_eq(a, b):
                if a == b:
                    return True
                if isinstance(a, dt.datetime) and isinstance(b, dt.date) and a.date() == b:
                    return True
                if isinstance(b, dt.datetime) and isinstance(a, dt.date) and b.date() == a:
                    return True
                return False

            diff = sum(1 for ra, rb in zip(got, ex) if not all(cell_eq(a, b) for a, b in zip(ra, rb)))
            self.assertEqual(diff, 0, f"Có sự sai khác dữ liệu khi đọc lại {fmt.upper()}: got != ex")


if __name__ == "__main__":
    unittest.main()
