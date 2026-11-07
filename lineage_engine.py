"""Data Lineage & Explainability Engine for DataDesk (Stage C - Future 5 & Future 7, Mục 78 & 80).
Theo vết nguồn gốc dữ liệu (Data Lineage) và giải trình biến đổi (Explainability) tới từng ô:
- Giá trị hiện tại (Current Value)
- Nguồn gốc gốc rễ (Source File, Sheet, Row, Column)
- Chuỗi biến đổi (Transformations: Formula, Conditional Rule, Normalize, Cleaning, Merge)
- Đối chiếu giá trị cũ -> giá trị mới và lý do cụ thể (Explainability).
- Hỗ trợ truy vết ngược (Backtrace Graph).
"""

from typing import List, Dict, Any, Optional, Tuple

class DataLineageEngine:
    def __init__(self):
        # session_id -> { (table_idx, row_idx, col_idx): [LineageNode] }
        self._lineage_store: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def _key(self, table_idx: int, row_idx: int, col_name: str) -> str:
        return f"{table_idx}:{row_idx}:{col_name.lower().strip()}"

    def record_cell_step(self, session_id: str, table_idx: int, row_idx: int, col_name: str,
                         old_val: Any, new_val: Any, step_type: str,
                         rule_name: str, formula_or_expr: Optional[str] = None,
                         source_file: Optional[str] = None, source_sheet: Optional[str] = None,
                         source_row: Optional[int] = None):
        """Ghi nhận một bước biến đổi trên một ô dữ liệu."""
        if session_id not in self._lineage_store:
            self._lineage_store[session_id] = {}

        k = self._key(table_idx, row_idx, col_name)
        if k not in self._lineage_store[session_id]:
            # Khởi tạo node gốc nếu có
            self._lineage_store[session_id][k] = [{
                "step": 0,
                "type": "ORIGINAL",
                "value": old_val if step_type != "ORIGINAL" else new_val,
                "reason": "Dữ liệu gốc nạp từ file",
                "source": {
                    "file": source_file or "unknown",
                    "sheet": source_sheet or "Sheet1",
                    "row": source_row if source_row is not None else (row_idx + 2),
                    "column": col_name
                }
            }]
            if step_type == "ORIGINAL":
                return

        history = self._lineage_store[session_id][k]
        history.append({
            "step": len(history),
            "type": step_type,
            "old_value": old_val,
            "new_value": new_val,
            "rule_name": rule_name,
            "expression": formula_or_expr,
            "reason": f"{step_type}: {rule_name}" + (f" ({formula_or_expr})" if formula_or_expr else ""),
            "source": {
                "file": source_file or history[0]["source"]["file"],
                "sheet": source_sheet or history[0]["source"]["sheet"],
                "row": source_row if source_row is not None else history[0]["source"]["row"],
                "column": col_name
            }
        })

    def get_cell_lineage(self, session_id: str, table_idx: int, row_idx: int, col_name: str,
                         current_val: Any = None, rows: Optional[List[List[Any]]] = None,
                         header: Optional[List[str]] = None, ops_list: Optional[List[Dict[str, Any]]] = None,
                         source_name: Optional[str] = None) -> Dict[str, Any]:
        """Truy xuất toàn bộ chuỗi nguồn gốc và giải trình của một ô dữ liệu."""
        k = self._key(table_idx, row_idx, col_name)
        history = self._lineage_store.get(session_id, {}).get(k, [])

        # Nếu chưa có trong store, tự động suy diễn từ quy trình biến đổi hiện tại
        if not history and ops_list is not None and header is not None:
            inferred = []
            orig_row_num = row_idx + 2
            src_info = {
                "file": source_name or "data.xlsx",
                "sheet": f"Bảng {table_idx + 1}",
                "row": orig_row_num,
                "column": col_name
            }

            # Node gốc
            inferred.append({
                "step": 0,
                "type": "ORIGINAL",
                "value": current_val,
                "reason": "Dữ liệu ban đầu",
                "source": src_info
            })

            # Duyệt các bước biến đổi xem có bước nào tác động vào cột này không
            for op_idx, op in enumerate(ops_list):
                if not op.get("enabled", True):
                    continue
                op_type = op.get("type", "FORMULA")
                target = op.get("target") or ""
                if str(target).lower().strip() == col_name.lower().strip():
                    inferred.append({
                        "step": len(inferred),
                        "type": op_type,
                        "rule_name": op.get("name") or f"Bước {op_idx + 1}",
                        "expression": op.get("expression") or "",
                        "reason": f"Được tính từ công thức: {op.get('expression')}",
                        "source": src_info
                    })
                elif op_type == "NORMALIZE" and col_name in (op.get("columns") or []):
                    inferred.append({
                        "step": len(inferred),
                        "type": "NORMALIZE",
                        "rule_name": op.get("name") or "Chuẩn hóa",
                        "reason": f"Chuẩn hóa dữ liệu ({op.get('kind')})",
                        "source": src_info
                    })
            history = inferred

        first_node = history[0] if history else {}
        source = first_node.get("source", {
            "file": source_name or "file.xlsx",
            "sheet": f"Bảng {table_idx + 1}",
            "row": row_idx + 2,
            "column": col_name
        })

        return {
            "cell": {
                "table_index": table_idx,
                "row_index": row_idx,
                "row_number": row_idx + 2,
                "column": col_name,
                "current_value": current_val
            },
            "root_source": source,
            "lineage_chain": history,
            "summary_explain": history[-1].get("reason", "Dữ liệu ban đầu") if history else "Không có biến đổi"
        }

    def clear_session(self, session_id: str):
        self._lineage_store.pop(session_id, None)

LINEAGE = DataLineageEngine()
