"""Data Quality Score Engine for DataDesk (Stage C - Future 3, Mục 76).
Tính toán điểm chất lượng dữ liệu 0-100 với 4 chỉ số thành phần giải thích được:
1. Completeness (Độ đầy đủ)
2. Consistency (Độ nhất quán)
3. Validity (Độ hợp lệ nghiệp vụ)
4. Uniqueness (Độ duy nhất)

Cung cấp bảng giải trình điểm số chi tiết (Explainable Deductions):
Mỗi điểm bị trừ đều có nguyên nhân, số dòng/ô vi phạm và gợi ý khắc phục.
Tuyệt đối KHÔNG tuyên bố 'Accuracy' khi không có nguồn dữ liệu đối chứng độc lập.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

NULL_TOKENS = {
    "", "null", "none", "nil", "n/a", "na", "#n/a", "-", "--", "không có", "khong co", "nan", "undefined"
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
VN_PHONE_REGEX = re.compile(r'^(0|\+84|84)(3|5|7|8|9)\d{8}$')

def is_blank(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in NULL_TOKENS

def compute_quality_score(rows: List[List[Any]], key_cols: Optional[List[int]] = None) -> Dict[str, Any]:
    """Tính toán điểm chất lượng dữ liệu toàn diện (0-100) và 4 chỉ số thành phần."""
    if not rows or len(rows) < 2:
        return {
            "overall_score": 100.0,
            "status": "SAFE",
            "metrics": {
                "completeness": 100.0,
                "consistency": 100.0,
                "validity": 100.0,
                "uniqueness": 100.0
            },
            "deductions": [],
            "summary": "Bộ dữ liệu rỗng hoặc chỉ có tiêu đề."
        }

    header = rows[0]
    data_rows = rows[1:]
    n_rows = len(data_rows)
    n_cols = len(header)
    total_cells = n_rows * n_cols

    deductions = []

    # ---------------------------------------------------------
    # 1. COMPLETENESS (ĐỘ ĐẦY ĐỦ) - Trọng số 30%
    # ---------------------------------------------------------
    empty_cells_count = 0
    col_empty_counts = [0] * n_cols

    for r in data_rows:
        for c in range(n_cols):
            val = r[c] if c < len(r) else None
            if is_blank(val):
                empty_cells_count += 1
                col_empty_counts[c] += 1

    completeness_ratio = 1.0 - (empty_cells_count / total_cells) if total_cells > 0 else 1.0
    completeness_score = round(completeness_ratio * 100.0, 1)

    # Giải thích trừ điểm Completeness (tối đa 30 điểm)
    completeness_penalty = round((1.0 - completeness_ratio) * 30.0, 1)
    if completeness_penalty > 0:
        for c, cnt in enumerate(col_empty_counts):
            if cnt > 0:
                c_penalty = round((cnt / total_cells) * 30.0, 1)
                deductions.append({
                    "category": "Completeness",
                    "column": header[c],
                    "penalty": c_penalty,
                    "count": cnt,
                    "reason": f"Có {cnt} ô để trống hoặc giá trị rỗng (N/A, null)",
                    "fix": f"Bổ sung dữ liệu hoặc chuẩn hóa ô trống giả ở cột '{header[c]}'"
                })

    # ---------------------------------------------------------
    # 2. CONSISTENCY (ĐỘ NHẤT QUÁN KIỂU DỮ LIỆU) - Trọng số 25%
    # ---------------------------------------------------------
    inconsistent_cells_count = 0
    non_empty_cells_count = total_cells - empty_cells_count

    for c in range(n_cols):
        col_vals = [r[c] for r in data_rows if c < len(r) and not is_blank(r[c])]
        if not col_vals:
            continue

        # Đếm số ô có thể đọc thành số
        num_count = 0
        for v in col_vals:
            sv = str(v).replace(',', '').replace('.', '').replace('-', '').strip()
            if sv.isdigit():
                num_count += 1

        ratio_num = num_count / len(col_vals)
        # Nếu đa số (>60%) là số nhưng có một số ô chữ -> không nhất quán
        if 0.6 <= ratio_num < 1.0:
            bad_cnt = len(col_vals) - num_count
            inconsistent_cells_count += bad_cnt
            deductions.append({
                "category": "Consistency",
                "column": header[c],
                "penalty": round((bad_cnt / max(1, non_empty_cells_count)) * 25.0, 1),
                "count": bad_cnt,
                "reason": f"Cột đa số là số nhưng có {bad_cnt} ô chứa ký tự chữ/sai kiểu",
                "fix": f"Kiểm tra và sửa các ô sai kiểu trong cột '{header[c]}'"
            })

    consistency_ratio = 1.0 - (inconsistent_cells_count / max(1, non_empty_cells_count))
    consistency_score = round(max(0.0, consistency_ratio * 100.0), 1)

    # ---------------------------------------------------------
    # 3. VALIDITY (ĐỘ HỢP LỆ ĐỊNH DẠNG NGHIỆP VỤ) - Trọng số 25%
    # ---------------------------------------------------------
    invalid_cells_count = 0
    checked_cells_count = 0

    for c, h_name in enumerate(header):
        h_lower = str(h_name).lower()
        is_email_col = 'email' in h_lower or 'thư điện tử' in h_lower
        is_phone_col = 'phone' in h_lower or 'sđt' in h_lower or 'điện thoại' in h_lower or 'tel' in h_lower

        if is_email_col:
            bad_email_cnt = 0
            for r in data_rows:
                if c < len(r) and not is_blank(r[c]):
                    checked_cells_count += 1
                    s = str(r[c]).strip().lower()
                    if not EMAIL_REGEX.match(s):
                        bad_email_cnt += 1
            if bad_email_cnt > 0:
                invalid_cells_count += bad_email_cnt
                deductions.append({
                    "category": "Validity",
                    "column": h_name,
                    "penalty": round((bad_email_cnt / max(1, n_rows)) * 15.0, 1),
                    "count": bad_email_cnt,
                    "reason": f"Có {bad_email_cnt} email sai định dạng (thiếu @, tên miền sai...)",
                    "fix": f"Dùng tính năng Chuẩn hóa Email để sửa định dạng cột '{h_name}'"
                })

        if is_phone_col:
            bad_phone_cnt = 0
            for r in data_rows:
                if c < len(r) and not is_blank(r[c]):
                    checked_cells_count += 1
                    digits = re.sub(r'\D', '', str(r[c]))
                    if not VN_PHONE_REGEX.match(digits):
                        bad_phone_cnt += 1
            if bad_phone_cnt > 0:
                invalid_cells_count += bad_phone_cnt
                deductions.append({
                    "category": "Validity",
                    "column": h_name,
                    "penalty": round((bad_phone_cnt / max(1, n_rows)) * 15.0, 1),
                    "count": bad_phone_cnt,
                    "reason": f"Có {bad_phone_cnt} số điện thoại không hợp lệ (sai độ dài hoặc đầu số)",
                    "fix": f"Dùng tính năng Chuẩn hóa Số điện thoại cho cột '{h_name}'"
                })

    validity_ratio = 1.0 - (invalid_cells_count / max(1, checked_cells_count)) if checked_cells_count > 0 else 1.0
    validity_score = round(max(0.0, validity_ratio * 100.0), 1)

    # ---------------------------------------------------------
    # 4. UNIQUENESS (ĐỘ DUY NHẤT) - Trọng số 20%
    # ---------------------------------------------------------
    cols_to_check = key_cols if key_cols is not None else list(range(n_cols))
    cols_to_check = [c for c in cols_to_check if 0 <= c < n_cols]
    if not cols_to_check:
        cols_to_check = list(range(n_cols))

    seen_keys = set()
    dup_rows_count = 0
    for r in data_rows:
        key = tuple(str(r[c]).strip().lower() if c < len(r) else "" for c in cols_to_check)
        if key in seen_keys:
            dup_rows_count += 1
        else:
            seen_keys.add(key)

    uniqueness_ratio = 1.0 - (dup_rows_count / n_rows) if n_rows > 0 else 1.0
    uniqueness_score = round(uniqueness_ratio * 100.0, 1)

    if dup_rows_count > 0:
        dup_penalty = round((dup_rows_count / n_rows) * 20.0, 1)
        deductions.append({
            "category": "Uniqueness",
            "column": ", ".join(header[c] for c in cols_to_check),
            "penalty": dup_penalty,
            "count": dup_rows_count,
            "reason": f"Có {dup_rows_count} dòng bị trùng lặp dữ liệu",
            "fix": "Sử dụng tính năng Lọc trùng lặp để loại bỏ các bản ghi thừa"
        })

    # ---------------------------------------------------------
    # TỔNG HỢP ĐIỂM SỐ
    # ---------------------------------------------------------
    overall_score = round(
        0.30 * completeness_score +
        0.25 * consistency_score +
        0.25 * validity_score +
        0.20 * uniqueness_score,
        1
    )
    overall_score = max(0.0, min(100.0, overall_score))

    if overall_score >= 85.0:
        status = "SAFE"
    elif overall_score >= 60.0:
        status = "REVIEW_REQUIRED"
    else:
        status = "UNSAFE"

    # Sắp xếp các điểm trừ lớn nhất lên đầu
    deductions.sort(key=lambda x: x["penalty"], reverse=True)

    return {
        "overall_score": overall_score,
        "status": status,
        "metrics": {
            "completeness": completeness_score,
            "consistency": consistency_score,
            "validity": validity_score,
            "uniqueness": uniqueness_score
        },
        "deductions": deductions,
        "stats": {
            "total_rows": n_rows,
            "total_cols": n_cols,
            "empty_cells": empty_cells_count,
            "inconsistent_cells": inconsistent_cells_count,
            "invalid_cells": invalid_cells_count,
            "duplicate_rows": dup_rows_count
        }
    }

def independent_quality_check(rows: List[List[Any]], reported_score: float) -> Tuple[bool, str]:
    """Kiểm tra đối chiếu độc lập điểm chất lượng theo Mục 0 nguyên tắc 10."""
    if not (0.0 <= reported_score <= 100.0):
        return False, f"Điểm số {reported_score} nằm ngoài khoảng [0, 100]"
    # Độc lập tính nhanh null ratio và duplicate ratio
    if len(rows) > 1:
        n_rows = len(rows) - 1
        n_cols = len(rows[0])
        total = n_rows * n_cols
        nulls = sum(1 for r in rows[1:] for c in range(n_cols) if is_blank(r[c] if c < len(r) else None))
        if nulls == total and reported_score > 70.0:
            return False, "Dữ liệu 100% rỗng nhưng điểm chất lượng quá cao"
    return True, "Kiểm tra đối chiếu độc lập thành công"
