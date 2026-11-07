"""Role-Based Access Control (RBAC) & Multi-User Engine for DataDesk (Stage C - Future 13, Mục 86).
Quản lý người dùng và phân quyền chi tiết:
- 4 vai trò chuẩn:
  1. ADMIN: Toàn quyền hệ thống, quản lý người dùng, cài đặt hệ thống.
  2. MANAGER: Phê duyệt quy trình (Approve workflow), duyệt và xử lý xung đột (Review conflicts), giải quyết trùng lặp.
  3. EDITOR: Tải lên dữ liệu (Upload), biến đổi (Transform), làm sạch (Clean), gộp bảng (Merge), xuất file (Export).
  4. VIEWER: Xem dữ liệu (View), xem trước biến đổi (Preview), tải báo cáo/file đã duyệt (Download).
- Cơ chế băm mật khẩu an toàn với Salt (PBKDF2-HMAC-SHA256).
- Bộ kiểm tra đối chiếu độc lập independent_rbac_check.
"""

import os
import json
import hashlib
import secrets
from typing import Dict, Any, Optional, List, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

ROLE_PERMISSIONS = {
    "VIEWER": {
        "view", "preview", "download", "export"
    },
    "EDITOR": {
        "view", "preview", "download", "export",
        "upload", "transform", "clean", "merge"
    },
    "MANAGER": {
        "view", "preview", "download", "export",
        "upload", "transform", "clean", "merge",
        "approve_workflow", "review_conflicts", "resolve_duplicates"
    },
    "ADMIN": {
        "view", "preview", "download", "export",
        "upload", "transform", "clean", "merge",
        "approve_workflow", "review_conflicts", "resolve_duplicates",
        "manage_users", "system_settings", "delete_all"
    }
}

class RBACEngine:
    def __init__(self, filepath: str = USERS_FILE):
        self.filepath = filepath
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            # Khởi tạo tài khoản admin mặc định nếu chưa có
            admin_salt = secrets.token_hex(16)
            admin_hash = self._hash_password("admin", admin_salt)
            init_users = {
                "admin": {
                    "username": "admin",
                    "role": "ADMIN",
                    "full_name": "Quản trị viên hệ thống",
                    "salt": admin_salt,
                    "password_hash": admin_hash,
                    "created_at": "2026-11-08 00:00:00"
                }
            }
            self._write_users(init_users)

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()

    def _read_users(self) -> Dict[str, Any]:
        try:
            if not os.path.exists(self.filepath):
                return {}
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_users(self, data: Dict[str, Any]):
        tmp = self.filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.filepath)

    def has_permission(self, role: str, action: str) -> bool:
        """Kiểm tra quyền thực hiện tác vụ của một vai trò."""
        role_upper = (role or "").upper().strip()
        allowed = ROLE_PERMISSIONS.get(role_upper, set())
        return action in allowed

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Xác thực người dùng qua tài khoản và mật khẩu."""
        users = self._read_users()
        user = users.get(username.strip().lower())
        if not user:
            return False, None, "Tài khoản không tồn tại."

        input_hash = self._hash_password(password, user["salt"])
        if secrets.compare_digest(input_hash, user["password_hash"]):
            return True, {
                "username": user["username"],
                "role": user["role"],
                "full_name": user.get("full_name", user["username"])
            }, None
        return False, None, "Mật khẩu không chính xác."

    def create_user(self, username: str, password: str, role: str, full_name: str = "") -> Dict[str, Any]:
        """Tạo người dùng mới với vai trò được cấp."""
        u_name = username.strip().lower()
        if not u_name:
            raise ValueError("Tên đăng nhập không được để trống.")
        role_upper = role.upper().strip()
        if role_upper not in ROLE_PERMISSIONS:
            raise ValueError(f"Vai trò không hợp lệ: {role}. Hỗ trợ: {', '.join(ROLE_PERMISSIONS.keys())}")

        users = self._read_users()
        if u_name in users:
            raise ValueError(f"Tài khoản '{u_name}' đã tồn tại.")

        salt = secrets.token_hex(16)
        user_record = {
            "username": u_name,
            "role": role_upper,
            "full_name": full_name or u_name,
            "salt": salt,
            "password_hash": self._hash_password(password, salt),
            "created_at": "2026-11-08 00:00:00"
        }
        users[u_name] = user_record
        self._write_users(users)

        return {
            "username": u_name,
            "role": role_upper,
            "full_name": user_record["full_name"]
        }

    def list_users(self) -> List[Dict[str, Any]]:
        """Lấy danh sách người dùng (không trả về hash mật khẩu)."""
        users = self._read_users()
        return [
            {
                "username": u["username"],
                "role": u["role"],
                "full_name": u.get("full_name", u["username"]),
                "created_at": u.get("created_at")
            }
            for u in users.values()
        ]

    def delete_user(self, username: str) -> bool:
        """Xóa một người dùng (ngoại trừ admin gốc)."""
        u_name = username.strip().lower()
        if u_name == "admin":
            raise ValueError("Không thể xóa tài khoản quản trị viên tối cao (admin).")
        users = self._read_users()
        if u_name in users:
            del users[u_name]
            self._write_users(users)
            return True
        return False

def independent_rbac_check(role: str, action: str, result: bool) -> Tuple[bool, str]:
    """Kiểm tra đối chiếu độc lập ma trận phân quyền theo Mục 0 nguyên tắc 10."""
    role_upper = (role or "").upper().strip()
    if role_upper == "ADMIN" and not result:
        return False, "ADMIN phải có toàn quyền cho mọi tác vụ hợp lệ"
    if role_upper == "VIEWER" and action in ("upload", "transform", "clean", "merge") and result:
        return False, f"VIEWER không được phép thực hiện tác vụ thay đổi: {action}"
    return True, "Kiểm tra đối chiếu độc lập thành công"

RBAC = RBACEngine()
