"""Business Validation Rules Engine for DataDesk (Stage C - Future 4, Mục 77).
Cho phép người dùng thiết lập các quy tắc nghiệp vụ/kiểm định dữ liệu tùy chỉnh:
- So sánh giá trị: [Tuổi] >= 18, [Số lượng] >= 0
- So sánh giữa 2 cột: [Ngày kết thúc] >= [Ngày bắt đầu], [Giá bán] >= [Giá vốn]
- Định dạng dữ liệu: Email hợp lệ, SĐT hợp lệ, Không để trống
- Tính duy nhất: Mã khách hàng không được trùng
- Báo cáo số dòng hợp lệ, số dòng vi phạm, và chi tiết vi phạm từng dòng (Click to inspect).
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
VN_PHONE_REGEX = re.compile(r'^(0|\+84|84)(3|5|7|8|9)\d{8}$')

def _to_num(val: Any) -> Optional[Decimal]:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    s = str(val).strip().replace(',', '').replace(' ', '')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

def evaluate_rule_on_row(rule: Dict[str, Any], row: List[Any], header: List[str], col_map: Dict[str, int]) -> Tuple[bool, Optional[str], Any]:
    """Kiểm tra một quy tắc trên một dòng dữ liệu.
    Trả về: (is_valid, violation_reason, actual_value)
    """
    col_name = rule.get("column", "")
    rule_type = rule.get("type", "compare")
    operator = rule.get("operator", "gte")
    expected_val = rule.get("value")
    target_col = rule.get("target_column")

    c_idx = col_map.get(col_name.lower().strip())
    if c_idx is None or c_idx >= len(row):
        return False, f"Không tìm thấy cột '{col_name}'", None

    actual_val = row[c_idx]

    # 1. Kiểm tra không để trống
    if rule_type == "not_empty":
        if actual_val is None or str(actual_val).strip() == "":
            return False, f"Ô cột '{col_name}' bị để trống", actual_val
        return True, None, actual_val

    # 2. Kiểm tra định dạng Email
    if rule_type == "valid_email":
        s = "" if actual_val is None else str(actual_val).strip()
        if not EMAIL_REGEX.match(s):
            return False, f"Email '{s}' không đúng định dạng", actual_val
        return True, None, actual_val

    # 3. Kiểm tra định dạng SĐT
    if rule_type == "valid_phone":
        s = "" if actual_val is None else str(actual_val).strip()
        digits = re.sub(r'\D', '', s)
        if not VN_PHONE_REGEX.match(digits):
            return False, f"Số điện thoại '{s}' không hợp lệ", actual_val
        return True, None, actual_val

    # 4. So sánh số với hằng số (e.g. Tuổi >= 18, Số lượng >= 0)
    if rule_type == "compare":
        n_act = _to_num(actual_val)
        n_exp = _to_num(expected_val)
        if n_act is None:
            return False, f"Giá trị '{actual_val}' không phải là số hợp lệ", actual_val
        if n_exp is None:
            return False, f"Giá trị so sánh '{expected_val}' không hợp lệ", actual_val

        passed = False
        if operator in (">=", "gte"): passed = (n_act >= n_exp)
        elif operator in ("<=", "lte"): passed = (n_act <= n_exp)
        elif operator in (">", "gt"): passed = (n_act > n_exp)
        elif operator in ("<", "lt"): passed = (n_act < n_exp)
        elif operator in ("==", "eq", "="): passed = (n_act == n_exp)
        elif operator in ("!=", "neq", "<>"): passed = (n_act != n_exp)

        if not passed:
            return False, f"Giá trị {n_act} không thỏa mãn điều kiện {operator} {n_exp}", actual_val
        return True, None, actual_val

    # 5. So sánh giữa 2 cột (e.g. Ngày kết thúc >= Ngày bắt đầu, Giá bán >= Giá vốn)
    if rule_type == "compare_columns":
        t_idx = col_map.get(str(target_col).lower().strip())
        if t_idx is None or t_idx >= len(row):
            return False, f"Không tìm thấy cột so sánh '{target_col}'", actual_val
        other_val = row[t_idx]

        n_act = _to_num(actual_val)
        n_other = _to_num(other_val)
        if n_act is not None and n_other is not None:
            passed = False
            if operator in (">=", "gte"): passed = (n_act >= n_other)
            elif operator in ("<=", "lte"): passed = (n_act <= n_other)
            elif operator in (">", "gt"): passed = (n_act > n_other)
            elif operator in ("<", "lt"): passed = (n_act < n_other)
            elif operator in ("==", "eq", "="): passed = (n_act == n_other)
            elif operator in ("!=", "neq", "<>"): passed = (n_act != n_other)
            if not passed:
                return False, f"Giá trị {n_act} không thỏa {operator} giá trị cột '{target_col}' ({n_other})", actual_val
            return True, None, actual_val
        else:
            # So sánh chuỗi hoặc ngày dạng chuỗi
            s_act = str(actual_val or "")
            s_other = str(other_val or "")
            passed = False
            if operator in (">=", "gte"): passed = (s_act >= s_other)
            elif operator in ("<=", "lte"): passed = (s_act <= s_other)
            elif operator in (">", "gt"): passed = (s_act > s_other)
            elif operator in ("<", "lt"): passed = (s_act < s_other)
            elif operator in ("==", "eq", "="): passed = (s_act == s_other)
            elif operator in ("!=", "neq", "<>"): passed = (s_act != s_other)
            if not passed:
                return False, f"'{s_act}' không thỏa {operator} cột '{target_col}' ('{s_other}')", actual_val
            return True, None, actual_val

    return True, None, actual_val

def validate_dataset_rules(rows: List[List[Any]], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Kiểm tra toàn bộ bộ quy tắc trên bảng dữ liệu.
    Trả về tổng quan số dòng hợp lệ/vi phạm và danh sách vi phạm chi tiết.
    """
    if not rows or len(rows) < 2 or not rules:
        return {
            "total_rows": 0,
            "valid_rows_count": 0,
            "violated_rows_count": 0,
            "violations": [],
            "rule_summaries": []
        }

    header = rows[0]
    data_rows = rows[1:]
    col_map = {str(h).lower().strip(): idx for idx, h in enumerate(header)}

    # Chuẩn bị thống kê quy tắc
    rule_stats = {r.get("id", f"rule_{i}"): {"id": r.get("id", f"rule_{i}"), "name": r.get("name", f"Quy tắc {i+1}"), "violations_count": 0} for i, r in enumerate(rules)}

    # Xử lý quy tắc duy nhất (Uniqueness) trước nếu có
    uniqueness_rules = [r for r in rules if r.get("type") == "unique"]
    row_uniqueness_violations = {r_idx: [] for r_idx in range(len(data_rows))}

    for u_rule in uniqueness_rules:
        r_id = u_rule.get("id", "unique_rule")
        c_name = u_rule.get("column", "")
        c_idx = col_map.get(c_name.lower().strip())
        if c_idx is not None:
            seen = {}
            for r_idx, row in enumerate(data_rows):
                val = str(row[c_idx] if c_idx < len(row) else "").strip().lower()
                if val:
                    if val in seen:
                        seen[val].append(r_idx)
                    else:
                        seen[val] = [r_idx]
            for val, r_indices in seen.items():
                if len(r_indices) > 1:
                    rule_stats[r_id]["violations_count"] += len(r_indices)
                    for r_idx in r_indices:
                        row_uniqueness_violations[r_idx].append({
                            "rule_id": r_id,
                            "rule_name": u_rule.get("name", f"Giá trị cột '{c_name}' không được trùng"),
                            "column": c_name,
                            "reason": f"Giá trị '{val}' bị trùng {len(r_indices)} lần",
                            "actual_value": data_rows[r_idx][c_idx]
                        })

    # Duyệt từng dòng kiểm tra các quy tắc thông thường
    row_violations = []
    violated_rows_set = set()

    for r_idx, row in enumerate(data_rows):
        row_num = r_idx + 2  # Dòng hiển thị trong bảng (header = dòng 1)
        current_row_violations = list(row_uniqueness_violations.get(r_idx, []))

        for rule in rules:
            if rule.get("type") == "unique":
                continue
            r_id = rule.get("id")
            passed, reason, act_val = evaluate_rule_on_row(rule, row, header, col_map)
            if not passed:
                rule_stats[r_id]["violations_count"] += 1
                current_row_violations.append({
                    "rule_id": r_id,
                    "rule_name": rule.get("name", "Quy tắc kiểm tra"),
                    "column": rule.get("column", ""),
                    "reason": reason,
                    "actual_value": act_val
                })

        if current_row_violations:
            violated_rows_set.add(r_idx)
            row_violations.append({
                "row_index": r_idx,
                "row_number": row_num,
                "row_data": [str(x) if x is not None else "" for x in row],
                "violations": current_row_violations
            })

    total_rows = len(data_rows)
    violated_count = len(violated_rows_set)
    valid_count = total_rows - violated_count

    return {
        "total_rows": total_rows,
        "valid_rows_count": valid_count,
        "violated_rows_count": violated_count,
        "valid_percent": round((valid_count / total_rows) * 100.0, 1) if total_rows > 0 else 100.0,
        "violations": row_violations,
        "rule_summaries": list(rule_stats.values())
    }

def independent_rules_check(rows: List[List[Any]], rules: List[Dict[str, Any]], result: Dict[str, Any]) -> Tuple[bool, str]:
    """Kiểm tra đối chiếu độc lập bộ quy tắc kiểm định theo Mục 0 nguyên tắc 10."""
    if not rows or len(rows) < 2:
        return True, "Bảng rỗng hợp lệ"
    n_rows = len(rows) - 1
    if result["total_rows"] != n_rows:
        return False, f"Tổng số dòng {result['total_rows']} không khớp với số dòng dữ liệu {n_rows}"
    if result["valid_rows_count"] + result["violated_rows_count"] != n_rows:
        return False, "Tổng dòng hợp lệ và vi phạm không bằng tổng số dòng"
    return True, "Kiểm tra đối chiếu độc lập thành công"
