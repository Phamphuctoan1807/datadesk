"""Tests for Business Validation Rules Engine (Stage C - Future 4, Mục 77)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import business_rules as BR

class TestBusinessRulesEngine(unittest.TestCase):

    def test_value_comparisons(self):
        dataset = [
            ["ID", "Họ tên", "Tuổi", "Số lượng"],
            ["1", "An", 20, 5],
            ["2", "Binh", 16, -2],   # Both Tuổi < 18 and Số lượng < 0
            ["3", "Cuong", 18, 0],   # Edge values (>= 18, >= 0)
        ]
        rules = [
            {"id": "r1", "name": "Tuổi >= 18", "type": "compare", "column": "Tuổi", "operator": ">=", "value": 18},
            {"id": "r2", "name": "Số lượng >= 0", "type": "compare", "column": "Số lượng", "operator": ">=", "value": 0},
        ]
        res = BR.validate_dataset_rules(dataset, rules)
        self.assertEqual(res["total_rows"], 3)
        self.assertEqual(res["valid_rows_count"], 2)
        self.assertEqual(res["violated_rows_count"], 1)

        # Check violation details for row 2 (row_number = 3)
        v_row = res["violations"][0]
        self.assertEqual(v_row["row_number"], 3)
        self.assertEqual(len(v_row["violations"]), 2)

        chk_ok, msg = BR.independent_rules_check(dataset, rules, res)
        self.assertTrue(chk_ok)

    def test_column_to_column_comparison(self):
        dataset = [
            ["Mã", "Ngày bắt đầu", "Ngày kết thúc", "Giá vốn", "Giá bán"],
            ["D1", "2026-01-01", "2026-01-15", 100000, 150000], # Valid
            ["D2", "2026-02-10", "2026-02-05", 200000, 180000], # Invalid dates and Giá bán < Giá vốn
        ]
        rules = [
            {"id": "r_date", "name": "Ngày kết thúc >= Ngày bắt đầu", "type": "compare_columns", "column": "Ngày kết thúc", "operator": ">=", "target_column": "Ngày bắt đầu"},
            {"id": "r_price", "name": "Giá bán >= Giá vốn", "type": "compare_columns", "column": "Giá bán", "operator": ">=", "target_column": "Giá vốn"}
        ]
        res = BR.validate_dataset_rules(dataset, rules)
        self.assertEqual(res["valid_rows_count"], 1)
        self.assertEqual(res["violated_rows_count"], 1)

    def test_format_and_empty_rules(self):
        dataset = [
            ["ID", "Email", "SĐT", "Địa chỉ"],
            ["1", "user@datadesk.vn", "0912345678", "Hà Nội"],
            ["2", "bad-email", "0987654321", "HCM"],
            ["3", "ok@mail.com", "12345", ""],  # Invalid phone and empty address
        ]
        rules = [
            {"id": "r_mail", "name": "Email hợp lệ", "type": "valid_email", "column": "Email"},
            {"id": "r_phone", "name": "SĐT hợp lệ", "type": "valid_phone", "column": "SĐT"},
            {"id": "r_addr", "name": "Địa chỉ không để trống", "type": "not_empty", "column": "Địa chỉ"},
        ]
        res = BR.validate_dataset_rules(dataset, rules)
        self.assertEqual(res["valid_rows_count"], 1)
        self.assertEqual(res["violated_rows_count"], 2)

    def test_uniqueness_rule(self):
        dataset = [
            ["Mã KH", "Tên"],
            ["KH01", "An"],
            ["KH02", "Binh"],
            ["KH01", "An Lặp"], # Duplicate ID
        ]
        rules = [
            {"id": "r_uniq", "name": "Mã KH không được trùng", "type": "unique", "column": "Mã KH"}
        ]
        res = BR.validate_dataset_rules(dataset, rules)
        self.assertEqual(res["valid_rows_count"], 1)
        self.assertEqual(res["violated_rows_count"], 2) # Both instances of KH01 are flagged


class TestBusinessRulesAPI(unittest.TestCase):
    def setUp(self):
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        self.sid = "test_rules_sid_01"
        server.STORE[self.sid] = {
            "name": "rules_data.xlsx",
            "tables": [
                {
                    "name": "Đơn hàng",
                    "rows": [
                        ["Mã ĐH", "Số lượng", "Đơn giá"],
                        ["DH01", 10, 50000],
                        ["DH02", -5, 20000],
                    ]
                }
            ],
            "ops": {0: {"list": [], "undo": [], "redo": [], "log": []}},
            "cache": {}
        }

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_business_rules_api(self):
        hdrs = {"X-Requested-With": "datadesk"}
        body = {
            "id": self.sid,
            "table": 0,
            "rules": [
                {"id": "r1", "name": "Số lượng >= 0", "type": "compare", "column": "Số lượng", "operator": ">=", "value": 0}
            ]
        }
        res = self.client.post("/api/business_rules/validate", json=body, headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        res_data = data["data"]["validation_result"]
        self.assertEqual(res_data["valid_rows_count"], 1)
        self.assertEqual(res_data["violated_rows_count"], 1)

if __name__ == "__main__":
    unittest.main()
