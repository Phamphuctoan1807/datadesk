"""Tests for Data Quality Score Engine (Stage C - Future 3, Mục 76)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import quality_engine as QE

class TestDataQualityEngine(unittest.TestCase):

    def test_perfect_dataset(self):
        dataset = [
            ["ID", "Họ tên", "Email", "Số điện thoại", "Số lượng"],
            ["1", "Nguyen Van An", "an@gmail.com", "0912345678", 10],
            ["2", "Tran Thi Binh", "binh@datadesk.vn", "0987654321", 20],
            ["3", "Le Van Cuong", "cuong@company.com", "0901234567", 30],
        ]
        res = QE.compute_quality_score(dataset)
        self.assertEqual(res["overall_score"], 100.0)
        self.assertEqual(res["status"], "SAFE")
        self.assertEqual(res["metrics"]["completeness"], 100.0)
        self.assertEqual(res["metrics"]["consistency"], 100.0)
        self.assertEqual(res["metrics"]["validity"], 100.0)
        self.assertEqual(res["metrics"]["uniqueness"], 100.0)
        self.assertEqual(len(res["deductions"]), 0)

        chk_ok, msg = QE.independent_quality_check(dataset, res["overall_score"])
        self.assertTrue(chk_ok)

    def test_completeness_drop(self):
        dataset = [
            ["ID", "Name", "Email"],
            ["1", "An", "an@gmail.com"],
            ["2", "Binh", "N/A"],     # Null token
            ["3", "Cuong", ""],        # Empty string
            ["4", "Dung", None],       # None
        ]
        res = QE.compute_quality_score(dataset)
        self.assertLess(res["metrics"]["completeness"], 100.0)
        self.assertLess(res["overall_score"], 100.0)

        # Check deduction explanation
        comp_deductions = [d for d in res["deductions"] if d["category"] == "Completeness"]
        self.assertGreaterEqual(len(comp_deductions), 1)
        self.assertEqual(comp_deductions[0]["column"], "Email")
        self.assertEqual(comp_deductions[0]["count"], 3)

    def test_consistency_drop(self):
        dataset = [
            ["ID", "Tuổi"],
            ["1", 25],
            ["2", 30],
            ["3", 40],
            ["4", "không biết"],  # Text in mostly numeric column
        ]
        res = QE.compute_quality_score(dataset)
        self.assertLess(res["metrics"]["consistency"], 100.0)
        cons_deductions = [d for d in res["deductions"] if d["category"] == "Consistency"]
        self.assertEqual(len(cons_deductions), 1)
        self.assertEqual(cons_deductions[0]["count"], 1)

    def test_validity_drop(self):
        dataset = [
            ["ID", "Email", "Số điện thoại"],
            ["1", "invalid-email", "0912345678"],
            ["2", "user@domain.com", "12345"],    # Invalid phone
        ]
        res = QE.compute_quality_score(dataset)
        self.assertLess(res["metrics"]["validity"], 100.0)
        val_deductions = [d for d in res["deductions"] if d["category"] == "Validity"]
        self.assertEqual(len(val_deductions), 2)

    def test_uniqueness_drop(self):
        dataset = [
            ["ID", "Name"],
            ["1", "An"],
            ["1", "An"],   # Duplicate
            ["2", "Binh"],
        ]
        res = QE.compute_quality_score(dataset)
        self.assertLess(res["metrics"]["uniqueness"], 100.0)
        uniq_deductions = [d for d in res["deductions"] if d["category"] == "Uniqueness"]
        self.assertEqual(len(uniq_deductions), 1)
        self.assertEqual(uniq_deductions[0]["count"], 1)

    def test_empty_or_small_dataset(self):
        empty_res = QE.compute_quality_score([])
        self.assertEqual(empty_res["overall_score"], 100.0)

        header_only = [["ID", "Name"]]
        h_res = QE.compute_quality_score(header_only)
        self.assertEqual(h_res["overall_score"], 100.0)


class TestQualityScoreAPI(unittest.TestCase):
    def setUp(self):
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        self.sid = "test_quality_sid_01"
        server.STORE[self.sid] = {
            "name": "quality_test.xlsx",
            "tables": [
                {
                    "name": "Bảng kiểm tra",
                    "rows": [
                        ["ID", "Họ tên", "Email", "SĐT"],
                        ["1", "An", "an@gmail.com", "0912345678"],
                        ["2", "Binh", "sai-email", "0987654321"],
                        ["3", "Cuong", "", "123"],
                    ]
                }
            ],
            "ops": {0: {"list": [], "undo": [], "redo": [], "log": []}},
            "cache": {}
        }

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_quality_score_api(self):
        hdrs = {"X-Requested-With": "datadesk"}
        res = self.client.get(f"/api/quality/score?id={self.sid}&table=0", headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        q = data["data"]["quality"]
        self.assertIn("overall_score", q)
        self.assertIn("metrics", q)
        self.assertIn("deductions", q)
        self.assertLess(q["overall_score"], 100.0)

if __name__ == "__main__":
    unittest.main()
