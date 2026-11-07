"""Bộ kiểm thử cho Giai đoạn 5 (Smart Merge: Schema, Nhận diện cột, Khóa - Mục 11 đến 18).
Chạy: python tests/test_schema.py
"""

import sys
import os
import unittest
import datetime as dt

# Đảm bảo đường dẫn import thư mục gốc
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import schema as S

class TestSchemaEngine(unittest.TestCase):

    # ---------------- 1. Test Chuẩn hóa tên cột (Mục 14) ----------------
    def test_normalize_col_name(self):
        # Các dạng viết khác nhau của cùng một cột phải về cùng dạng chuẩn
        expected = "ma kh"
        variants = ["Mã KH", "ma_kh", "MA KH", "mã-kh", "MaKH", "  mã_kh  ", "MÃ-KH"]
        for v in variants:
            self.assertEqual(S.normalize_col_name(v), expected, "Lỗi chuẩn hóa: %s" % v)

        # Cột tiếng Anh và camelCase
        self.assertEqual(S.normalize_col_name("CustomerID"), "customer id")
        self.assertEqual(S.normalize_col_name("customer_id"), "customer id")
        self.assertEqual(S.normalize_col_name("PhoneNumber"), "phone number")
        self.assertEqual(S.normalize_col_name("Số ĐT"), "so dt")
        self.assertEqual(S.normalize_col_name("Đơn Giá (VNĐ)"), "don gia vnd")

    # ---------------- 2. Test Độ tương đồng tên cột (Mục 14 & 15) ----------------
    def test_name_similarity(self):
        # Trùng dạng chuẩn
        self.assertEqual(S.name_similarity("Mã KH", "ma_kh"), 1.0)
        self.assertEqual(S.name_similarity("Số lượng", "so_luong"), 1.0)

        # Nhóm đồng nghĩa Việt - Anh
        self.assertGreaterEqual(S.name_similarity("Mã KH", "Customer ID"), 0.90)
        self.assertGreaterEqual(S.name_similarity("Số điện thoại", "Phone"), 0.90)
        self.assertGreaterEqual(S.name_similarity("Đơn giá", "Unit Price"), 0.90)
        self.assertGreaterEqual(S.name_similarity("Email", "Thu dien tu"), 0.90)

        # Tên chứa nhau
        self.assertGreaterEqual(S.name_similarity("Khách hàng", "Tên khách hàng"), 0.70)

        # Tên hoàn toàn khác nhau
        self.assertLess(S.name_similarity("Mã KH", "Ngày tạo"), 0.30)
        self.assertLess(S.name_similarity("Số điện thoại", "Thành tiền"), 0.30)

    # ---------------- 3. Test Nhận diện ngữ nghĩa (Mục 16) ----------------
    def test_detect_semantic(self):
        # Email
        emails = ["toan@gmail.com", "contact@company.vn", "user123@yahoo.com"]
        res = S.detect_semantic("Email", emails, "text")
        self.assertEqual(res["type"], "email")
        self.assertGreaterEqual(res["confidence"], 0.85)

        # Phone
        phones = ["0912345678", "0987654321", "0903112233", "02438250000"]
        res = S.detect_semantic("Số ĐT", phones, "text")
        self.assertEqual(res["type"], "phone")
        self.assertGreaterEqual(res["confidence"], 0.85)

        # Date
        dates = ["15/08/2026", "20/08/2026", "01/09/2026"]
        res = S.detect_semantic("Ngày mua", dates, "text")
        self.assertEqual(res["type"], "date")

        # Price / Currency
        prices = ["100.000₫", "250.000 VND", "1.500.000 ₫"]
        res = S.detect_semantic("Đơn giá", prices, "text")
        self.assertEqual(res["type"], "price")

        # Customer ID
        cids = ["KH001", "KH002", "KH003", "KH004"]
        res = S.detect_semantic("Mã khách hàng", cids, "text")
        self.assertEqual(res["type"], "customer_id")

        # Name
        names = ["Nguyễn Văn A", "Trần Thị B", "Lê Hoàng C", "Phạm Phúc Toàn"]
        res = S.detect_semantic("Họ và tên", names, "text")
        self.assertEqual(res["type"], "name")

        # Status
        statuses = ["Đang xử lý", "Hoàn thành", "Đang xử lý", "Hủy", "Hoàn thành"] * 10
        res = S.detect_semantic("Trạng thái", statuses, "text")
        self.assertEqual(res["type"], "status")

    # ---------------- 4. Test Nhận diện Lược đồ & Khóa đơn (Mục 13 & 17) ----------------
    def test_detect_schema_and_single_key(self):
        headers = ["Mã KH", "Họ tên", "Số điện thoại", "Thành tiền", "Ghi chú"]
        rows = [
            ["KH001", "Nguyễn Văn A", "0912345678", 150000, "Khách quen"],
            ["KH002", "Trần Thị B", "0987654321", 320000, ""],
            ["KH003", "Lê Văn C", "0903112233", 450000, "Giao giờ hành chính"],
            ["KH004", "Phạm Văn D", "0977889900", 210000, "Đã thanh toán"],
        ]
        schema = S.detect_schema("Khách hàng", headers, rows)

        self.assertEqual(schema["name"], "Khách hàng")
        self.assertEqual(schema["total_rows"], 4)
        self.assertEqual(schema["total_columns"], 5)

        # Kiểm tra cột Mã KH
        col_makh = schema["columns"][0]
        self.assertEqual(col_makh["normalized_name"], "ma kh")
        self.assertEqual(col_makh["unique_ratio"], 1.0)
        self.assertEqual(col_makh["null_ratio"], 0.0)

        # Khóa đơn ứng viên
        keys = schema["key_candidates"]
        self.assertTrue(len(keys) >= 1)
        top_key = keys[0]
        self.assertEqual(top_key["column_name"], "Mã KH")
        self.assertTrue(top_key["is_perfect_key"])

    # ---------------- 5. Test Nhận diện Khóa kép (Mục 18) ----------------
    def test_detect_composite_key(self):
        # Bảng không có khóa đơn duy nhất (Chi nhánh trùng, Mã SP trùng), nhưng kết hợp là duy nhất
        headers = ["Mã chi nhánh", "Mã sản phẩm", "Tồn kho"]
        rows = [
            ["CN01", "SP01", 10],
            ["CN01", "SP02", 15],
            ["CN02", "SP01", 10],
            ["CN02", "SP02", 20],
            ["CN03", "SP01", 15],
            ["CN03", "SP02", 10],
        ]
        schema = S.detect_schema("Kho hàng", headers, rows)

        # Không có khóa đơn nào đạt 100%
        for k in schema["key_candidates"]:
            self.assertFalse(k["is_perfect_key"])

        # Phải tìm ra khóa kép (Mã chi nhánh + Mã sản phẩm)
        comp_keys = schema["composite_key_candidates"]
        self.assertTrue(len(comp_keys) >= 1)
        top_comp = comp_keys[0]
        self.assertEqual(set(top_comp["column_names"]), {"Mã chi nhánh", "Mã sản phẩm"})
        self.assertTrue(top_comp["is_perfect_key"])

    # ---------------- 6. Test So khớp Cột Thông minh & Ngưỡng An toàn (Mục 15 & 21) ----------------
    def test_match_schemas(self):
        # File A (tiếng Việt)
        headers_a = ["Mã KH", "Tên khách hàng", "Số điện thoại", "Ngày mua", "Tổng tiền"]
        rows_a = [
            ["KH001", "Nguyễn Văn A", "0912345678", "10/05/2026", 500000],
            ["KH002", "Trần Văn B", "0987654321", "12/05/2026", 750000],
        ]
        schema_a = S.detect_schema("File A", headers_a, rows_a)

        # File B (tiếng Anh)
        headers_b = ["Customer ID", "Customer Name", "Phone", "Purchase Date", "Amount"]
        rows_b = [
            ["KH001", "Nguyen Van A", "0912345678", "10/05/2026", 500000],
            ["KH003", "Le Van C", "0903344556", "15/05/2026", 300000],
        ]
        schema_b = S.detect_schema("File B", headers_b, rows_b)

        result = S.match_schemas(schema_a, schema_b)
        mappings = result["mappings"]

        # Phải khớp đủ 5 cột
        self.assertEqual(len(mappings), 5)

        # Cột Mã KH <-> Customer ID phải có điểm >= 0.90 và trạng thái SAFE
        makh_match = next(m for m in mappings if m["source_name"] == "Mã KH")
        self.assertEqual(makh_match["target_name"], "Customer ID")
        self.assertGreaterEqual(makh_match["score"], 0.90)
        self.assertEqual(makh_match["status"], "SAFE")

        # Cột SĐT <-> Phone phải khớp
        phone_match = next(m for m in mappings if m["source_name"] == "Số điện thoại")
        self.assertEqual(phone_match["target_name"], "Phone")
        self.assertGreaterEqual(phone_match["score"], 0.85)

        # Đề xuất kiểu merge: 5/5 cột khớp cao -> UNION
        rec = result["recommendation"]
        self.assertEqual(rec["mode"], "UNION")

    # ---------------- 7. Test Kiểm tra Đối chiếu Độc lập (Independent Validation - Mục 0 & 39) ----------------
    def test_independent_match_check(self):
        headers_a = ["Mã KH", "Điểm số"]
        rows_a = [["001", 9.5], ["002", 8.0]]
        schema_a = S.detect_schema("A", headers_a, rows_a)

        headers_b = ["Mã KH", "Ngày sinh"]
        rows_b = [["001", "2000-01-01"], ["002", "2001-02-02"]]
        schema_b = S.detect_schema("B", headers_b, rows_b)

        # Trường hợp ghép sai kiểu: Cột số (Điểm số) ghép vào Cột ngày (Ngày sinh)
        invalid_mapping = [
            {"source_index": 0, "target_index": 0, "score": 1.0, "status": "SAFE"},
            {"source_index": 1, "target_index": 1, "score": 0.6, "status": "REVIEW_REQUIRED"},
        ]
        check_res = S.independent_match_check(schema_a, schema_b, invalid_mapping)
        self.assertFalse(check_res["valid"])
        self.assertTrue(any("Không thể ghép cột số" in err for err in check_res["errors"]))

        # Trường hợp vi phạm an toàn: điểm 0.70 nhưng gán SAFE
        violating_mapping = [
            {"source_index": 0, "target_index": 0, "score": 0.70, "status": "SAFE"}
        ]
        check_res2 = S.independent_match_check(schema_a, schema_b, violating_mapping)
        self.assertFalse(check_res2["valid"])
        self.assertTrue(any("Vi phạm nguyên tắc an toàn" in err for err in check_res2["errors"]))

if __name__ == "__main__":
    unittest.main()
