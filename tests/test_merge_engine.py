"""
Kiểm thử bộ máy Record Matching & Merge Execution Engine (Giai đoạn 6)
Chạy: python tests/test_merge_engine.py
"""

import sys
import os
import unittest
import copy
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import merge_engine as ME

class TestMergeEngine(unittest.TestCase):

    def test_normalize_key_value(self):
        # Kiểm tra chuẩn hóa chuỗi, khoảng trắng, chữ hoa/thường, Unicode NFC
        self.assertEqual(ME.normalize_key_value("  KH001  "), "kh001")
        self.assertEqual(ME.normalize_key_value("NGUYỄN VĂN A"), "nguyễn văn a")
        # Số học: 10.0 == 10
        self.assertEqual(ME.normalize_key_value(10.0), "10")
        self.assertEqual(ME.normalize_key_value("10.0"), "10")
        self.assertEqual(ME.normalize_key_value(10.5), "10.5")
        # Ngày tháng
        self.assertEqual(ME.normalize_key_value(dt.date(2026, 3, 5)), "2026-03-05")
        self.assertEqual(ME.normalize_key_value("05/03/2026"), "2026-03-05")
        # Rỗng
        self.assertEqual(ME.normalize_key_value(None), "")
        self.assertEqual(ME.normalize_key_value(""), "")

    def test_execute_union_basic(self):
        h_a = ["Mã KH", "Tên", "Điểm"]
        b_a = [
            ["KH01", "An", 8],
            ["KH02", "Bình", 9],
        ]
        h_b = ["Mã KH", "Tên", "Điểm"]
        b_b = [
            ["KH03", "Chi", 7],
            ["KH04", "Dũng", 10],
        ]

        res = ME.execute_union(h_a, b_a, h_b, b_b)
        self.assertEqual(res["headers"], ["Mã KH", "Tên", "Điểm"])
        self.assertEqual(len(res["rows"]), 4)
        self.assertEqual(res["stats"]["total_rows"], 4)
        self.assertEqual(res["rows"][0], ["KH01", "An", 8])
        self.assertEqual(res["rows"][2], ["KH03", "Chi", 7])

    def test_execute_union_with_mapping_and_extra_cols(self):
        h_a = ["Mã KH", "Họ và Tên", "Doanh thu"]
        b_a = [
            ["KH01", "Nguyễn Văn A", 1000],
            ["KH02", "Trần Thị B", 2000],
        ]
        # Bảng B có tên cột khác và có cột Email riêng
        h_b = ["Customer ID", "Customer Name", "Sales", "Email"]
        b_b = [
            ["KH03", "Lê Văn C", 3000, "c@gmail.com"],
        ]

        mapping = [
            {"source_name": "Mã KH", "target_name": "Customer ID"},
            {"source_name": "Họ và Tên", "target_name": "Customer Name"},
            {"source_name": "Doanh thu", "target_name": "Sales"},
        ]

        res = ME.execute_union(h_a, b_a, h_b, b_b, col_mapping=mapping, missing_col_strategy="append")
        # Kết quả có 4 cột: 3 cột của A + cột Email từ B
        self.assertEqual(res["headers"], ["Mã KH", "Họ và Tên", "Doanh thu", "Email"])
        self.assertEqual(len(res["rows"]), 3)
        # Dòng của A được độn rỗng ở cột Email
        self.assertEqual(res["rows"][0], ["KH01", "Nguyễn Văn A", 1000, ""])
        # Dòng của B được ghép đúng vị trí tương ứng
        self.assertEqual(res["rows"][2], ["KH03", "Lê Văn C", 3000, "c@gmail.com"])

    def test_execute_union_immutability(self):
        h_a = ["A", "B"]
        b_a = [["1", "2"]]
        h_b = ["A", "B", "C"]
        b_b = [["3", "4", "5"]]

        h_a_orig = copy.deepcopy(h_a)
        b_a_orig = copy.deepcopy(b_a)
        h_b_orig = copy.deepcopy(h_b)
        b_b_orig = copy.deepcopy(b_b)

        ME.execute_union(h_a, b_a, h_b, b_b)

        self.assertEqual(h_a, h_a_orig)
        self.assertEqual(b_a, b_a_orig)
        self.assertEqual(h_b, h_b_orig)
        self.assertEqual(b_b, b_b_orig)

    def test_execute_join_left(self):
        h_a = ["Mã KH", "Tên"]
        b_a = [
            ["KH01", "Nguyễn Văn A"],
            ["KH02", "Trần Văn B"],
            ["KH03", "Lê Thị C"],
        ]
        h_b = ["Mã KH", "Điểm thưởng"]
        b_b = [
            ["KH01", 100],
            ["KH02", 200],
            ["KH04", 400], # Không có trong A
        ]

        res = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", join_type="left")
        self.assertEqual(res["headers"], ["Mã KH", "Tên", "Điểm thưởng"])
        self.assertEqual(len(res["rows"]), 3)
        self.assertEqual(res["rows"][0], ["KH01", "Nguyễn Văn A", 100])
        self.assertEqual(res["rows"][1], ["KH02", "Trần Văn B", 200])
        self.assertEqual(res["rows"][2], ["KH03", "Lê Thị C", ""]) # KH03 không có trong B -> rỗng
        self.assertEqual(res["stats"]["missing_in_b"], 1)

    def test_execute_join_inner(self):
        h_a = ["Mã KH", "Tên"]
        b_a = [
            ["KH01", "Nguyễn Văn A"],
            ["KH02", "Trần Văn B"],
            ["KH03", "Lê Thị C"],
        ]
        h_b = ["Mã KH", "Điểm thưởng"]
        b_b = [
            ["KH01", 100],
            ["KH02", 200],
            ["KH04", 400],
        ]

        res = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", join_type="inner")
        self.assertEqual(len(res["rows"]), 2)
        self.assertEqual(res["rows"][0], ["KH01", "Nguyễn Văn A", 100])
        self.assertEqual(res["rows"][1], ["KH02", "Trần Văn B", 200])

    def test_execute_join_full(self):
        h_a = ["Mã KH", "Tên"]
        b_a = [
            ["KH01", "Nguyễn Văn A"],
            ["KH02", "Trần Văn B"],
        ]
        h_b = ["Mã KH", "Điểm thưởng"]
        b_b = [
            ["KH02", 200],
            ["KH03", 300],
        ]

        res = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", join_type="full")
        self.assertEqual(len(res["rows"]), 3)
        # KH01 có ở A, không có ở B
        # KH02 có ở cả 2
        # KH03 có ở B, không có ở A
        self.assertEqual(res["rows"][0], ["KH01", "Nguyễn Văn A", ""])
        self.assertEqual(res["rows"][1], ["KH02", "Trần Văn B", 200])
        self.assertEqual(res["rows"][2], ["KH03", "", 300])

    def test_execute_join_composite_key(self):
        h_a = ["Chi nhánh", "Mã SP", "Tồn kho"]
        b_a = [
            ["CN1", "SP01", 50],
            ["CN1", "SP02", 30],
            ["CN2", "SP01", 20],
        ]
        h_b = ["Chi nhánh", "Mã SP", "Giá bán"]
        b_b = [
            ["CN1", "SP01", 100000],
            ["CN2", "SP01", 120000],
        ]

        res = ME.execute_join(h_a, b_a, h_b, b_b, key_a=["Chi nhánh", "Mã SP"], key_b=["Chi nhánh", "Mã SP"], join_type="left")
        self.assertEqual(res["headers"], ["Chi nhánh", "Mã SP", "Tồn kho", "Giá bán"])
        self.assertEqual(len(res["rows"]), 3)
        self.assertEqual(res["rows"][0], ["CN1", "SP01", 50, 100000])
        self.assertEqual(res["rows"][1], ["CN1", "SP02", 30, ""])
        self.assertEqual(res["rows"][2], ["CN2", "SP01", 20, 120000])

    def test_execute_join_conflict_strategies(self):
        h_a = ["Mã KH", "Tên", "Số điện thoại"]
        b_a = [["KH01", "Nguyễn Văn A", "0912345678"]]
        # Bảng B có cùng cột "Số điện thoại" nhưng số khác (xung đột)
        h_b = ["Mã KH", "Số điện thoại", "Email"]
        b_b = [["KH01", "0988888888", "a@test.com"]]

        # Chiến lược 1: prefer_a
        res_a = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", conflict_strategy="prefer_a")
        self.assertEqual(res_a["headers"], ["Mã KH", "Tên", "Số điện thoại", "Email"])
        self.assertEqual(res_a["rows"][0][2], "0912345678")
        self.assertEqual(len(res_a["conflicts"]), 1)

        # Chiến lược 2: prefer_b
        res_b = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", conflict_strategy="prefer_b")
        self.assertEqual(res_b["rows"][0][2], "0988888888")

        # Chiến lược 3: keep_both
        res_both = ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã KH", key_b="Mã KH", conflict_strategy="keep_both")
        self.assertIn("Số điện thoại (A)", res_both["headers"])
        self.assertIn("Số điện thoại (B)", res_both["headers"])

    def test_execute_join_cartesian_explosion_guard(self):
        h_a = ["Mã", "Tên"]
        b_a = [["X", "A1"] for _ in range(100)] # 100 dòng trùng khóa X
        h_b = ["Mã", "Mô tả"]
        b_b = [["X", "B1"] for _ in range(100)] # 100 dòng trùng khóa X
        # 100 * 100 = 10,000 dòng

        # Đặt ngưỡng giới hạn nhỏ = 500 dòng -> Phải kích hoạt chặn bảo vệ an toàn
        with self.assertRaises(ValueError) as ctx:
            ME.execute_join(h_a, b_a, h_b, b_b, key_a="Mã", key_b="Mã", max_expansion_limit=500)
        self.assertIn("CẢNH BÁO BÙNG NỔ DÒNG", str(ctx.exception))

    def test_independent_merge_check(self):
        h_a = ["Mã KH", "Tên"]
        b_a = [["KH01", "A"], ["KH02", "B"]]
        h_b = ["Mã KH", "Tên"]
        b_b = [["KH03", "C"]]

        u_res = ME.execute_union(h_a, b_a, h_b, b_b)
        chk = ME.independent_merge_check(h_a, b_a, h_b, b_b, u_res["headers"], u_res["rows"], mode="UNION")
        self.assertTrue(chk["valid"])
        self.assertEqual(len(chk["errors"]), 0)

        # Cố tình làm sai số dòng để kiểm tra khả năng phát hiện lỗi
        bad_rows = u_res["rows"][:2] # Thiếu 1 dòng
        chk_bad = ME.independent_merge_check(h_a, b_a, h_b, b_b, u_res["headers"], bad_rows, mode="UNION")
        self.assertFalse(chk_bad["valid"])
        self.assertIn("Vi phạm bất biến dòng UNION", chk_bad["errors"][0])

if __name__ == "__main__":
    unittest.main()
