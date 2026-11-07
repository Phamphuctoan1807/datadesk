"""Tests for Advanced Data Cleaning Engine (Stage C - Future 2, Mục 75)."""
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cleaning_engine as CE

class TestAdvancedDataCleaning(unittest.TestCase):

    def test_text_cleaning(self):
        # 1. Trim & Collapse spaces
        raw = "   Nguyen   Van    An   \t  "
        self.assertEqual(CE.clean_text(raw), "Nguyen Van An")

        # 2. Case transformations
        self.assertEqual(CE.clean_text("nguyễn văn an", case="upper"), "NGUYỄN VĂN AN")
        self.assertEqual(CE.clean_text("NGUYỄN VĂN AN", case="lower"), "nguyễn văn an")
        self.assertEqual(CE.clean_text("nguyễn văn an", case="title"), "Nguyễn Văn An")
        self.assertEqual(CE.clean_text("nguyễn văn an", case="sentence"), "Nguyễn văn an")

        # 3. Vietnamese accent removal
        vn_text = "Đại học Bách Khoa Hà Nội - Việt Nam (Ươ, Ơ, Ô, Ê, Đ, Ă, Â)"
        stripped = CE.strip_vietnamese_accents(vn_text)
        self.assertEqual(stripped, "Dai hoc Bach Khoa Ha Noi - Viet Nam (Uo, O, O, E, D, A, A)")

        # 4. Invisible chars & Unicode normalization
        text_with_zwsp = "Data\u200BDesk\uFEFF\u200E"
        self.assertEqual(CE.clean_text(text_with_zwsp, remove_invisible=True), "DataDesk")

        # 5. Null or empty string handling
        self.assertEqual(CE.clean_text(None), "")
        self.assertEqual(CE.clean_text("   "), "")

    def test_phone_cleaning(self):
        # Valid Vietnam mobile phones
        p1 = "0912 345 678"
        p2 = "+84 912.345.678"
        p3 = "84912345678"
        p4 = "0084912345678"
        p5 = "912345678"  # 9 digits without leading 0

        self.assertEqual(CE.clean_phone(p1, output_format='vn_standard')[0], "0912345678")
        self.assertEqual(CE.clean_phone(p2, output_format='vn_standard')[0], "0912345678")
        self.assertEqual(CE.clean_phone(p3, output_format='vn_standard')[0], "0912345678")
        self.assertEqual(CE.clean_phone(p4, output_format='vn_standard')[0], "0912345678")
        self.assertEqual(CE.clean_phone(p5, output_format='vn_standard')[0], "0912345678")

        # Various formats
        self.assertEqual(CE.clean_phone(p1, output_format='vn_grouped')[0], "0912 345 678")
        self.assertEqual(CE.clean_phone(p1, output_format='e164')[0], "+84912345678")
        self.assertEqual(CE.clean_phone(p1, output_format='intl_grouped')[0], "+84 912 345 678")
        self.assertEqual(CE.clean_phone(p1, output_format='national')[0], "84912345678")

        # Invalid phone lengths or prefixes
        bad1, valid1, err1 = CE.clean_phone("12345")
        self.assertFalse(valid1)
        self.assertEqual(err1, "INVALID_PHONE_LENGTH")

        bad2, valid2, err2 = CE.clean_phone("0112345678")
        self.assertFalse(valid2)
        self.assertEqual(err2, "UNKNOWN_PHONE_PREFIX")

        # Empty
        val_empty, valid_empty, _ = CE.clean_phone("")
        self.assertEqual(val_empty, "")
        self.assertTrue(valid_empty)

    def test_email_cleaning(self):
        # Standard cleaning & typo domain correction
        e1, valid, _ = CE.clean_email("  User.Name@GMAIL.COM  ")
        self.assertTrue(valid)
        self.assertEqual(e1, "user.name@gmail.com")

        # Typo correction: @gmai.com -> @gmail.com, hotmial.com -> hotmail.com
        e2, valid, _ = CE.clean_email("toan@gmai.com")
        self.assertTrue(valid)
        self.assertEqual(e2, "toan@gmail.com")

        e3, valid, _ = CE.clean_email("contact@hotmial.com")
        self.assertTrue(valid)
        self.assertEqual(e3, "contact@hotmail.com")

        # Stripping enclosing angle brackets <test@domain.com>
        e4, valid, _ = CE.clean_email("<sales@datadesk.vn>")
        self.assertTrue(valid)
        self.assertEqual(e4, "sales@datadesk.vn")

        # Invalid formats
        _, valid, err = CE.clean_email("not-an-email")
        self.assertFalse(valid)
        self.assertEqual(err, "INVALID_EMAIL_FORMAT")

        _, valid, err = CE.clean_email("user@@domain.com")
        self.assertFalse(valid)
        self.assertEqual(err, "INVALID_EMAIL_FORMAT")

    def test_numeric_currency_percentage(self):
        # Numeric EU/VN format with dots for thousands and comma for decimal
        n1, valid, _ = CE.clean_number("1.234.567,89")
        self.assertTrue(valid)
        self.assertEqual(n1, Decimal("1234567.89"))

        # Numeric US format with commas for thousands and dot for decimal
        n2, valid, _ = CE.clean_number("1,234,567.89")
        self.assertTrue(valid)
        self.assertEqual(n2, Decimal("1234567.89"))

        # Multiple thousands separators
        n3, valid, _ = CE.clean_number("10.000.000")
        self.assertTrue(valid)
        self.assertEqual(n3, Decimal("10000000"))

        # Currency
        c1 = CE.clean_currency("1.500.000 ₫")
        self.assertTrue(c1["valid"])
        self.assertEqual(c1["amount"], Decimal("1500000"))
        self.assertEqual(c1["currency"], "VND")

        c2 = CE.clean_currency("$ 250.50")
        self.assertTrue(c2["valid"])
        self.assertEqual(c2["amount"], Decimal("250.50"))
        self.assertEqual(c2["currency"], "USD")

        c3 = CE.clean_currency("99.9 €")
        self.assertTrue(c3["valid"])
        self.assertEqual(c3["amount"], Decimal("99.9"))
        self.assertEqual(c3["currency"], "EUR")

        # Percentage
        pct1 = CE.clean_percentage(" 18.5 % ", as_ratio=True)
        self.assertTrue(pct1["valid"])
        self.assertEqual(pct1["value"], Decimal("0.185"))

        pct2 = CE.clean_percentage("10%", as_ratio=False)
        self.assertTrue(pct2["valid"])
        self.assertEqual(pct2["value"], Decimal("10"))

    def test_find_and_replace(self):
        dataset = [
            ["ID", "Name", "City"],
            ["1", "Toan Pham", "HN"],
            ["2", "Lan Anh", "HCM"],
            ["3", "Minh Toan", "HN"],
        ]

        # 1. Preview
        preview = CE.preview_find_replace(dataset, [1], "Toan", "Toàn", match_type="contains")
        self.assertEqual(preview["matches_count"], 2)
        self.assertEqual(preview["affected_rows"], 2)
        self.assertEqual(len(preview["preview_items"]), 2)

        # 2. Apply (Verify immutability: original dataset must not be modified)
        orig_copy = [list(r) for r in dataset]
        new_data, stats = CE.apply_find_replace(dataset, [1], "Toan", "Toàn", match_type="contains")
        self.assertEqual(dataset, orig_copy, "Dataset gốc không được bị biến đổi in-place")
        self.assertEqual(stats["affected_cells"], 2)
        self.assertEqual(new_data[1][1], "Toàn Pham")
        self.assertEqual(new_data[3][1], "Minh Toàn")

        # 3. Exact match
        new_data_exact, stats_exact = CE.apply_find_replace(dataset, [2], "HN", "Hà Nội", match_type="exact")
        self.assertEqual(stats_exact["affected_cells"], 2)
        self.assertEqual(new_data_exact[1][2], "Hà Nội")
        self.assertEqual(new_data_exact[3][2], "Hà Nội")
        self.assertEqual(new_data_exact[2][2], "HCM")

        # 4. Safe regex check
        safe, err = CE.validate_regex_pattern(r"(a+)+")
        self.assertFalse(safe)
        self.assertIn("ReDoS", err)

        safe_valid, _ = CE.validate_regex_pattern(r"^HN|HCM$")
        self.assertTrue(safe_valid)

        # 5. Regex replace
        new_data_rgx, stats_rgx = CE.apply_find_replace(dataset, [2], r"^(HN|HCM)$", r"City_\1", is_regex=True)
        self.assertEqual(stats_rgx["affected_cells"], 3)
        self.assertEqual(new_data_rgx[1][2], "City_HN")
        self.assertEqual(new_data_rgx[2][2], "City_HCM")

    def test_duplicate_management(self):
        dataset = [
            ["ID", "Name", "Phone"],
            ["1", "Nguyen Van An", "0912345678"],
            ["2", "Nguyen Van An", "0912345678"],  # Exact dup of 1
            ["3", "nguyen van an", "0912345678"],  # Normalized dup of 1
            ["4", "Nguyen Van Anh", "0912345678"], # Fuzzy dup of 1
            ["5", "Tran Thi B", "0987654321"],
        ]

        # Exact
        exact_dup = CE.find_duplicates(dataset, key_cols=[1, 2], mode="exact")
        self.assertEqual(exact_dup["total_duplicates"], 1)
        self.assertEqual(exact_dup["duplicate_row_indices"], [2])

        # Normalized
        norm_dup = CE.find_duplicates(dataset, key_cols=[1, 2], mode="normalized")
        self.assertEqual(norm_dup["total_duplicates"], 2)
        self.assertIn(2, norm_dup["duplicate_row_indices"])
        self.assertIn(3, norm_dup["duplicate_row_indices"])

        # Fuzzy
        fuzzy_dup = CE.find_duplicates(dataset, key_cols=[1, 2], mode="fuzzy", threshold=0.80)
        self.assertGreaterEqual(fuzzy_dup["total_duplicates"], 2)

        # Deduplicate keep_first
        dedup_first, stats_first = CE.deduplicate_dataset(dataset, key_cols=[1, 2], mode="exact", strategy="keep_first")
        self.assertEqual(stats_first["removed_count"], 1)
        self.assertEqual(len(dedup_first), 5)
        self.assertEqual(dedup_first[1][0], "1")

        # Deduplicate keep_last
        dedup_last, stats_last = CE.deduplicate_dataset(dataset, key_cols=[1, 2], mode="exact", strategy="keep_last")
        self.assertEqual(stats_last["removed_count"], 1)
        self.assertEqual(len(dedup_last), 5)
        self.assertEqual(dedup_last[1][0], "2")

        # Deduplicate remove_all
        dedup_none, stats_none = CE.deduplicate_dataset(dataset, key_cols=[1, 2], mode="exact", strategy="remove_all")
        self.assertEqual(stats_none["removed_count"], 2)
        self.assertEqual(len(dedup_none), 4)

        # Independent check
        chk = CE.independent_cleaning_check(dataset, dedup_first, "deduplicate", strategy="keep_first")
        self.assertTrue(chk["valid"])

    def test_similarity_metrics(self):
        # Levenshtein distance
        self.assertEqual(CE.levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(CE.levenshtein_distance("hello", "hello"), 0)
        self.assertEqual(CE.levenshtein_distance("", "test"), 4)

        # String similarity
        sim_exact = CE.string_similarity("Nguyen Van A", "Nguyen Van A")
        self.assertEqual(sim_exact, 1.0)

        sim_reordered = CE.string_similarity("Nguyen Van A", "Van Nguyen A")
        self.assertGreater(sim_reordered, 0.8)


class TestCleaningAPI(unittest.TestCase):
    def setUp(self):
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True

        self.sid = "test_clean_sid_01"
        server.STORE[self.sid] = {
            "name": "data.xlsx",
            "tables": [
                {
                    "name": "Khách hàng",
                    "rows": [
                        ["ID", "Họ tên", "Số điện thoại", "Email"],
                        ["1", "  nguyễn văn an  ", "0912 345 678", "an@gmai.com"],
                        ["2", "Nguyen Van An", "+84912345678", "an@gmail.com"],
                        ["3", "Trần Thị Bình", "0987654321", "binh@datadesk.vn"],
                    ]
                }
            ],
            "ops": {
                0: {"list": [], "undo": [], "redo": [], "log": []}
            },
            "cache": {}
        }

    def tearDown(self):
        import server
        server.STORE.pop(self.sid, None)

    def test_find_replace_api(self):
        hdrs = {"X-Requested-With": "datadesk"}

        # 1. Preview
        p_body = {
            "id": self.sid,
            "table": 0,
            "columns": ["Email"],
            "find_val": "gmai.com",
            "replace_val": "gmail.com",
            "match_type": "contains"
        }
        res_p = self.client.post("/api/clean/find_replace/preview", json=p_body, headers=hdrs)
        self.assertEqual(res_p.status_code, 200)
        p_data = res_p.get_json()
        self.assertTrue(p_data["success"])
        self.assertEqual(p_data["data"]["matches_count"], 1)

        # 2. Apply in-place
        a_body = dict(p_body, target_mode="in_place")
        res_a = self.client.post("/api/clean/find_replace/apply", json=a_body, headers=hdrs)
        self.assertEqual(res_a.status_code, 200)
        a_data = res_a.get_json()
        self.assertTrue(a_data["success"])
        self.assertEqual(a_data["data"]["stats"]["affected_cells"], 1)

    def test_duplicates_api(self):
        hdrs = {"X-Requested-With": "datadesk"}

        # 1. Detect normalized duplicates
        d_body = {
            "id": self.sid,
            "table": 0,
            "columns": ["Họ tên"],
            "mode": "normalized"
        }
        res_d = self.client.post("/api/clean/duplicates/detect", json=d_body, headers=hdrs)
        self.assertEqual(res_d.status_code, 200)
        d_data = res_d.get_json()
        self.assertTrue(d_data["success"])
        self.assertEqual(d_data["data"]["total_duplicates"], 1)

        # 2. Remove duplicates (new table)
        r_body = {
            "id": self.sid,
            "table": 0,
            "columns": ["Họ tên"],
            "mode": "normalized",
            "strategy": "keep_first",
            "target_mode": "new_table"
        }
        res_r = self.client.post("/api/clean/duplicates/remove", json=r_body, headers=hdrs)
        self.assertEqual(res_r.status_code, 200)
        r_data = res_r.get_json()
        self.assertTrue(r_data["success"])
        self.assertEqual(r_data["data"]["stats"]["removed_count"], 1)
        self.assertEqual(r_data["data"]["name"], "[Lọc trùng] Khách hàng")

    def test_format_clean_api(self):
        hdrs = {"X-Requested-With": "datadesk"}

        # Clean text: Title Case & trim
        c_body = {
            "id": self.sid,
            "table": 0,
            "columns": ["Họ tên"],
            "kind": "text",
            "options": {"trim": True, "collapse_spaces": True, "case": "title"},
            "target_mode": "in_place"
        }
        res_c = self.client.post("/api/clean/format/apply", json=c_body, headers=hdrs)
        self.assertEqual(res_c.status_code, 200)
        c_data = res_c.get_json()
        self.assertTrue(c_data["success"])
        self.assertGreaterEqual(c_data["data"]["stats"]["changed_cells"], 1)


if __name__ == "__main__":
    unittest.main()
