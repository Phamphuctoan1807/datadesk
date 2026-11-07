"""Version History Engine for DataDesk (Stage C - Future 6, Mục 79).
Quản lý lịch sử phiên bản của dataset:
- Lưu snapshot các mốc quan trọng: Version 1 (Original), Version 2 (Cleaned), Version 3 (Merged), Version 4 (Transformed), Version 5 (Final)...
- Danh sách version kèm mốc thời gian, số dòng, số cột.
- Khôi phục (Restore) về một phiên bản trước.
- So sánh (Compare) sự khác biệt giữa hai phiên bản bất kỳ (cột thêm/bớt, biến động số dòng, mẫu ô thay đổi).
- Bộ kiểm tra đối chiếu độc lập independent_version_check.
"""

import datetime as dt
from typing import List, Dict, Any, Optional, Tuple

class VersionHistoryEngine:
    def __init__(self):
        # session_id -> { version_id: VersionDict }
        self._versions: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # session_id -> { table_idx: [version_id...] }
        self._table_version_order: Dict[str, Dict[int, List[str]]] = {}

    def clear_session(self, session_id: str):
        self._versions.pop(session_id, None)
        self._table_version_order.pop(session_id, None)

    def create_version(self, session_id: str, table_idx: int, label: str,
                       description: str, rows: List[List[Any]]) -> Dict[str, Any]:
        """Tạo snapshot phiên bản mới cho một bảng."""
        if not rows:
            raise ValueError("Không thể tạo phiên bản cho bảng dữ liệu rỗng.")

        if session_id not in self._versions:
            self._versions[session_id] = {}
            self._table_version_order[session_id] = {}

        t_order = self._table_version_order[session_id].setdefault(table_idx, [])
        v_num = len(t_order) + 1
        v_id = f"v_{table_idx}_{v_num}"

        header = list(rows[0])
        data_rows = [list(r) for r in rows[1:]]

        version_data = {
            "id": v_id,
            "table_index": table_idx,
            "version_number": v_num,
            "label": label or f"Phiên bản {v_num}",
            "description": description or "",
            "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "row_count": len(data_rows),
            "col_count": len(header),
            "columns": header,
            "rows": [header] + data_rows
        }

        self._versions[session_id][v_id] = version_data
        t_order.append(v_id)

        return version_data

    def list_versions(self, session_id: str, table_idx: int) -> List[Dict[str, Any]]:
        """Lấy danh sách tóm tắt các phiên bản của một bảng (không tải toàn bộ rows)."""
        t_order = self._table_version_order.get(session_id, {}).get(table_idx, [])
        all_v = self._versions.get(session_id, {})
        res = []
        for vid in t_order:
            v = all_v.get(vid)
            if v:
                res.append({
                    "id": v["id"],
                    "table_index": v["table_index"],
                    "version_number": v["version_number"],
                    "label": v["label"],
                    "description": v["description"],
                    "created_at": v["created_at"],
                    "row_count": v["row_count"],
                    "col_count": v["col_count"],
                    "columns": v["columns"]
                })
        return res

    def get_version(self, session_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết một phiên bản bao gồm dữ liệu hàng."""
        return self._versions.get(session_id, {}).get(version_id)

    def compare_versions(self, session_id: str, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        """So sánh sự khác biệt cấu trúc và dữ liệu giữa 2 phiên bản."""
        va = self.get_version(session_id, version_id_a)
        vb = self.get_version(session_id, version_id_b)

        if not va or not vb:
            raise ValueError("Không tìm thấy một trong hai phiên bản cần so sánh.")

        cols_a = set(va["columns"])
        cols_b = set(vb["columns"])

        added_cols = [c for c in vb["columns"] if c not in cols_a]
        removed_cols = [c for c in va["columns"] if c not in cols_b]
        common_cols = [c for c in vb["columns"] if c in cols_a]

        row_diff = vb["row_count"] - va["row_count"]

        # So sánh ô dữ liệu mẫu trên các cột chung và các dòng chung
        cell_changes = []
        rows_a = va["rows"]
        rows_b = vb["rows"]
        min_rows = min(len(rows_a), len(rows_b))

        col_map_a = {c: i for i, c in enumerate(va["columns"])}
        col_map_b = {c: i for i, c in enumerate(vb["columns"])}

        modified_cells_count = 0
        for r_idx in range(1, min_rows):
            ra = rows_a[r_idx]
            rb = rows_b[r_idx]
            for c in common_cols:
                ia = col_map_a[c]
                ib = col_map_b[c]
                va_cell = ra[ia] if ia < len(ra) else None
                vb_cell = rb[ib] if ib < len(rb) else None
                if va_cell != vb_cell:
                    modified_cells_count += 1
                    if len(cell_changes) < 20:
                        cell_changes.append({
                            "row_index": r_idx - 1,
                            "row_number": r_idx + 1,
                            "column": c,
                            "old_value": va_cell,
                            "new_value": vb_cell
                        })

        return {
            "version_a": {"id": va["id"], "label": va["label"], "row_count": va["row_count"]},
            "version_b": {"id": vb["id"], "label": vb["label"], "row_count": vb["row_count"]},
            "column_diff": {
                "added_columns": added_cols,
                "removed_columns": removed_cols,
                "common_columns_count": len(common_cols)
            },
            "row_diff": {
                "row_count_delta": row_diff,
                "is_expanded": row_diff > 0,
                "is_reduced": row_diff < 0
            },
            "cell_diff": {
                "modified_cells_count": modified_cells_count,
                "sample_changes": cell_changes
            }
        }

    def restore_version(self, session_id: str, version_id: str) -> Dict[str, Any]:
        """Khôi phục dữ liệu từ một phiên bản."""
        v = self.get_version(session_id, version_id)
        if not v:
            raise ValueError(f"Không tìm thấy phiên bản {version_id}.")
        return {
            "table_index": v["table_index"],
            "label": v["label"],
            "rows": [list(r) for r in v["rows"]],
            "version_id": version_id
        }

def independent_version_check(va: Dict[str, Any], vb: Dict[str, Any], diff: Dict[str, Any]) -> Tuple[bool, str]:
    """Kiểm tra đối chiếu độc lập tính toán diff phiên bản theo Mục 0 nguyên tắc 10."""
    expected_delta = vb["row_count"] - va["row_count"]
    if diff["row_diff"]["row_count_delta"] != expected_delta:
        return False, f"Chênh lệch số dòng {diff['row_diff']['row_count_delta']} không khớp với kỳ vọng {expected_delta}"
    return True, "Kiểm tra đối chiếu độc lập thành công"

VERSIONS = VersionHistoryEngine()
