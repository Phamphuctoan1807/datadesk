"""Tests for Multi-User & RBAC Engine (Stage C - Future 13, Mục 86)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rbac_engine import RBACEngine, independent_rbac_check

class TestRBACEngine(unittest.TestCase):

    def setUp(self):
        self.test_file = os.path.join(ROOT, "data", "test_users_scratch.json")
        self.rbac = RBACEngine(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_permission_matrix(self):
        # Viewer
        self.assertTrue(self.rbac.has_permission("VIEWER", "view"))
        self.assertTrue(self.rbac.has_permission("VIEWER", "download"))
        self.assertFalse(self.rbac.has_permission("VIEWER", "transform"))
        self.assertFalse(self.rbac.has_permission("VIEWER", "upload"))

        # Editor
        self.assertTrue(self.rbac.has_permission("EDITOR", "upload"))
        self.assertTrue(self.rbac.has_permission("EDITOR", "transform"))
        self.assertFalse(self.rbac.has_permission("EDITOR", "approve_workflow"))

        # Manager
        self.assertTrue(self.rbac.has_permission("MANAGER", "approve_workflow"))
        self.assertTrue(self.rbac.has_permission("MANAGER", "review_conflicts"))
        self.assertFalse(self.rbac.has_permission("MANAGER", "manage_users"))

        # Admin
        self.assertTrue(self.rbac.has_permission("ADMIN", "manage_users"))
        self.assertTrue(self.rbac.has_permission("ADMIN", "system_settings"))
        self.assertTrue(self.rbac.has_permission("ADMIN", "transform"))

        # Independent check
        chk_ok, msg = independent_rbac_check("ADMIN", "transform", True)
        self.assertTrue(chk_ok)
        chk_ok2, _ = independent_rbac_check("VIEWER", "transform", False)
        self.assertTrue(chk_ok2)

    def test_authentication_and_user_crud(self):
        # Authenticate default admin
        ok, user, err = self.rbac.authenticate("admin", "admin")
        self.assertTrue(ok)
        self.assertEqual(user["role"], "ADMIN")

        # Create new Editor
        u = self.rbac.create_user("toan_editor", "password123", "EDITOR", "Toan Pham")
        self.assertEqual(u["username"], "toan_editor")
        self.assertEqual(u["role"], "EDITOR")

        # Authenticate new user
        ok_toan, user_toan, _ = self.rbac.authenticate("toan_editor", "password123")
        self.assertTrue(ok_toan)
        self.assertEqual(user_toan["full_name"], "Toan Pham")

        # Wrong password
        bad_ok, _, err = self.rbac.authenticate("toan_editor", "wrongpass")
        self.assertFalse(bad_ok)
        self.assertIn("Mật khẩu không chính xác", err)

        # List users
        users = self.rbac.list_users()
        self.assertGreaterEqual(len(users), 2)

        # Delete user
        del_ok = self.rbac.delete_user("toan_editor")
        self.assertTrue(del_ok)

        # Admin cannot be deleted
        with self.assertRaises(ValueError):
            self.rbac.delete_user("admin")


class TestRBACAPI(unittest.TestCase):
    def setUp(self):
        import server
        server.PW = "admin"
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with self.client.session_transaction() as sess:
            sess["ok"] = True
            sess["role"] = "ADMIN"

    def test_rbac_api_users_list(self):
        hdrs = {"X-Requested-With": "datadesk"}
        res = self.client.get("/api/auth/users", headers=hdrs)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("users", data["data"])

if __name__ == "__main__":
    unittest.main()
