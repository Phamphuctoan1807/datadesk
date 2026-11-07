"""
Kiểm thử bộ máy Saved Workflow / Preset Engine (Stage C - Future 1, Mục 74)
Chạy: python tests/test_preset.py
"""

import sys
import os
import json
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import preset_engine as PE

class TestPresetEngine(unittest.TestCase):
    def setUp(self):
        # Thiết lập tệp preset tạm thời cho kiểm thử
        self.orig_file = PE.PRESET_FILE
        PE.PRESET_FILE = os.path.join(PE.DATA_DIR, "test_presets_scratch.json")
        PE._write_all({})

    def tearDown(self):
        if os.path.exists(PE.PRESET_FILE):
            os.remove(PE.PRESET_FILE)
        PE.PRESET_FILE = self.orig_file

    def test_save_get_and_list_preset(self):
        steps = [
            {"type": "FORMULA", "target": "Thành tiền", "expression": "[Số lượng] * [Đơn giá]"},
            {"type": "NORMALIZE", "columns": ["Số điện thoại"], "categories": ["phone"]},
            {"type": "CONDITIONAL", "conditions": [{"col": "Thành tiền", "op": "gt", "val": 1000000}], "then": [{"type": "color_row", "color": "#FFE08A"}]}
        ]

        preset = PE.save_preset("Quy trình xử lý đơn hàng", steps, "Tính tiền và tô màu đơn lớn")
        self.assertIsNotNone(preset["id"])
        self.assertEqual(preset["name"], "Quy trình xử lý đơn hàng")
        self.assertEqual(len(preset["steps"]), 3)
        self.assertEqual(preset["version"], 1)

        # Trích xuất yêu cầu cột
        reqs = preset["column_requirements"]
        self.assertIn("Số lượng", reqs)
        self.assertIn("Đơn giá", reqs)
        self.assertIn("Số điện thoại", reqs)
        self.assertIn("Thành tiền", reqs)

        # Lấy lại preset
        retrieved = PE.get_preset(preset["id"])
        self.assertEqual(retrieved["name"], "Quy trình xử lý đơn hàng")

        # Liệt kê danh sách
        lst = PE.list_presets()
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["id"], preset["id"])

    def test_validate_preset_for_dataset(self):
        steps = [
            {"type": "FORMULA", "target": "Thành tiền", "expression": "[Số lượng] * [Đơn giá]"},
            {"type": "NORMALIZE", "columns": ["Số điện thoại"], "categories": ["phone"]}
        ]
        preset = PE.save_preset("Test Validate", steps)

        # Bảng 1: Có đủ cột -> Tương thích
        headers_ok = ["Mã KH", "Tên", "Số lượng", "Đơn giá", "Số điện thoại"]
        val_ok = PE.validate_preset_for_dataset(preset, headers_ok)
        self.assertTrue(val_ok["compatible"])
        self.assertEqual(len(val_ok["missing_columns"]), 0)

        # Bảng 2: Thiếu cột "Số lượng" -> Không tương thích
        headers_missing = ["Mã KH", "Tên", "Đơn giá", "Số điện thoại"]
        val_miss = PE.validate_preset_for_dataset(preset, headers_missing)
        self.assertFalse(val_miss["compatible"])
        self.assertIn("Số lượng", val_miss["missing_columns"])

        # Bảng 3: Cột khác dấu tiếng Việt (so khớp chuẩn hóa) -> Gợi ý ánh xạ
        headers_accents = ["Mã KH", "Tên", "So luong", "Don gia", "So dien thoai"]
        val_acc = PE.validate_preset_for_dataset(preset, headers_accents)
        self.assertIn("Số lượng", val_acc["suggested_mapping"])
        self.assertEqual(val_acc["suggested_mapping"]["Số lượng"], "So luong")

    def test_adapt_steps_with_mapping(self):
        steps = [
            {"type": "FORMULA", "target": "Thành tiền", "expression": "[Số lượng] * [Đơn giá]"},
            {"type": "NORMALIZE", "columns": ["Số điện thoại"], "categories": ["phone"]}
        ]
        mapping = {
            "Số lượng": "Quantity",
            "Đơn giá": "Price",
            "Số điện thoại": "Phone"
        }

        adapted = PE.adapt_steps_with_mapping(steps, mapping)
        self.assertEqual(adapted[0]["expression"], "[Quantity] * [Price]")
        self.assertEqual(adapted[1]["columns"], ["Phone"])

    def test_export_and_import_preset(self):
        steps = [
            {"type": "FORMULA", "target": "Cột mới", "expression": "[A] + [B]"}
        ]
        preset = PE.save_preset("Mẫu Xuất Nhập", steps, "Mô tả mẫu")

        # Xuất JSON
        json_str = PE.export_preset_json(preset["id"])
        self.assertIn("datadesk_preset_version", json_str)
        self.assertIn("Mẫu Xuất Nhập", json_str)

        # Nhập lại JSON
        imported = PE.import_preset_json(json_str)
        self.assertIn("Mẫu Xuất Nhập", imported["name"])
        self.assertEqual(len(imported["steps"]), 1)

    def test_delete_preset(self):
        steps = [{"type": "FORMULA", "target": "X", "expression": "1"}]
        preset = PE.save_preset("Xóa tôi", steps)
        pid = preset["id"]

        self.assertIsNotNone(PE.get_preset(pid))
        del_res = PE.delete_preset(pid)
        self.assertTrue(del_res)
        self.assertIsNone(PE.get_preset(pid))

import io
import server

class TestPresetAPI(unittest.TestCase):
    def setUp(self):
        server.PW = "matkhautest123"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        self.orig_file = PE.PRESET_FILE
        PE.PRESET_FILE = os.path.join(PE.DATA_DIR, "test_presets_api_scratch.json")
        PE._write_all({})

        # Nạp bảng mẫu
        csv_data = "Mã KH,Số lượng,Đơn giá,Số điện thoại\nKH01,5,20000,0912345678\nKH02,2,50000,0987654321"
        data = {"file": (io.BytesIO(csv_data.encode("utf-8")), "orders.csv")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data", headers={"X-Requested-With": "datadesk"})
        self.sid = res.get_json()["id"]

    def tearDown(self):
        if os.path.exists(PE.PRESET_FILE):
            os.remove(PE.PRESET_FILE)
        PE.PRESET_FILE = self.orig_file

    def test_preset_api_full_flow(self):
        hdrs = {"X-Requested-With": "datadesk"}

        # 1. Thêm 1 công thức vào bảng
        f_body = {"id": self.sid, "table": 0, "header": True, "target": "Thành tiền", "expression": "[Số lượng] * [Đơn giá]"}
        res_f = self.client.post("/api/formula/apply", json=f_body, headers=hdrs)
        self.assertEqual(res_f.status_code, 200)

        # 2. Lưu thành Preset qua /api/preset/save
        save_body = {"id": self.sid, "table": 0, "name": "Tính đơn hàng", "description": "Nhân số lượng với đơn giá"}
        res_save = self.client.post("/api/preset/save", json=save_body, headers=hdrs)
        self.assertEqual(res_save.status_code, 200)
        s_data = res_save.get_json()
        self.assertTrue(s_data["success"])
        pid = s_data["data"]["preset"]["id"]

        # 3. Lấy danh sách Preset qua /api/preset/list
        res_list = self.client.get("/api/preset/list", headers=hdrs)
        self.assertEqual(res_list.status_code, 200)
        l_data = res_list.get_json()
        self.assertEqual(len(l_data["data"]["presets"]), 1)
        self.assertEqual(l_data["data"]["presets"][0]["id"], pid)

        # 4. Kiểm tra tương thích qua /api/preset/validate
        val_body = {"id": self.sid, "table": 0, "preset_id": pid}
        res_val = self.client.post("/api/preset/validate", json=val_body, headers=hdrs)
        self.assertEqual(res_val.status_code, 200)
        v_data = res_val.get_json()
        self.assertTrue(v_data["data"]["validation"]["compatible"])

        # 5. Áp dụng Preset vào bảng qua /api/preset/apply
        apply_body = {"id": self.sid, "table": 0, "preset_id": pid}
        res_app = self.client.post("/api/preset/apply", json=apply_body, headers=hdrs)
        self.assertEqual(res_app.status_code, 200)
        a_data = res_app.get_json()
        self.assertTrue(a_data["success"])
        self.assertEqual(len(a_data["data"]["state"]["list"]), 1)

        # 6. Xuất Preset qua /api/preset/export
        exp_body = {"preset_id": pid}
        res_exp = self.client.post("/api/preset/export", json=exp_body, headers=hdrs)
        self.assertEqual(res_exp.status_code, 200)
        json_content = res_exp.get_json()["data"]["json_content"]

        # 7. Nhập Preset qua /api/preset/import
        imp_body = {"json_content": json_content}
        res_imp = self.client.post("/api/preset/import", json=imp_body, headers=hdrs)
        self.assertEqual(res_imp.status_code, 200)
        self.assertTrue(res_imp.get_json()["success"])

        # 8. Xóa Preset qua /api/preset/delete
        del_body = {"preset_id": pid}
        res_del = self.client.post("/api/preset/delete", json=del_body, headers=hdrs)
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()["data"]["deleted"])

if __name__ == "__main__":
    unittest.main()
