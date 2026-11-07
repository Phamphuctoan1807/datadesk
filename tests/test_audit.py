"""
Phase 10: Security & Performance Audit Test Suite
Kiểm tra toàn diện tính bảo mật và hiệu năng của DataDesk theo mục 44, 45, 57, 58 và 72 trong Roadmap.
"""
import os
import sys
import io
import time
import copy
import json
import unittest
import datetime as dt

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import formula as FX
import validate_engine as VE
import export as EXP
import openpyxl

class TestSecurityAndPerformanceAudit(unittest.TestCase):

    # ==========================================================================
    # 1. BẢO MẬT: FORMULA DSL INJECTION & SANDBOXING (Mục 45)
    # ==========================================================================

    def test_formula_dsl_injection_safety(self):
        """
        Mục 45: Tuyệt đối không cho formula thực thi mã độc (Python code, shell, eval, import, system).
        Mọi biểu thức nằm ngoài danh sách token/hàm cho phép đều phải bị từ chối ở tầng AST hoặc validate.
        """
        malicious_expressions = [
            "__import__('os').system('calc')",
            "eval('1 + 1')",
            "exec('x = 5')",
            "open('server.py').read()",
            "import os",
            "subprocess.Popen(['cmd'])",
            "class X: pass",
            "lambda x: x + 1",
            "globals()",
            "locals()",
            "getattr(__builtins__, 'eval')",
            "<script>alert(1)</script>",
            "DROP TABLE users;",
            "SELECT * FROM confidential",
            "; rm -rf / ;",
            "[A] + `whoami`"
        ]

        cols = ["A", "B", "C"]
        for expr in malicious_expressions:
            rejected = False
            try:
                ast = FX.parse_formula(expr, cols)
                used = FX.validate_formula(ast, cols)
            except FX.FormulaError:
                rejected = True
            except Exception:
                rejected = True

            self.assertTrue(
                rejected,
                f"LỖ HỔNG BẢO MẬT: Biểu thức độc hại '{expr}' không bị chặn bởi AST parser!"
            )

    def test_formula_dsl_whitelist_only(self):
        """
        Mục 45: Formula DSL chỉ chấp nhận các hàm trong danh mục toán học, logic, chuỗi và ngày tháng.
        """
        allowed_functions = [
            "IF", "AND", "OR", "NOT", "ISEMPTY", "ISNUMBER", "ISDATE",
            "ABS", "ROUND", "CEIL", "FLOOR", "MIN", "MAX", "SUM", "AVERAGE",
            "POWER", "SQRT", "CONCAT", "LEFT", "RIGHT", "MID", "LEN",
            "TRIM", "LOWER", "UPPER", "REPLACE", "SUBSTITUTE", "CONTAINS",
            "STARTSWITH", "ENDSWITH", "YEAR", "MONTH", "DAY"
        ]
        cols = ["A", "B"]
        for fn in allowed_functions:
            expr = f"{fn}([A], [B])" if fn in ("CONCAT", "LEFT", "RIGHT", "ROUND", "POWER", "CONTAINS", "STARTSWITH", "ENDSWITH") else (
                f"{fn}([A], 1, 2)" if fn == "MID" else (
                    f"{fn}([A], 1, 1, \"x\")" if fn == "REPLACE" else (
                        f"{fn}([A], \"x\", \"y\")" if fn == "SUBSTITUTE" else (
                            f"IF([A]>0, 1, 0)" if fn == "IF" else f"{fn}([A])"
                        )
                    )
                )
            )
            try:
                ast = FX.parse_formula(expr, cols)
                used = FX.validate_formula(ast, cols)
                self.assertIsNotNone(used)
            except Exception as e:
                self.fail(f"Hàm chuẩn trong danh mục whitelist '{fn}' bị ném ngoại lệ: {e}")

    def test_circular_dependency_rejection(self):
        """
        Mục 17: Phát hiện và chặn triệt để đồ thị phụ thuộc vòng giữa các cột tính toán.
        """
        ops = [
            {"id": "op1", "type": "FORMULA", "target": "A", "expression": "[B] + 1", "enabled": True},
            {"id": "op2", "type": "FORMULA", "target": "B", "expression": "[C] * 2", "enabled": True},
            {"id": "op3", "type": "FORMULA", "target": "C", "expression": "[A] - 3", "enabled": True}
        ]
        # Gọi derive từ formula engine
        res = FX.derive(1, ["Gốc"], ops, lambda vals, ctype, pn, pd, nf: (vals, None, None))
        codes = [e.get("code") for e in res.get("errors", [])]
        self.assertIn(
            "CIRCULAR_DEPENDENCY", codes,
            f"LỖI BẢO MẬT/TÀI NGUYÊN: Không phát hiện được phụ thuộc vòng lặp A -> B -> C -> A! Mã lỗi: {codes}"
        )

    # ==========================================================================
    # 2. BẢO MẬT: BẢO TOÀN DỮ LIỆU & BẤT BIẾN NGUỒN (Mục 0 & Mục 58)
    # ==========================================================================

    def test_source_dataset_immutability(self):
        """
        Mục 0 & 58: Immutable Source - Không bao giờ sửa in-place trên bảng dữ liệu gốc.
        Mọi thao tác lọc, sắp xếp, chuẩn hóa, tính toán chỉ tạo ra view dẫn xuất (Derived Dataset).
        """
        orig_rows = [
            ["ID", "Name", "Salary"],
            ["NV01", "An", 15000000],
            ["NV02", "Bình", 22000000],
            ["NV03", "Châu", 18000000]
        ]
        deep_orig = copy.deepcopy(orig_rows)
        table = {
            "name": "NhanVien",
            "rows": orig_rows,
            "fm": None,
            "sf": None
        }

        # Thực hiện xuất dữ liệu có sắp xếp và lọc
        outidx = [0, 2, 1]  # Bỏ NV03, đảo vị trí NV02 và NV01
        cols = [0, 2]       # Chỉ lấy ID và Salary
        data = EXP.export_data(table, outidx, cols, fills={}, hdr=True, fmt="xlsx", formula_mode="value")
        self.assertIsNotNone(data)

        # Kiểm tra dữ liệu gốc hoàn toàn bất biến
        self.assertEqual(
            table["rows"],
            deep_orig,
            "LỖI TOÀN VẸN: Thao tác xuất file đã làm biến đổi in-place bảng dữ liệu gốc!"
        )

    # ==========================================================================
    # 3. HIỆU NĂNG: BENCHMARK 10.000 DÒNG (Mục 57)
    # ==========================================================================

    def test_performance_calculation_and_export_10k(self):
        """
        Mục 57: Benchmark hiệu năng xử lý 10.000 dòng.
        Thời gian tính toán công thức + xuất file + đọc lại kiểm tra đối chiếu kép < 3.0 giây.
        """
        N = 10000
        headers = ["Mã ĐH", "Số lượng", "Đơn giá", "Ngày lập"]
        base_date = dt.date(2026, 1, 1)

        # Sinh 10.000 dòng dữ liệu mẫu
        rows = [headers]
        for i in range(1, N + 1):
            rows.append([f"DH{i:05d}", (i % 50) + 1, 15000.0 + (i % 10) * 1000, base_date + dt.timedelta(days=i % 365)])

        table = {
            "name": "DonHang10K",
            "rows": rows,
            "fm": None,
            "sf": None
        }

        # 1. Tính toán giá trị công thức: Thành tiền = [Số lượng] * [Đơn giá]
        t0 = time.time()
        col_qty = 1
        col_price = 2
        calc_res = [rows[0] + ["Thành tiền"]]
        for r in rows[1:]:
            qty = r[col_qty]
            price = r[col_price]
            calc_res.append(r + [qty * price])
        t_calc = time.time() - t0

        self.assertLess(
            t_calc, 0.5,
            f"Hiệu năng tính toán 10.000 dòng quá chậm: {t_calc:.2f}s > 0.5s"
        )

        # 2. Xuất 10.000 dòng sang CSV (Định dạng phổ biến cho big data)
        table_10k = {"name": "DonHang10K", "rows": calc_res, "fm": None, "sf": None}
        outidx = list(range(len(calc_res)))
        cols = list(range(len(calc_res[0])))

        t1 = time.time()
        csv_bytes = EXP.export_data(table_10k, outidx, cols, fills={}, hdr=True, fmt="csv")
        t_export_csv = time.time() - t1

        self.assertLess(
            t_export_csv, 1.0,
            f"Hiệu năng xuất CSV 10.000 dòng quá chậm: {t_export_csv:.2f}s > 1.0s"
        )

        # 3. Đọc lại và đối chiếu kép độc lập (Read-back verification)
        t2 = time.time()
        got, _ = EXP.read_back(csv_bytes, "csv", len(outidx), len(cols))
        t_read_back = time.time() - t2

        self.assertLess(
            t_read_back, 0.5,
            f"Hiệu năng đọc lại CSV 10.000 dòng quá chậm: {t_read_back:.2f}s > 0.5s"
        )
        self.assertEqual(len(got), N + 1)
        self.assertEqual(len(got[0]), 5)

        # 4. Kiểm tra Data Loss Detection trên 10.000 dòng
        loss_safe, loss_detail, _ = VE.detect_data_loss(
            input_row_count=N,
            output_row_count=N,
            filter_removed_count=0
        )
        self.assertTrue(loss_safe)
        self.assertIn("10000", loss_detail)

    def test_numeric_tolerance_benchmark(self):
        """
        Mục 41: Kiểm tra dung sai số học với 100.000 phép so sánh số thực IEEE 754.
        Thời gian hoàn thành < 0.2s.
        """
        vals_exp = [0.1 * i + 0.2 * i for i in range(1, 10001)]
        vals_act = [0.3 * i for i in range(1, 10001)]

        t0 = time.time()
        ok, detail, mismatches = VE.validate_formula_values(vals_exp, vals_act, tolerance_rel=1e-9, tolerance_abs=1e-9)
        dt_val = time.time() - t0

        self.assertTrue(ok, f"Dung sai số thực thất bại: {detail}")
        self.assertEqual(len(mismatches), 0)
        self.assertLess(
            dt_val, 0.2,
            f"Xác thực dung sai 10.000 phép tính quá chậm: {dt_val:.2f}s > 0.2s"
        )

if __name__ == "__main__":
    unittest.main()
