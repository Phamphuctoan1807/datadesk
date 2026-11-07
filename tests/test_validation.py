"""
Bộ kiểm thử đơn vị cho validate_engine.py (Phase 9 - DataDesk)
Kiểm tra toàn diện:
- Formula validation với dung sai tolerance
- Data loss detection
- Duplicate expansion detection
- Referential integrity
- ValidationReport xuất JSON & CSV
"""

import unittest
import math
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime as dt
from validate_engine import (
    validate_formula_values,
    detect_data_loss,
    detect_duplicate_expansion,
    check_referential_integrity,
    run_full_validation,
    ValidationReport
)

class TestValidationEngine(unittest.TestCase):

    def test_formula_numeric_tolerance(self):
        # 1. Khớp hoàn hảo
        exp = [10.0, 20.5, 30.000000001]
        act = [10.0, 20.5, 30.000000001]
        ok, detail, mismatches = validate_formula_values(exp, act)
        self.assertTrue(ok)
        self.assertEqual(len(mismatches), 0)

        # 2. Lệch trong ngưỡng floating point tolerance (1e-9)
        exp = [1.0000000000000002, 0.1 + 0.2]
        act = [1.0, 0.3]
        ok, detail, mismatches = validate_formula_values(exp, act)
        self.assertTrue(ok)
        self.assertEqual(len(mismatches), 0)

        # 3. Lệch vượt ngưỡng
        exp = [10.0, 20.0]
        act = [10.0, 20.5]
        ok, detail, mismatches = validate_formula_values(exp, act)
        self.assertFalse(ok)
        self.assertEqual(len(mismatches), 1)

    def test_formula_strings_and_dates(self):
        # Ngày tháng
        d1 = dt.date(2026, 11, 7)
        d2 = dt.date(2026, 11, 7)
        d3 = dt.date(2026, 11, 8)
        ok, _, mismatches = validate_formula_values([d1], [d2])
        self.assertTrue(ok)
        ok, _, mismatches = validate_formula_values([d1], [d3])
        self.assertFalse(ok)

        # Chuỗi ký tự
        ok, _, mismatches = validate_formula_values(["  Hà Nội  ", "TP.HCM"], ["Hà Nội", "TP.HCM"])
        self.assertTrue(ok)
        ok, _, mismatches = validate_formula_values(["Đà Nẵng"], ["Cần Thơ"])
        self.assertFalse(ok)

    def test_data_loss_detection(self):
        # 1. An toàn: không mất dòng
        safe, detail, info = detect_data_loss(input_row_count=100, output_row_count=100)
        self.assertTrue(safe)
        self.assertEqual(info["unexpected_loss"], 0)

        # 2. An toàn: mất dòng có giải trình (do lọc)
        safe, detail, info = detect_data_loss(input_row_count=100, output_row_count=80, filter_removed_count=20)
        self.assertTrue(safe)
        self.assertEqual(info["unexpected_loss"], 0)

        # 3. Không an toàn: mất dòng bất thường
        safe, detail, info = detect_data_loss(input_row_count=100, output_row_count=70, filter_removed_count=10)
        self.assertFalse(safe)
        self.assertEqual(info["unexpected_loss"], 20)

    def test_duplicate_expansion_detection(self):
        keys_a = ["NV01", "NV02", "NV03"]
        # Khóa B duy nhất 1:1
        keys_b_unique = ["NV01", "NV02", "NV03"]
        safe, detail, info = detect_duplicate_expansion(keys_a, keys_b_unique)
        self.assertTrue(safe)
        self.assertFalse(info["has_expansion"])

        # Khóa B trùng lặp (1-nhiều)
        keys_b_dup = ["NV01", "NV02", "NV02", "NV03", "NV03", "NV03"]
        safe, detail, info = detect_duplicate_expansion(keys_a, keys_b_dup)
        self.assertFalse(safe)
        self.assertTrue(info["has_expansion"])
        self.assertEqual(info["duplicate_keys_count"], 2)

    def test_referential_integrity(self):
        # Đạt chuẩn
        ok, detail, _ = check_referential_integrity(["A01", "A02", "A03"], "Mã hàng")
        self.assertTrue(ok)

        # Có trùng lặp
        ok, detail, info = check_referential_integrity(["A01", "A02", "A02"], "Mã hàng")
        self.assertFalse(ok)
        self.assertIn("A02", info["duplicates"])

        # Có ô trống
        ok, detail, info = check_referential_integrity(["A01", "", "A03"], "Mã hàng")
        self.assertFalse(ok)
        self.assertEqual(info["empty"], 1)

    def test_full_pipeline_validation(self):
        source = {
            "name": "sales.xlsx",
            "rows": [["ID", "Name", "Amount"], ["1", "A", 100], ["2", "B", 200]]
        }
        output = [["ID", "Name", "Amount"], ["1", "A", 100], ["2", "B", 200]]
        
        rep = run_full_validation(
            source_table=source,
            output_rows=output,
            header=True,
            exported_data=b"mock-xlsx-data",
            format_type="xlsx"
        )
        self.assertTrue(rep.is_safe)
        self.assertEqual(rep.status, "SAFE")
        
        # Test JSON & CSV export
        json_str = rep.to_json()
        self.assertIn("SAFE", json_str)
        csv_bytes = rep.to_csv()
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf")) # UTF-8 BOM

if __name__ == '__main__':
    unittest.main()
