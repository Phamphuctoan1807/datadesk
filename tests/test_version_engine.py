"""Tests for Version History Engine (Stage C - Future 6, Mục 79)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from version_engine import VERSIONS, independent_version_check

class TestVersionEngine(unittest.TestCase):

    def setUp(self):
        self.sid = "test_version_sid"
        VERSIONS.clear_session(self.sid)

    def test_version_crud_and_compare(self):
        # Version 1 - Original
        rows_v1 = [
            ["ID", "Name", "Score"],
            ["1", "An", 8],
            ["2", "Binh", 7],
        ]
        v1 = VERSIONS.create_version(self.sid, 0, "Original", "Dữ liệu ban đầu", rows_v1)
        self.assertEqual(v1["version_number"], 1)
        self.assertEqual(v1["row_count"], 2)

        # Version 2 - Transformed (Added column & modified score)
        rows_v2 = [
            ["ID", "Name", "Score", "Rank"],
            ["1", "An", 9, "A"],      # Score changed 8 -> 9, added Rank
            ["2", "Binh", 7, "B"],
            ["3", "Cuong", 10, "A+"],  # Added row
        ]
        v2 = VERSIONS.create_version(self.sid, 0, "Transformed", "Đã cộng điểm và thêm hạng", rows_v2)
        self.assertEqual(v2["version_number"], 2)
        self.assertEqual(v2["row_count"], 3)

        # List versions
        v_list = VERSIONS.list_versions(self.sid, 0)
        self.assertEqual(len(v_list), 2)
        self.assertEqual(v_list[0]["label"], "Original")
        self.assertEqual(v_list[1]["label"], "Transformed")

        # Compare versions
        diff = VERSIONS.compare_versions(self.sid, v1["id"], v2["id"])
        self.assertEqual(diff["column_diff"]["added_columns"], ["Rank"])
        self.assertEqual(diff["row_diff"]["row_count_delta"], 1)
        self.assertGreaterEqual(diff["cell_diff"]["modified_cells_count"], 1)

        # Independent check
        chk_ok, msg = independent_version_check(v1, v2, diff)
        self.assertTrue(chk_ok)

        # Restore version 1
        restored = VERSIONS.restore_version(self.sid, v1["id"])
        self.assertEqual(restored["rows"], rows_v1)


class TestVersionAPI(unittest.TestCase):
    def setUp(self):
        import io
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        csv_data = "Mã,Tên,Tuổi\n1,An,20\n2,Binh,22"
        data = {"file": (io.BytesIO(csv_data.encode("utf-8")), "students.csv")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data", headers={"X-Requested-With": "datadesk"})
        self.sid = res.get_json()["id"]

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_version_api_flow(self):
        hdrs = {"X-Requested-With": "datadesk"}

        # 1. Create version 1
        c1 = self.client.post("/api/version/create", json={"id": self.sid, "table": 0, "label": "V1 Ban đầu", "description": "Gốc"}, headers=hdrs)
        self.assertEqual(c1.status_code, 200)
        v1_data = c1.get_json()["data"]["version"]
        self.assertEqual(v1_data["version_number"], 1)

        # 2. List versions
        l1 = self.client.get(f"/api/version/list?id={self.sid}&table=0", headers=hdrs)
        self.assertEqual(l1.status_code, 200)
        self.assertEqual(len(l1.get_json()["data"]["versions"]), 1)

        # 3. Create version 2
        c2 = self.client.post("/api/version/create", json={"id": self.sid, "table": 0, "label": "V2 Đã sửa", "description": "Sửa"}, headers=hdrs)
        self.assertEqual(c2.status_code, 200)
        v2_data = c2.get_json()["data"]["version"]

        # 4. Compare versions
        cmp_res = self.client.post("/api/version/compare", json={"id": self.sid, "version_a": v1_data["id"], "version_b": v2_data["id"]}, headers=hdrs)
        self.assertEqual(cmp_res.status_code, 200)
        self.assertTrue(cmp_res.get_json()["success"])

        # 5. Restore version 1
        rst_res = self.client.post("/api/version/restore", json={"id": self.sid, "table": 0, "version_id": v1_data["id"]}, headers=hdrs)
        self.assertEqual(rst_res.status_code, 200)
        self.assertTrue(rst_res.get_json()["success"])

if __name__ == "__main__":
    unittest.main()
