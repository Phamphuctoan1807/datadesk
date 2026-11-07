"""Tests for Automation & Batch Processing Engine (Stage C - Future 9, 11, 12, Mục 82, 84, 85)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation_engine import AUTOMATION, independent_automation_check

class TestAutomationEngine(unittest.TestCase):

    def test_workflow_planner(self):
        prompt = "Gộp hai file theo mã khách hàng, chuẩn hóa SĐT, tính Thành tiền, tô màu đơn hàng lớn và xuất Excel"
        res = AUTOMATION.plan_workflow_from_text(prompt)
        self.assertGreaterEqual(res["total_steps"], 4)
        types = [s["type"] for s in res["plan"]]
        self.assertIn("MERGE", types)
        self.assertIn("NORMALIZE", types)
        self.assertIn("FORMULA", types)
        self.assertIn("EXPORT", types)

    def test_batch_processing(self):
        preset = {
            "id": "p_orders",
            "name": "Xử lý đơn hàng",
            "steps": [{"type": "FORMULA", "target": "Thành tiền", "expression": "[Số lượng] * [Đơn giá]"}]
        }

        files_data = [
            # File 1: Full columns (Succeeded)
            {"filename": "orders_jan.csv", "rows": [["Mã", "Số lượng", "Đơn giá"], ["1", 5, 1000]]},
            # File 2: Missing Đơn giá (Review Required)
            {"filename": "orders_feb.csv", "rows": [["Mã", "Số lượng"], ["2", 10]]},
            # File 3: Empty file (Failed)
            {"filename": "orders_empty.csv", "rows": []}
        ]

        batch_res = AUTOMATION.run_batch_preset(files_data, preset)
        self.assertEqual(batch_res["total_files"], 3)
        self.assertEqual(batch_res["succeeded"], 1)
        self.assertEqual(batch_res["review_required"], 1)
        self.assertEqual(batch_res["failed"], 1)

        # Independent check
        chk_ok, msg = independent_automation_check(batch_res)
        self.assertTrue(chk_ok)

    def test_schedule_crud(self):
        job = AUTOMATION.create_schedule(
            schedule_id="job_daily_sales",
            name="Daily Sales Processing",
            preset_id="p_orders",
            frequency="daily",
            time_str="08:00"
        )
        self.assertEqual(job["name"], "Daily Sales Processing")
        self.assertEqual(job["time"], "08:00")
        schedules = AUTOMATION.list_schedules()
        self.assertGreaterEqual(len(schedules), 1)


class TestAutomationAPI(unittest.TestCase):
    def setUp(self):
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

    def test_automation_api_plan(self):
        hdrs = {"X-Requested-With": "datadesk"}
        body = {"prompt": "Chuẩn hóa SĐT và tính tổng tiền rồi xuất file"}
        res = self.client.post("/api/automation/plan", json=body, headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["data"]["plan"]["total_steps"], 2)

if __name__ == "__main__":
    unittest.main()
