"""Kiểm thử tích hợp cho API Smart Merge (Giai đoạn 5 - Mục 11 đến 18).
Chạy: python tests/test_merge_api.py
"""

import sys
import os
import io
import json
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import server

class TestMergeAPI(unittest.TestCase):
    def setUp(self):
        server.PW = "matkhautest123"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()

        # Đăng nhập để lấy cookie phiên
        with self.client.session_transaction() as sess:
            sess["ok"] = True

    def test_multi_file_analyze_and_merge_apis(self):
        # Tạo 2 file CSV mẫu trong bộ nhớ
        csv_a = "Mã KH,Tên khách hàng,Số điện thoại,Tổng tiền\nKH001,Nguyễn Văn A,0912345678,500000\nKH002,Trần Văn B,0987654321,300000"
        csv_b = "Customer ID,Customer Name,Phone,Email\nKH001,Nguyen Van A,0912345678,a@gmail.com\nKH003,Le Thi C,0903112233,c@gmail.com"

        # 1. Test nạp 2 file cùng lúc vào /api/analyze
        data = {
            "files": [
                (io.BytesIO(csv_a.encode("utf-8")), "khach_hang_a.csv"),
                (io.BytesIO(csv_b.encode("utf-8")), "khach_hang_b.csv"),
            ]
        }
        hdrs = {"X-Requested-With": "datadesk"}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data", headers=hdrs)
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        sid = body["id"]
        self.assertIn("datasets", body)
        self.assertEqual(len(body["datasets"]), 2)
        self.assertEqual(len(body["tables"]), 2)

        # 2. Test /api/merge/schema cho bảng 0
        res_schema = self.client.post("/api/merge/schema", json={"id": sid, "table": 0}, headers=hdrs)
        self.assertEqual(res_schema.status_code, 200)
        s_data = res_schema.get_json()
        self.assertTrue(s_data["success"])
        self.assertEqual(s_data["data"]["total_columns"], 4)
        self.assertTrue(len(s_data["data"]["key_candidates"]) >= 1)
        self.assertEqual(s_data["data"]["key_candidates"][0]["column_name"], "Mã KH")

        # 3. Test /api/merge/analyze (so khớp cột giữa bảng 0 và bảng 1)
        res_merge = self.client.post("/api/merge/analyze", json={"id": sid, "table_a": 0, "table_b": 1}, headers=hdrs)
        self.assertEqual(res_merge.status_code, 200)
        m_data = res_merge.get_json()
        self.assertTrue(m_data["success"])
        mappings = m_data["data"]["matching"]["mappings"]
        self.assertTrue(len(mappings) >= 3)

        # Kiểm tra khớp 'Mã KH' <-> 'Customer ID'
        makh = next(m for m in mappings if m["source_name"] == "Mã KH")
        self.assertEqual(makh["target_name"], "Customer ID")
        self.assertGreaterEqual(makh["score"], 0.90)
        self.assertEqual(makh["status"], "SAFE")

        # 4. Test /api/merge/mapping (xác nhận ánh xạ hợp lệ)
        user_mappings = [
            {"source_index": 0, "target_index": 0, "score": 0.95, "status": "SAFE"},
            {"source_index": 1, "target_index": 1, "score": 0.92, "status": "SAFE"},
            {"source_index": 2, "target_index": 2, "score": 0.90, "status": "SAFE"},
        ]
        res_map = self.client.post("/api/merge/mapping", json={"id": sid, "table_a": 0, "table_b": 1, "mappings": user_mappings}, headers=hdrs)
        self.assertEqual(res_map.status_code, 200)
        map_body = res_map.get_json()
        self.assertTrue(map_body["success"])
        self.assertTrue(map_body["data"]["valid"])

        # 5. Test thêm 1 file thứ ba bằng /api/merge/add_file
        csv_c = "Mã KH,Điểm thưởng\nKH001,100\nKH002,50"
        data_c = {
            "id": sid,
            "file": (io.BytesIO(csv_c.encode("utf-8")), "diem_thuong.csv"),
        }
        res_add = self.client.post("/api/merge/add_file", data=data_c, content_type="multipart/form-data", headers=hdrs)
        self.assertEqual(res_add.status_code, 200)
        add_body = res_add.get_json()
        self.assertEqual(len(add_body["tables"]), 3)
        self.assertEqual(len(add_body["datasets"]), 3)

        # 6. Test thực thi Gộp dòng (UNION) qua /api/merge/execute
        res_union = self.client.post(
            "/api/merge/execute",
            json={"id": sid, "table_a": 0, "table_b": 1, "mode": "UNION", "mappings": user_mappings},
            headers=hdrs
        )
        self.assertEqual(res_union.status_code, 200)
        u_body = res_union.get_json()
        self.assertTrue(u_body["success"])
        self.assertEqual(u_body["data"]["stats"]["total_rows"], 4)
        self.assertEqual(len(u_body["data"]["tables"]), 4)

        # 7. Test thực thi Ghép theo khóa (JOIN) qua /api/merge/execute
        res_join = self.client.post(
            "/api/merge/execute",
            json={"id": sid, "table_a": 0, "table_b": 2, "mode": "JOIN", "key_a": "Mã KH", "key_b": "Mã KH", "join_type": "left"},
            headers=hdrs
        )
        self.assertEqual(res_join.status_code, 200)
        j_body = res_join.get_json()
        self.assertTrue(j_body["success"])
        self.assertEqual(j_body["data"]["matched_rows"], 2)
        self.assertEqual(j_body["data"]["stats"]["mode"], "JOIN")
        self.assertEqual(len(j_body["data"]["tables"]), 5)

        # 8. Test chế độ không hợp lệ
        res_inv = self.client.post(
            "/api/merge/execute",
            json={"id": sid, "table_a": 0, "table_b": 1, "mode": "UNKNOWN"},
            headers=hdrs
        )
        self.assertEqual(res_inv.status_code, 400)
        inv_body = res_inv.get_json()
        self.assertFalse(inv_body["success"])
        self.assertEqual(inv_body["errors"][0]["code"], "INVALID_MODE")

        # 9. Test xem trước kết quả gộp (/api/merge/preview)
        res_pv_u = self.client.post(
            "/api/merge/preview",
            json={"id": sid, "table_a": 0, "table_b": 1, "mode": "UNION", "mappings": user_mappings},
            headers=hdrs
        )
        self.assertEqual(res_pv_u.status_code, 200)
        pv_u_body = res_pv_u.get_json()
        self.assertTrue(pv_u_body["success"])
        self.assertIn("headers", pv_u_body["data"])
        self.assertIn("preview_rows", pv_u_body["data"])
        self.assertEqual(len(pv_u_body["data"]["preview_rows"]), 4)

        res_pv_j = self.client.post(
            "/api/merge/preview",
            json={"id": sid, "table_a": 0, "table_b": 2, "mode": "JOIN", "key_a": "Mã KH", "key_b": "Mã KH", "join_type": "left"},
            headers=hdrs
        )
        self.assertEqual(res_pv_j.status_code, 200)
        pv_j_body = res_pv_j.get_json()
        self.assertTrue(pv_j_body["success"])
        self.assertEqual(pv_j_body["data"]["stats"]["matched_rows"], 2)

    def test_unauthenticated_blocked(self):
        # Thoát đăng nhập
        client = server.app.test_client()
        res = client.post("/api/merge/schema", json={"id": "abc", "table": 0}, headers={"X-Requested-With": "datadesk"})
        self.assertEqual(res.status_code, 401)

if __name__ == "__main__":
    unittest.main()
