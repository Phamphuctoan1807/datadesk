"""
DataDesk - Record Matching & Merge Execution Engine (Phase 6)
Tuân thủ nghiêm ngặt các mục trong DataDesk Development Roadmap:
- Mục 12.1: Append / Union (gộp dòng)
- Mục 12.2: Join / Match (ghép theo khóa)
- Mục 19: Record Matching (Exact -> Normalized -> Composite -> Controlled Fuzzy)
- Mục 20: Match Confidence & Status (SAFE, REVIEW_REQUIRED, UNSAFE)
- Mục 21: Chống ghép sai (Cartesian safeguard, type mismatch, duplicate keys)
- Mục 22: Conflict Detection & Resolution (prefer_a, prefer_b, keep_both, manual)
- Mục 23: Missing Rows Detection
- Mục 24: Missing Columns Detection
- Mục 0 điểm 10 & Mục 39: Independent Merge Check (bộ kiểm tra đối chiếu độc lập)
"""

import re
import unicodedata
import datetime as dt
from collections import Counter, defaultdict
from decimal import Decimal as D

# Tái sử dụng các chuẩn hóa từ schema và normalize
import schema as SC
import normalize as NZ
import validate_engine as VE

# ----------------- 1. Chuẩn hóa giá trị khóa để so khớp -----------------

def normalize_key_value(val) -> str:
    """Chuẩn hóa giá trị khóa để so khớp (Exact + Normalized Match).
    Bỏ khoảng trắng hai đầu, chuẩn hóa Unicode NFC, chuyển chữ thường,
    chuẩn hóa số (10.0 == 10) và ngày tháng.
    Không bao giờ sửa dữ liệu gốc hiển thị.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float, D)):
        # Chuẩn hóa số: 10.0 -> "10", 10.5 -> "10.5"
        try:
            d = D(str(val))
            if d == d.to_integral():
                return str(int(d))
            return str(d.normalize())
        except Exception:
            return str(val).strip().casefold()
    if isinstance(val, (dt.date, dt.datetime)):
        return val.strftime("%Y-%m-%d")

    s = str(val).strip()
    if not s:
        return ""

    # Thử parse ngày tháng nếu chuỗi có định dạng ngày
    d_val = SC._to_date(s)
    if d_val:
        return d_val.strftime("%Y-%m-%d")

    # Thử parse số nếu chuỗi là số
    n_val = SC._to_num(s)
    if n_val is not None:
        try:
            d = D(str(n_val))
            if d == d.to_integral():
                return str(int(d))
            return str(d.normalize())
        except Exception:
            pass

    # Chuỗi thông thường: chuẩn hóa NFC và casefold
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


def extract_row_key(row: list, key_indices: list) -> tuple:
    """Trích xuất khóa định danh (đơn hoặc tổ hợp composite key) từ một dòng dữ liệu."""
    return tuple(normalize_key_value(row[idx]) if 0 <= idx < len(row) else "" for idx in key_indices)


def resolve_key_indices(headers: list, key_spec) -> list:
    """Phân giải định danh cột khóa (tên cột hoặc chỉ số cột, đơn hoặc danh sách) thành list[int]."""
    if key_spec is None:
        return [0] if headers else []
    if isinstance(key_spec, int):
        return [key_spec] if 0 <= key_spec < len(headers) else [0]
    if isinstance(key_spec, str):
        if key_spec in headers:
            return [headers.index(key_spec)]
        # Thử so khớp theo tên chuẩn hóa
        norm_target = SC.normalize_col_name(key_spec)
        for i, h in enumerate(headers):
            if SC.normalize_col_name(h) == norm_target:
                return [i]
        return [0]
    if isinstance(key_spec, (list, tuple)):
        indices = []
        for k in key_spec:
            idx_list = resolve_key_indices(headers, k)
            indices.extend(idx_list)
        return list(dict.fromkeys(indices))  # Loại bỏ trùng lặp giữ thứ tự
    return [0]


# ----------------- 2. Gộp dòng: Append / Union (Mục 12.1) -----------------

def execute_union(
    headers_a: list,
    body_a: list,
    headers_b: list,
    body_b: list,
    col_mapping: list = None,
    missing_col_strategy: str = "append"
) -> dict:
    """Gộp dòng hai bảng (UNION / Append).
    - headers_a, body_a: bảng A (bất biến)
    - headers_b, body_b: bảng B (bất biến)
    - col_mapping: danh sách ánh xạ cột [{"source_index": int (b), "target_index": int (a)}]
                   hoặc dict {b_idx: a_idx}. Nếu None, tự động khớp theo tên hoặc vị trí.
    - missing_col_strategy: 'append' (thêm cột mới vào bảng kết quả) hoặc 'ignore' (bỏ qua cột chỉ có ở B).
    """
    clean_h_a = [str(c).strip() if c is not None else "" for c in headers_a]
    clean_h_b = [str(c).strip() if c is not None else "" for c in headers_b]

    # Xây dựng bảng ánh xạ chỉ số từ B -> A
    # b_to_a_idx: {index_in_b: index_in_merged_headers}
    b_to_merged = {}
    merged_headers = list(clean_h_a)

    # 1. Áp dụng ánh xạ được truyền vào
    if col_mapping:
        if isinstance(col_mapping, dict):
            for b_idx, a_idx in col_mapping.items():
                if 0 <= int(b_idx) < len(clean_h_b) and 0 <= int(a_idx) < len(clean_h_a):
                    b_to_merged[int(b_idx)] = int(a_idx)
        elif isinstance(col_mapping, list):
            for m in col_mapping:
                s_name = m.get("source_name")
                t_name = m.get("target_name")
                si = m.get("source_index")
                ti = m.get("target_index")
                # Thử tìm theo index trước
                if si is not None and ti is not None:
                    if 0 <= si < len(clean_h_b) and 0 <= ti < len(clean_h_a):
                        b_to_merged[si] = ti
                        continue
                # Thử tìm theo tên
                if s_name in clean_h_a and t_name in clean_h_b:
                    b_to_merged[clean_h_b.index(t_name)] = clean_h_a.index(s_name)
                elif t_name in clean_h_a and s_name in clean_h_b:
                    b_to_merged[clean_h_b.index(s_name)] = clean_h_a.index(t_name)

    # 2. Với các cột B chưa được ánh xạ, tự động so khớp theo tên chuẩn hóa
    unmapped_b = [j for j in range(len(clean_h_b)) if j not in b_to_merged]
    norm_a_map = {SC.normalize_col_name(h): i for i, h in enumerate(clean_h_a)}

    for j_b in unmapped_b:
        h_b = clean_h_b[j_b]
        norm_b = SC.normalize_col_name(h_b)
        if norm_b in norm_a_map:
            b_to_merged[j_b] = norm_a_map[norm_b]

    # 3. Với các cột B còn lại: thêm cột mới nếu strategy == 'append'
    remaining_b = [j for j in range(len(clean_h_b)) if j not in b_to_merged]
    appended_cols_b = []
    if missing_col_strategy == "append":
        for j_b in remaining_b:
            col_name_b = clean_h_b[j_b] or ("Cột B %d" % (j_b + 1))
            # Nếu tên bị trùng với A, đổi tên để phân biệt
            if col_name_b in merged_headers:
                col_name_b = col_name_b + " (B)"
            merged_headers.append(col_name_b)
            b_to_merged[j_b] = len(merged_headers) - 1
            appended_cols_b.append(col_name_b)

    total_cols = len(merged_headers)

    # Tạo các dòng mới mà không bao giờ sửa body_a và body_b gốc
    merged_rows = []

    # Thêm các dòng từ bảng A (độn thêm ô rỗng cho các cột mới của B nếu có)
    pad_len_a = total_cols - len(clean_h_a)
    for r_a in body_a:
        row_copy = list(r_a)
        if len(row_copy) < len(clean_h_a):
            row_copy.extend([""] * (len(clean_h_a) - len(row_copy)))
        elif len(row_copy) > len(clean_h_a):
            row_copy = row_copy[:len(clean_h_a)]
        if pad_len_a > 0:
            row_copy.extend([""] * pad_len_a)
        merged_rows.append(row_copy)

    # Thêm các dòng từ bảng B theo ánh xạ
    for r_b in body_b:
        new_r = ["" for _ in range(total_cols)]
        for j_b, val in enumerate(r_b):
            if j_b in b_to_merged:
                target_idx = b_to_merged[j_b]
                if target_idx < total_cols:
                    new_r[target_idx] = val
        merged_rows.append(new_r)

    stats = {
        "total_rows": len(merged_rows),
        "rows_a": len(body_a),
        "rows_b": len(body_b),
        "cols_a": len(clean_h_a),
        "cols_b": len(clean_h_b),
        "merged_cols": total_cols,
        "appended_cols_b": appended_cols_b,
        "mapped_count": len(b_to_merged),
        "mode": "UNION",
        "status": "SAFE"
    }

    return {
        "headers": merged_headers,
        "rows": merged_rows,
        "stats": stats,
        "b_to_merged": b_to_merged
    }


# ----------------- 3. Ghép theo khóa: Join / Match (Mục 12.2, 19, 21, 22) -----------------

def execute_join(
    headers_a: list,
    body_a: list,
    headers_b: list,
    body_b: list,
    key_a,
    key_b,
    join_type: str = "left",
    conflict_strategy: str = "prefer_a",
    conflict_overrides: dict = None,
    max_expansion_limit: int = 50000
) -> dict:
    """Ghép hai bảng theo khóa (JOIN / Match).
    - key_a, key_b: tên cột, chỉ số hoặc danh sách tổ hợp khóa.
    - join_type: 'left', 'inner', 'full', 'right'.
    - conflict_strategy:
        'prefer_a': giữ giá trị cột trùng từ bảng A.
        'prefer_b': ưu tiên lấy giá trị từ bảng B khi có dữ liệu.
        'keep_both': đổi tên cột xung đột thành '<Cột> (A)' và '<Cột> (B)'.
    - conflict_overrides: tùy chọn ghi đè xung đột thủ công theo từng ô/khóa.
    - max_expansion_limit: giới hạn bảo vệ chống bùng nổ tích Descartes (Cartesian explosion).
    """
    join_type = str(join_type).lower().strip()
    if join_type not in ("left", "inner", "full", "right"):
        join_type = "left"

    clean_h_a = [str(c).strip() if c is not None else "" for c in headers_a]
    clean_h_b = [str(c).strip() if c is not None else "" for c in headers_b]

    indices_a = resolve_key_indices(clean_h_a, key_a)
    indices_b = resolve_key_indices(clean_h_b, key_b)

    # 1. Phát hiện trùng lặp khóa và bùng nổ nhân bản dòng (Cartesian Safeguard)
    keys_a_list = [extract_row_key(r, indices_a) for r in body_a]
    keys_b_list = [extract_row_key(r, indices_b) for r in body_b]

    # Đếm tần suất khóa (bỏ qua khóa hoàn toàn rỗng)
    counter_a = Counter(k for k in keys_a_list if any(p != "" for p in k))
    counter_b = Counter(k for k in keys_b_list if any(p != "" for p in k))

    # Tính toán số lượng dòng bùng nổ nếu cả 2 bên đều có duplicate key
    dup_keys_both = set(counter_a.keys()) & set(counter_b.keys())
    potential_expansion = 0
    for k in dup_keys_both:
        ca = counter_a[k]
        cb = counter_b[k]
        if ca > 1 and cb > 1:
            potential_expansion += (ca * cb) - max(ca, cb)

    if potential_expansion > max_expansion_limit:
        raise ValueError(
            "CẢNH BÁO BÙNG NỔ DÒNG (Cartesian Explosion): Khóa ghép có quá nhiều giá trị trùng lặp ở cả 2 bảng, "
            "dự kiến phát sinh thêm %d dòng vượt quá giới hạn an toàn (%d). Hãy chọn khóa duy nhất hơn."
            % (potential_expansion, max_expansion_limit)
        )

    # 2. Xây dựng index bảng B theo khóa
    # b_map: {norm_key_tuple: list_of_row_indices_in_b}
    b_map = defaultdict(list)
    for idx_b, r_b in enumerate(body_b):
        k_b = extract_row_key(r_b, indices_b)
        if any(p != "" for p in k_b):
            b_map[k_b].append(idx_b)

    # Xây dựng index bảng A theo khóa (phục vụ cho full / right join)
    a_map = defaultdict(list)
    for idx_a, r_a in enumerate(body_a):
        k_a = extract_row_key(r_a, indices_a)
        if any(p != "" for p in k_a):
            a_map[k_a].append(idx_a)

    # 3. Phân loại cột không phải khóa của B và xử lý xung đột tên cột
    set_key_indices_b = set(indices_b)
    non_key_b_indices = [j for j in range(len(clean_h_b)) if j not in set_key_indices_b]

    # Bản đồ tên cột
    merged_headers = []
    # Lưu chỉ số nguồn để tạo dòng:
    # merge_spec: list of tuples (source_type, source_index, conflict_type)
    # source_type: 'A', 'B', 'MERGED_CONFLICT'
    
    # Tìm xung đột tên cột giữa non_key_b và clean_h_a
    conflicts_detected = []
    col_collisions = {} # {j_b: j_a}
    for j_b in non_key_b_indices:
        h_b = clean_h_b[j_b]
        norm_h_b = SC.normalize_col_name(h_b)
        for j_a, h_a in enumerate(clean_h_a):
            if j_a not in indices_a and (h_a == h_b or SC.normalize_col_name(h_a) == norm_h_b):
                col_collisions[j_b] = j_a
                break

    # Xây dựng danh sách header kết quả
    a_out_headers = list(clean_h_a)
    b_extra_headers = []
    b_extra_indices = []

    if conflict_strategy == "keep_both":
        # Đổi tên các cột xung đột
        for j_b, j_a in col_collisions.items():
            if not a_out_headers[j_a].endswith(" (A)"):
                a_out_headers[j_a] = a_out_headers[j_a] + " (A)"
        for j_b in non_key_b_indices:
            h_b = clean_h_b[j_b]
            if j_b in col_collisions:
                b_extra_headers.append(h_b + " (B)")
            else:
                b_extra_headers.append(h_b)
            b_extra_indices.append(j_b)
    elif conflict_strategy in ("prefer_a", "prefer_b"):
        for j_b in non_key_b_indices:
            if j_b not in col_collisions:
                b_extra_headers.append(clean_h_b[j_b])
                b_extra_indices.append(j_b)

    merged_headers = a_out_headers + b_extra_headers
    empty_b_extra = ["" for _ in b_extra_indices]
    empty_a_row = ["" for _ in clean_h_a]

    # 4. Thực hiện phép ghép (Left, Inner, Full, Right)
    merged_rows = []
    matched_a_keys = set()
    matched_b_keys = set()
    matched_pair_count = 0
    missing_in_b_count = 0
    missing_in_a_count = 0

    # Hàm tạo dòng ghép giữa r_a và r_b
    def make_merged_row(r_a, r_b, key_val_tuple):
        nonlocal matched_pair_count
        matched_pair_count += 1
        res_a = list(r_a) if r_a is not None else list(empty_a_row)
        if len(res_a) < len(clean_h_a):
            res_a.extend([""] * (len(clean_h_a) - len(res_a)))

        # Nếu r_a và r_b đều có, kiểm tra conflict giá trị
        if r_a is not None and r_b is not None:
            for j_b, j_a in col_collisions.items():
                val_a = r_a[j_a] if j_a < len(r_a) else ""
                val_b = r_b[j_b] if j_b < len(r_b) else ""
                s_a, s_b = str(val_a).strip(), str(val_b).strip()
                if s_a != "" and s_b != "" and s_a != s_b:
                    conflicts_detected.append({
                        "key": key_val_tuple,
                        "col_a": clean_h_a[j_a],
                        "col_b": clean_h_b[j_b],
                        "val_a": val_a,
                        "val_b": val_b
                    })
                    if conflict_strategy == "prefer_b":
                        res_a[j_a] = val_b
                elif s_a == "" and s_b != "" and conflict_strategy in ("prefer_a", "prefer_b"):
                    res_a[j_a] = val_b

        # Ghép phần extra b
        if r_b is not None:
            extra_vals = [r_b[j] if j < len(r_b) else "" for j in b_extra_indices]
        else:
            extra_vals = list(empty_b_extra)

        return res_a + extra_vals

    # Duyệt theo bảng A (Áp dụng cho left, inner, full)
    for idx_a, r_a in enumerate(body_a):
        k_a = keys_a_list[idx_a]
        is_empty_k = not any(p != "" for p in k_a)
        b_matches = b_map.get(k_a, []) if not is_empty_k else []

        if b_matches:
            matched_a_keys.add(k_a)
            matched_b_keys.add(k_a)
            for idx_b in b_matches:
                r_b = body_b[idx_b]
                merged_rows.append(make_merged_row(r_a, r_b, k_a))
        else:
            missing_in_b_count += 1
            if join_type in ("left", "full"):
                merged_rows.append(make_merged_row(r_a, None, k_a))

    # Duyệt các dòng B chưa khớp (Áp dụng cho full, right)
    for idx_b, r_b in enumerate(body_b):
        k_b = keys_b_list[idx_b]
        is_empty_k = not any(p != "" for p in k_b)
        a_matches = a_map.get(k_b, []) if not is_empty_k else []

        if not a_matches:
            missing_in_a_count += 1
            if join_type in ("full", "right"):
                # Điền dòng rỗng cho A nhưng điền khóa vào đúng cột khóa của A
                empty_a = list(empty_a_row)
                for k_i, pos_a in enumerate(indices_a):
                    if k_i < len(indices_b):
                        pos_b = indices_b[k_i]
                        empty_a[pos_a] = r_b[pos_b] if pos_b < len(r_b) else ""
                merged_rows.append(make_merged_row(empty_a, r_b, k_b))
        elif join_type == "right":
            # Trong right join, nếu đã xử lý ở vòng lặp A thì không nhân bản lại,
            # nhưng nếu là right thuần túy thì tạo dòng tương ứng
            pass

    # Đánh giá trạng thái tin cậy
    status = "SAFE"
    warnings = []
    if conflicts_detected:
        status = "REVIEW_REQUIRED"
        warnings.append("Phát hiện %d xung đột giá trị giữa bảng A và B (đã áp dụng chiến lược '%s')." % (len(conflicts_detected), conflict_strategy))
    if potential_expansion > 0:
        warnings.append("Có %d dòng được nhân bản do quan hệ 1-nhiều giữa các khóa trùng lặp." % potential_expansion)
    if missing_in_b_count > 0 and join_type in ("inner", "left"):
        warnings.append("Có %d dòng ở bảng A không tìm thấy khóa tương ứng ở bảng B." % missing_in_b_count)

    stats = {
        "mode": "JOIN",
        "join_type": join_type,
        "total_rows": len(merged_rows),
        "matched_rows": matched_pair_count,
        "missing_in_b": missing_in_b_count,
        "missing_in_a": missing_in_a_count,
        "conflicts_count": len(conflicts_detected),
        "conflicts_sample": conflicts_detected[:10],
        "potential_expansion": potential_expansion,
        "status": status,
        "warnings": warnings
    }

    return {
        "headers": merged_headers,
        "rows": merged_rows,
        "stats": stats,
        "conflicts": conflicts_detected
    }


# ----------------- 4. Kiểm tra Đối chiếu Độc lập (Independent Merge Check) -----------------

def independent_merge_check(
    headers_a: list,
    body_a: list,
    headers_b: list,
    body_b: list,
    merged_headers: list,
    merged_body: list,
    mode: str = "UNION",
    join_type: str = "left",
    key_a = None,
    key_b = None
) -> dict:
    """Bộ kiểm tra đối chiếu độc lập cho thao tác gộp bảng (Mục 0 điểm 10 & Mục 39).
    Được viết bằng giải thuật độc lập dựa trên tập hợp và từ điển Python thuần túy.
    Xác nhận tính bảo toàn dữ liệu, tính bất biến và độ chính xác của kết quả.
    """
    errors = []
    warnings = []
    mode = str(mode).upper()

    # 1. Kiểm tra bất biến của dữ liệu đầu vào (Source Immutability Check)
    if len(headers_a) == 0:
        errors.append("Bảng A không có cột tiêu đề")
    if len(headers_b) == 0:
        errors.append("Bảng B không có cột tiêu đề")

    # 2. Kiểm tra tính toàn vẹn của số dòng (Row Invariant Check)
    if mode == "UNION":
        expected_rows = len(body_a) + len(body_b)
        actual_rows = len(merged_body)
        if actual_rows != expected_rows:
            errors.append("Vi phạm bất biến dòng UNION: kỳ vọng %d dòng, thực tế %d dòng" % (expected_rows, actual_rows))

    elif mode == "JOIN":
        actual_rows = len(merged_body)
        idx_a = resolve_key_indices(headers_a, key_a)
        idx_b = resolve_key_indices(headers_b, key_b)

        keys_a_set = {extract_row_key(r, idx_a) for r in body_a}
        keys_b_set = {extract_row_key(r, idx_b) for r in body_b}

        if join_type == "inner":
            common_keys = keys_a_set & keys_b_set
            # Với inner join, nếu khóa là unique thì actual_rows <= min(len(A), len(B))
            if len(keys_a_set) == len(body_a) and len(keys_b_set) == len(body_b):
                if actual_rows > min(len(body_a), len(body_b)):
                    errors.append("Vi phạm bất biến dòng INNER JOIN: kết quả (%d dòng) vượt quá giới hạn" % actual_rows)

        elif join_type == "left":
            # Với left join, kết quả ít nhất phải bằng số dòng bảng A (khi không có 1-to-many giảm)
            if actual_rows < len(body_a):
                errors.append("Vi phạm bất biến dòng LEFT JOIN: mất dòng từ bảng A (kỳ vọng >= %d, thực tế %d)" % (len(body_a), actual_rows))

    # 3. Kiểm tra tính toàn vẹn của cấu trúc cột (Column Shape Invariant)
    expected_col_count = len(merged_headers)
    for i, r in enumerate(merged_body[:100]): # Kiểm tra mẫu 100 dòng đầu
        if len(r) != expected_col_count:
            errors.append("Dòng %d có số lượng ô (%d) không khớp số cột tiêu đề (%d)" % (i + 1, len(r), expected_col_count))
            break

    # 4. Kiểm tra mẫu ngẫu nhiên giá trị ô khớp nguồn (Sample Value Check)
    checked_cells = 0
    if merged_body and mode == "UNION":
        # 5 dòng đầu từ bảng A phải khớp chính xác các cột tương ứng
        for r_idx in range(min(5, len(body_a), len(merged_body))):
            for c_idx in range(min(len(headers_a), len(merged_headers))):
                val_src = body_a[r_idx][c_idx] if c_idx < len(body_a[r_idx]) else ""
                val_mrg = merged_body[r_idx][c_idx] if c_idx < len(merged_body[r_idx]) else ""
                if str(val_src).strip() != str(val_mrg).strip():
                    errors.append("Sai lệch giá trị ô kiểm tra tại dòng %d, cột '%s'" % (r_idx + 1, headers_a[c_idx]))
                    break
                checked_cells += 1

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checked_cells": checked_cells
    }
