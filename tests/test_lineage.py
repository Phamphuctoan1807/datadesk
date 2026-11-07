"""Tests for Data Lineage & Explainability Engine (Stage C - Future 5 & Future 7, Mục 78 & 80)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lineage_engine import LINEAGE

class TestLineageEngine(unittest.TestCase):

    def setUp(self):
        self.sid = "test_lineage_sid"
        LINEAGE.clear_session(self.sid)

    def test_record_and_get_lineage(self):
        # Step 0: Original value
        LINEAGE.record_cell_step(
            session_id=self.sid, table_idx=0, row_idx=5, col_name="Thành tiền",
            old_val=100000, new_val=100000, step_type="ORIGINAL",
            rule_name="Gốc", source_file="sales.xlsx", source_sheet="January", source_row=7
        )

        # Step 1: Formula transformation
        LINEAGE.record_cell_step(
            session_id=self.sid, table_idx=0, row_idx=5, col_name="Thành tiền",
            old_val=100000, new_val=120000, step_type="FORMULA",
            rule_name="Tăng giá 20%", formula_or_expr="[Giá] * 1.2"
        )

        # Query lineage
        res = LINEAGE.get_cell_lineage(self.sid, 0, 5, "Thành tiền", current_val=120000)
        self.assertEqual(res["cell"]["current_value"], 120000)
        self.assertEqual(res["root_source"]["file"], "sales.xlsx")
        self.assertEqual(res["root_source"]["sheet"], "January")
        self.assertEqual(res["root_source"]["row"], 7)
        self.assertEqual(len(res["lineage_chain"]), 2)
        self.assertIn("Tăng giá 20%", res["summary_explain"])

    def test_inferred_lineage(self):
        # Test inference from table header and ops list when not explicitly recorded
        header = ["Mã SP", "Đơn giá", "Thành tiền"]
        ops = [
            {"id": "op_1", "type": "FORMULA", "name": "Tính thành tiền", "target": "Thành tiền", "expression": "[Đơn giá] * 2", "enabled": True}
        ]
        res = LINEAGE.get_cell_lineage(
            session_id="fresh_sid", table_idx=0, row_idx=2, col_name="Thành tiền",
            current_val=50000, header=header, ops_list=ops, source_name="orders.csv"
        )
        self.assertEqual(res["root_source"]["file"], "orders.csv")
        self.assertEqual(len(res["lineage_chain"]), 2)
        self.assertEqual(res["lineage_chain"][1]["type"], "FORMULA")


class TestLineageAPI(unittest.TestCase):
    def setUp(self):
        import io
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        csv_data = "Mã SP,Số lượng,Đơn giá\nSP01,10,25000\nSP02,5,50000"
        data = {"file": (io.BytesIO(csv_data.encode("utf-8")), "sales.csv")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data", headers={"X-Requested-With": "datadesk"})
        self.sid = res.get_json()["id"]

        # Thêm 1 công thức
        f_body = {"id": self.sid, "table": 0, "header": True, "target": "Thành tiền", "expression": "[Đơn giá] * 1.1"}
        self.client.post("/api/formula/apply", json=f_body, headers={"X-Requested-With": "datadesk"})

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_lineage_api(self):
        hdrs = {"X-Requested-With": "datadesk"}
        res = self.client.get(f"/api/lineage/cell?id={self.sid}&table=0&row=0&col=Thành tiền", headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        lin = data["data"]["lineage"]
        self.assertEqual(lin["cell"]["column"], "Thành tiền")
        self.assertEqual(lin["root_source"]["file"], "sales.csv")

if __name__ == "__main__":
    unittest.main()
