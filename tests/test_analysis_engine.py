"""Tests for Quick Analysis & Dashboard Engine (Stage C - Future 8, Mục 81)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import analysis_engine as AE

class TestAnalysisEngine(unittest.TestCase):

    def test_analysis_generation(self):
        dataset = [
            ["Mã SP", "Danh mục", "Ngày bán", "Số lượng", "Doanh thu"],
            ["SP01", "Điện tử", "2026-01-01", 5, 25000000],
            ["SP02", "Gia dụng", "2026-01-02", 10, 5000000],
            ["SP03", "Điện tử", "2026-01-03", 2, 12000000],
            ["SP04", "Thời trang", "2026-01-04", 20, 8000000],
            ["SP05", "Điện tử", "2026-01-05", 3, 15000000],
            ["SP06", "Gia dụng", "2026-01-06", 8, 4000000],
        ]

        res = AE.generate_quick_analysis(dataset)
        kpis = res["kpi_cards"]
        self.assertGreaterEqual(len(kpis), 2)
        self.assertEqual(kpis[0]["value"], "6") # 6 rows

        # Check charts generated
        charts = res["charts"]
        chart_types = [c["type"] for c in charts]
        self.assertIn("bar", chart_types)
        self.assertIn("pie", chart_types)
        self.assertIn("line", chart_types)

        # Independent check
        chk_ok, msg = AE.independent_analysis_check(dataset, res)
        self.assertTrue(chk_ok)


class TestAnalysisAPI(unittest.TestCase):
    def setUp(self):
        import io
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        csv_data = "Sản phẩm,Loại,Doanh thu\nLaptop,IT,2000\nChuột,IT,50\nBàn,Noi that,300"
        data = {"file": (io.BytesIO(csv_data.encode("utf-8")), "products.csv")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data", headers={"X-Requested-With": "datadesk"})
        self.sid = res.get_json()["id"]

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_analysis_api(self):
        hdrs = {"X-Requested-With": "datadesk"}
        res = self.client.get(f"/api/analysis/dashboard?id={self.sid}&table=0", headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        dash = data["data"]["dashboard"]
        self.assertIn("kpi_cards", dash)
        self.assertIn("charts", dash)

if __name__ == "__main__":
    unittest.main()
