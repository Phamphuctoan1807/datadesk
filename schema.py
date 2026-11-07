"""Module nhận diện Schema, chuẩn hóa tên cột, nhận diện ngữ nghĩa, khóa và so khớp cột thông minh (Giai đoạn 5 của lộ trình DataDesk - Mục 11 đến 18).

Nguyên tắc bắt buộc:
1. Không sửa dataset gốc trực tiếp. Tên cột gốc luôn được giữ nguyên; chuẩn hóa tên chỉ dùng cho đối chiếu so khớp.
2. Không tự khớp khi độ tin cậy thấp. Điểm < 90% phải chuyển thành REVIEW_REQUIRED hoặc UNSAFE.
3. Không tự chọn khóa khi có nhiều ứng viên ngang nhau (báo AMBIGUOUS_KEYS).
4. Kiểm tra độc lập: hàm independent_match_check đối chiếu tính hợp lệ của mapping độc lập với bộ so khớp chính.
"""

import re
import unicodedata
import datetime as dt
from decimal import Decimal as D

# Tái dùng chuẩn hóa chuỗi và biểu thức chính quy từ normalize
import formula as F
import normalize as NZ

# ---------- Tiện ích kiểm tra số và ngày ----------
def _to_num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float, D)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = re.sub(r"\s|₫|đ|\$|€|%|VND|VNĐ", "", v, flags=re.I)
    if not re.fullmatch(r"[+-]?[0-9.,]+", s) or not re.search(r"[0-9]", s):
        return None
    hc, hd = "," in s, "." in s
    if hc and hd:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif hc:
        s = s.replace(",", "") if re.fullmatch(r"[+-]?[0-9]{1,3}(,[0-9]{3})+", s) else ("x" if s.count(",") > 1 else s.replace(",", "."))
    elif hd:
        if re.fullmatch(r"[+-]?[0-9]{1,3}(\.[0-9]{3})+", s):
            s = s.replace(".", "")
        elif s.count(".") > 1:
            s = "x"
    try:
        return float(s)
    except ValueError:
        return None

def _to_date(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        s = v.strip()
        m1 = NZ.RX_DMY.match(s)
        if m1:
            d, m, y = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
            try:
                return dt.datetime(y, m, d)
            except ValueError:
                return None
        m2 = NZ.RX_YMD.match(s)
        if m2:
            y, m, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
            try:
                return dt.datetime(y, m, d)
            except ValueError:
                return None
    return None


# ----------------- 1. Chuẩn hóa tên cột để so khớp (Mục 14) -----------------

def _strip_accents(s: str) -> str:
    """Bỏ dấu tiếng Việt, chuyển đ/Đ thành d/D (dùng cho so sánh đối chiếu)."""
    s = str(s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def normalize_col_name(name: str) -> str:
    """Chuẩn hóa tên cột thành dạng chuẩn so sánh (canonical comparison form).
    Ví dụ: 'Mã KH', 'ma_kh', 'MA KH', 'mã-kh', 'MaKH' -> 'ma kh'.
    Không bao giờ thay đổi tên cột gốc của người dùng.
    """
    if name is None:
        return ""
    s = str(name).strip()
    # Tách CamelCase: 'MaKH' -> 'Ma KH', 'customerName' -> 'customer Name'
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    # Bỏ dấu tiếng Việt
    s = _strip_accents(s)
    # Đổi các ký tự ngăn cách (gạch dưới, gạch ngang, chấm, phẩy, chéo) thành dấu cách
    s = re.sub(r"[\-_\./\\,;:#()\[\]]+", " ", s)
    # Chuyển về chữ thường và gộp khoảng trắng thừa
    s = " ".join(s.lower().split())
    return s

# Từ điển nhóm đồng nghĩa phổ biến (Việt - Anh và chữ viết tắt)
SYNONYM_GROUPS = [
    {"ma kh", "customer id", "cust id", "makh", "ma khach hang", "client id", "customer code", "ma khach", "id khach hang"},
    {"ten", "ho ten", "name", "customer name", "ten khach hang", "fullname", "full name", "client name", "ho va ten"},
    {"sdt", "so dien thoai", "phone", "tel", "mobile", "dien thoai", "telephone", "phone number", "so dt"},
    {"email", "thu dien tu", "mail", "email address", "dia chi email"},
    {"dia chi", "address", "noi o", "street address", "location"},
    {"ngay", "date", "ngay tao", "ngay mua", "created at", "purchase date", "thoi gian", "timestamp"},
    {"gia", "don gia", "price", "unit price", "thanh tien", "amount", "cost", "tong tien", "total", "tien"},
    {"so luong", "sl", "quantity", "qty", "count"},
    {"ma sp", "product id", "sku", "item code", "ma hang", "ma san pham", "masp", "prod id"},
    {"ten sp", "ten san pham", "product name", "item name", "tensp", "ten hang"},
    {"trang thai", "status", "tinh trang", "state"},
    {"ghi chu", "note", "description", "mo ta", "remark", "notes", "comments"},
    {"chi nhanh", "branch", "branch id", "ma chi nhanh", "store", "ma kho", "kho"},
    {"loai", "category", "type", "phan loai", "nhom", "group"},
]

def _are_synonyms(norm_a: str, norm_b: str) -> bool:
    if not norm_a or not norm_b:
        return False
    for group in SYNONYM_GROUPS:
        if norm_a in group and norm_b in group:
            return True
    return False

# ----------------- 2. Độ tương đồng chuỗi tên cột (Name Similarity) -----------------

def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insert = prev[j + 1] + 1
            delete = curr[j] + 1
            sub = prev[j] + (0 if c1 == c2 else 1)
            curr.append(min(insert, delete, sub))
        prev = curr
    return prev[-1]

def name_similarity(name_a: str, name_b: str) -> float:
    """Tính điểm tương đồng giữa hai tên cột (0.0 -> 1.0)."""
    norm_a = normalize_col_name(name_a)
    norm_b = normalize_col_name(name_b)

    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0

    # Khớp chính xác dạng chuẩn
    if norm_a == norm_b:
        return 1.0

    # Khớp nhóm từ đồng nghĩa
    if _are_synonyms(norm_a, norm_b):
        return 0.95

    # Phân tích theo tập từ (Token set Jaccard)
    toks_a = set(norm_a.split())
    toks_b = set(norm_b.split())
    if toks_a == toks_b:
        return 0.98

    intersection = toks_a & toks_b
    union = toks_a | toks_b
    jaccard = len(intersection) / len(union) if union else 0.0

    # Một tên bao trọn tên kia (ví dụ 'ma kh' nằm trong 'ma khach hang')
    if norm_a in norm_b or norm_b in norm_a:
        sub_score = 0.85 * (min(len(norm_a), len(norm_b)) / max(len(norm_a), len(norm_b)))
    else:
        sub_score = 0.0

    # Levenshtein distance
    max_l = max(len(norm_a), len(norm_b))
    dist = _levenshtein_distance(norm_a, norm_b)
    lev_score = max(0.0, 1.0 - (dist / max_l))

    # Tổng hợp điểm tên
    return max(jaccard, sub_score, lev_score)


# ----------------- 3. Nhận diện ngữ nghĩa (Mục 16) -----------------

SEMANTIC_TYPES = (
    "customer_id",
    "product_id",
    "email",
    "phone",
    "address",
    "name",
    "date",
    "price",
    "quantity",
    "currency",
    "percentage",
    "status",
    "description",
)

VN_SURNAMES = {
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "vu", "vo", "dang",
    "bui", "do", "ho", "ngo", "duong", "ly", "dinh", "doan", "lam", "trinh", "mai"
}

ADDRESS_KEYWORDS = {
    "duong", "pho", "quan", "huyen", "tinh", "thanh pho", "tp", "phuong", "xa",
    "street", "st", "ward", "district", "city", "province", "ngo", "ngach", "ap", "thon"
}

def detect_semantic(col_name: str, values: list, data_type: str) -> dict:
    """Nhận diện loại ngữ nghĩa của cột và độ tin cậy (Mục 16).
    Trả về: {"type": <str>, "confidence": <float>, "reasons": [<str>]}
    """
    norm_nm = normalize_col_name(col_name)
    toks = set(norm_nm.split())
    nb = [v for v in values if v is not None and (not isinstance(v, str) or v.strip())]
    n_total = len(values)
    n_nb = len(nb)

    if n_nb == 0:
        return {"type": "unknown", "confidence": 0.0, "reasons": ["cột hoàn toàn trống"]}

    reasons = []

    # 1. Email
    email_cnt = sum(1 for v in nb if isinstance(v, str) and NZ.EMAIL.search(v.strip()))
    email_ratio = email_cnt / n_nb
    if email_ratio >= 0.6:
        return {"type": "email", "confidence": min(1.0, email_ratio + 0.1), "reasons": ["%d%% ô là định dạng email" % int(email_ratio * 100)]}
    if "email" in toks or "mail" in toks:
        if email_ratio >= 0.3:
            return {"type": "email", "confidence": 0.90, "reasons": ["tên cột chứa email và có dữ liệu email"]}

    # 2. Số điện thoại (Phone)
    phone_cnt = sum(1 for v in nb if isinstance(v, str) and NZ.PHONE_OK.fullmatch(re.sub(r"[\s.\-()]", "", v.strip())) or (isinstance(v, (int, float)) and 100000000 <= v <= 9999999999))
    phone_ratio = phone_cnt / n_nb
    if phone_ratio >= 0.6:
        return {"type": "phone", "confidence": min(1.0, phone_ratio + 0.1), "reasons": ["%d%% ô là số điện thoại" % int(phone_ratio * 100)]}
    if any(k in norm_nm for k in ("sdt", "dien thoai", "phone", "tel", "mobile")):
        if phone_ratio >= 0.2:
            return {"type": "phone", "confidence": 0.88, "reasons": ["tên cột là số điện thoại"]}

    # 3. Phần trăm (Percentage)
    pct_cnt = sum(1 for v in nb if isinstance(v, str) and "%" in v)
    pct_ratio = pct_cnt / n_nb
    if pct_ratio >= 0.5:
        return {"type": "percentage", "confidence": 0.95, "reasons": ["giá trị chứa ký hiệu %"]}
    if any(k in norm_nm for k in ("%", "phan tram", "ti le", "ty le", "percentage", "rate")):
        if data_type == "number":
            return {"type": "percentage", "confidence": 0.85, "reasons": ["tên cột chỉ tỷ lệ/phần trăm"]}

    # 4. Tiền tệ / Giá (Price / Currency)
    curr_cnt = sum(1 for v in nb if isinstance(v, str) and any(c in v.lower() for c in ("₫", "vnd", "$", "usd", "dong", "đồng")))
    if curr_cnt / n_nb >= 0.3:
        return {"type": "price", "confidence": 0.92, "reasons": ["chứa ký hiệu tiền tệ"]}
    if any(k in norm_nm for k in ("gia", "don gia", "thanh tien", "price", "amount", "cost", "tong tien", "doanh thu")):
        if data_type in ("number", "text"):
            return {"type": "price", "confidence": 0.88, "reasons": ["tên cột chỉ giá/tiền"]}

    # 5. Ngày tháng (Date)
    if data_type == "date":
        return {"type": "date", "confidence": 0.98, "reasons": ["kiểu dữ liệu là ngày tháng"]}
    date_cnt = sum(1 for v in nb if isinstance(v, str) and (NZ.RX_DMY.search(v) or NZ.RX_YMD.search(v) or NZ.RX_VN.search(v)))
    if date_cnt / n_nb >= 0.5:
        return {"type": "date", "confidence": 0.90, "reasons": ["giá trị có mẫu ngày tháng"]}

    # 6. Số lượng (Quantity)
    if any(k in toks for k in ("sl", "quantity", "qty")) or "so luong" in norm_nm:
        if data_type == "number":
            return {"type": "quantity", "confidence": 0.90, "reasons": ["tên cột là số lượng"]}

    # 7. Customer ID (Mã khách hàng)
    uniq_ratio = len(set(str(v) for v in nb)) / n_nb
    if any(k in norm_nm for k in ("ma kh", "makh", "customer id", "cust id", "ma khach", "client id")):
        return {"type": "customer_id", "confidence": 0.95 if uniq_ratio >= 0.7 else 0.80, "reasons": ["tên cột là mã khách hàng"]}

    # 8. Product ID (Mã sản phẩm / SKU)
    if any(k in norm_nm for k in ("ma sp", "masp", "product id", "sku", "item code", "ma hang", "barcode")):
        return {"type": "product_id", "confidence": 0.95 if uniq_ratio >= 0.7 else 0.80, "reasons": ["tên cột là mã sản phẩm/sku"]}

    # 9. Họ tên người (Name)
    if any(k in norm_nm for k in ("ho ten", "ten", "name", "khach hang", "customer", "nhan vien", "ho va ten")):
        # Kiểm tra mẫu họ tiếng Việt hoặc chữ hoa đầu từ
        name_sample_cnt = 0
        for v in nb[:100]:
            if isinstance(v, str):
                w = _strip_accents(v).lower().split()
                if w and (w[0] in VN_SURNAMES or len(w) in (2, 3, 4)):
                    name_sample_cnt += 1
        conf = 0.90 if name_sample_cnt >= 5 else 0.75
        return {"type": "name", "confidence": conf, "reasons": ["tên cột chỉ họ tên người"]}

    # 10. Địa chỉ (Address)
    if any(k in norm_nm for k in ("dia chi", "address", "noi o", "que quan")):
        return {"type": "address", "confidence": 0.90, "reasons": ["tên cột chỉ địa chỉ"]}
    addr_cnt = 0
    for v in nb[:50]:
        if isinstance(v, str):
            tw = set(_strip_accents(v).lower().split())
            if tw & ADDRESS_KEYWORDS:
                addr_cnt += 1
    if addr_cnt >= 5:
        return {"type": "address", "confidence": 0.75, "reasons": ["nội dung có từ khóa địa chỉ"]}

    # 11. Trạng thái (Status)
    if any(k in norm_nm for k in ("trang thai", "status", "tinh trang", "state")):
        return {"type": "status", "confidence": 0.90, "reasons": ["tên cột chỉ trạng thái"]}
    if len(set(str(v) for v in nb)) <= 8 and n_nb >= 20:
        if data_type == "text":
            return {"type": "status", "confidence": 0.70, "reasons": ["số giá trị phân loại nhỏ (<= 8)"]}

    # 12. Mô tả / Ghi chú (Description)
    if any(k in norm_nm for k in ("ghi chu", "note", "mo ta", "description", "remark", "notes")):
        return {"type": "description", "confidence": 0.88, "reasons": ["tên cột chỉ ghi chú/mô tả"]}
    avg_len = sum(len(str(v)) for v in nb) / n_nb if n_nb else 0
    if avg_len >= 45 and data_type == "text":
        return {"type": "description", "confidence": 0.75, "reasons": ["độ dài văn bản trung bình cao (> 45 ký tự)"]}

    # Không nhận diện được rõ ràng
    return {"type": "text" if data_type == "text" else data_type, "confidence": 0.50, "reasons": ["phân loại theo kiểu dữ liệu cơ bản"]}


# ----------------- 4. Nhận diện Lược đồ dữ liệu (DatasetSchema - Mục 13) -----------------

def detect_column_schema(col_idx: int, col_name: str, values: list, numfmt: str = "auto") -> dict:
    """Trích xuất lược đồ chi tiết cho một cột (Mục 13)."""
    n_total = len(values)
    non_empty = [v for v in values if v is not None and (not isinstance(v, str) or v.strip())]
    n_nb = len(non_empty)

    null_ratio = (n_total - n_nb) / n_total if n_total > 0 else 0.0

    # Lấy tập mẫu không trùng
    distinct_vals = []
    seen = set()
    for v in non_empty:
        sv = str(v)
        if sv not in seen:
            seen.add(sv)
            distinct_vals.append(v)
            if len(distinct_vals) >= 10:
                break

    distinct_count = len(set(str(v) for v in non_empty))
    unique_ratio = distinct_count / n_nb if n_nb > 0 else 0.0

    # Xác định kiểu dữ liệu cơ bản
    types_count = {"text": 0, "number": 0, "date": 0, "boolean": 0}
    format_dist = {"date_formats": {}, "number_formats": {}}

    for v in non_empty[:500]:
        if isinstance(v, bool):
            types_count["boolean"] += 1
        elif isinstance(v, (int, float, D)):
            types_count["number"] += 1
        elif isinstance(v, (dt.datetime, dt.date)):
            types_count["date"] += 1
        elif isinstance(v, str):
            s = v.strip()
            # Kiểm tra date
            if NZ.RX_DMY.search(s) or NZ.RX_YMD.search(s) or NZ.RX_VN.search(s):
                types_count["date"] += 1
                fmt_key = "dmy" if NZ.RX_DMY.search(s) else ("ymd" if NZ.RX_YMD.search(s) else "vn_text")
                format_dist["date_formats"][fmt_key] = format_dist["date_formats"].get(fmt_key, 0) + 1
            elif _to_num(s) is not None:
                types_count["number"] += 1
                fmt_key = "vi" if ("," in s and "." not in s) else ("en" if ("." in s and "," not in s) else "plain")
                format_dist["number_formats"][fmt_key] = format_dist["number_formats"].get(fmt_key, 0) + 1
            else:
                types_count["text"] += 1

    sample_size = min(n_nb, 500)
    if sample_size == 0:
        base_type = "empty"
    else:
        # Ngưỡng chọn kiểu cơ bản (>= 75% theo quy ước hệ thống)
        if types_count["number"] / sample_size >= 0.75:
            base_type = "number"
        elif types_count["date"] / sample_size >= 0.75:
            base_type = "date"
        elif types_count["boolean"] / sample_size >= 0.75:
            base_type = "boolean"
        else:
            base_type = "text"

    norm_name = normalize_col_name(col_name)
    semantic = detect_semantic(col_name, values, base_type)

    return {
        "index": col_idx,
        "column_name": col_name,
        "normalized_name": norm_name,
        "data_type": base_type,
        "sample_values": distinct_vals[:6],
        "unique_ratio": round(unique_ratio, 4),
        "null_ratio": round(null_ratio, 4),
        "distinct_count": distinct_count,
        "non_empty_count": n_nb,
        "total_rows": n_total,
        "format_distribution": format_dist,
        "semantic_hint": semantic,
    }


def detect_schema(table_name: str, headers: list, rows: list, numfmt: str = "auto") -> dict:
    """Tạo DatasetSchema hoàn chỉnh cho một bảng dữ liệu (Mục 13, 17, 18)."""
    columns = []
    col_values_list = []

    for idx, h in enumerate(headers):
        vals = [r[idx] if idx < len(r) else None for r in rows]
        col_values_list.append(vals)
        col_schema = detect_column_schema(idx, str(h), vals, numfmt)
        columns.append(col_schema)

    schema = {
        "name": table_name,
        "total_rows": len(rows),
        "total_columns": len(headers),
        "columns": columns,
        "key_candidates": [],
        "composite_key_candidates": [],
    }

    # Phát hiện khóa đơn (Mục 17)
    key_candidates = _detect_single_keys(columns)
    schema["key_candidates"] = key_candidates

    # Phát hiện khóa kép (Mục 18)
    composite_keys = _detect_composite_keys(columns, col_values_list, rows)
    schema["composite_key_candidates"] = composite_keys

    return schema


# ----------------- 5. Nhận diện Khóa & Khóa kép (Mục 17 & 18) -----------------

def _detect_single_keys(columns: list) -> list:
    """Nhận diện các cột có khả năng làm khóa chính (Mục 17).
    Quy tắc: Không tự chọn khi có nhiều ứng viên ngang nhau.
    """
    candidates = []
    for c in columns:
        if c["non_empty_count"] == 0:
            continue

        uniq = c["unique_ratio"]
        null_r = c["null_ratio"]
        sem = c["semantic_hint"]["type"]

        # Điều kiện tối thiểu: tỷ lệ duy nhất >= 90% và tỷ lệ trống <= 5%
        if uniq >= 0.90 and null_r <= 0.05:
            # Điểm phù hợp làm khóa:
            # - Tỷ lệ duy nhất: 40%
            # - Độ đầy đủ (1 - null): 30%
            # - Ngữ nghĩa (ID/code/phone/email): 20%
            # - Kiểu dữ liệu phù hợp (chuỗi ngắn, số nguyên): 10%
            sem_boost = 1.0 if sem in ("customer_id", "product_id") else (0.8 if sem in ("email", "phone") else 0.4)
            type_score = 1.0 if c["data_type"] in ("text", "number") else 0.2

            score = round(0.40 * uniq + 0.30 * (1.0 - null_r) + 0.20 * sem_boost + 0.10 * type_score, 4)

            candidates.append({
                "column_index": c["index"],
                "column_name": c["column_name"],
                "score": score,
                "unique_ratio": uniq,
                "null_ratio": null_r,
                "semantic_type": sem,
                "is_perfect_key": (uniq == 1.0 and null_r == 0.0),
            })

    # Sắp xếp theo điểm giảm dần
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Kiểm tra tính mơ hồ (Ambiguity): nếu >= 2 ứng viên điểm chênh nhau <= 0.02
    if len(candidates) >= 2:
        top_diff = abs(candidates[0]["score"] - candidates[1]["score"])
        is_ambiguous = top_diff <= 0.02
    else:
        is_ambiguous = False

    for cand in candidates:
        cand["is_ambiguous"] = is_ambiguous

    return candidates


def _detect_composite_keys(columns: list, col_values_list: list, rows: list, max_candidates: int = 5) -> list:
    """Nhận diện khóa kép kết hợp từ 2 cột khi không có khóa đơn đạt 100% (Mục 18)."""
    n_rows = len(rows)
    if n_rows < 2:
        return []

    # Lọc các cột ứng viên tiềm năng (không chọn cột mô tả, text dài, float nhiều thập phân)
    potential_cols = []
    for c in columns:
        sem = c["semantic_hint"]["type"]
        if sem in ("description", "address"):
            continue
        if c["null_ratio"] > 0.10:
            continue
        # Cột có độ phân biệt nhất định (unique_ratio > 0.01)
        if c["unique_ratio"] > 0.01 and c["unique_ratio"] < 1.0:
            potential_cols.append(c["index"])

    composite_candidates = []

    # Duyệt các cặp cột (col1, col2)
    for i in range(len(potential_cols)):
        for j in range(i + 1, len(potential_cols)):
            c1_idx = potential_cols[i]
            c2_idx = potential_cols[j]

            v1_list = col_values_list[c1_idx]
            v2_list = col_values_list[c2_idx]

            # Đếm số cặp giá trị kết hợp
            combined_pairs = set()
            null_count = 0
            for r_idx in range(n_rows):
                val1 = v1_list[r_idx]
                val2 = v2_list[r_idx]
                if val1 is None or val2 is None or val1 == "" or val2 == "":
                    null_count += 1
                else:
                    combined_pairs.add((str(val1), str(val2)))

            non_null_rows = n_rows - null_count
            if non_null_rows == 0:
                continue

            comb_unique_ratio = len(combined_pairs) / non_null_rows
            comb_null_ratio = null_count / n_rows

            # Nếu kết hợp đạt tỷ lệ duy nhất >= 98% và ít ô trống
            if comb_unique_ratio >= 0.98 and comb_null_ratio <= 0.05:
                score = round(0.50 * comb_unique_ratio + 0.30 * (1.0 - comb_null_ratio) + 0.20 * 0.8, 4)
                composite_candidates.append({
                    "column_indices": [c1_idx, c2_idx],
                    "column_names": [columns[c1_idx]["column_name"], columns[c2_idx]["column_name"]],
                    "score": score,
                    "unique_ratio": round(comb_unique_ratio, 4),
                    "null_ratio": round(comb_null_ratio, 4),
                    "is_perfect_key": (comb_unique_ratio == 1.0 and comb_null_ratio == 0.0),
                })

    composite_candidates.sort(key=lambda x: x["score"], reverse=True)
    return composite_candidates[:max_candidates]


# ----------------- 6. So khớp Cột Thông minh (Intelligent Column Matching - Mục 15) -----------------

DEFAULT_WEIGHTS = {
    "name": 0.30,       # 30% Tương đồng tên cột
    "data_type": 0.20,  # 20% Kiểu dữ liệu
    "value": 0.20,      # 20% Mẫu giá trị
    "semantic": 0.15,   # 15% Ngữ nghĩa
    "format": 0.10,     # 10% Định dạng
    "stats": 0.05,      # 5%  Thống kê (tỷ lệ trống/duy nhất)
}

DEFAULT_THRESHOLDS = {
    "auto_match": 0.90,       # >= 90% -> SAFE (Tự khớp)
    "suggest_confirm": 0.75,  # 75% - 89% -> REVIEW_REQUIRED (Đề xuất + người dùng duyệt)
    "possible_match": 0.50,   # 50% - 74% -> REVIEW_REQUIRED (Khả năng khớp / xem xét)
    # < 50% -> UNSAFE (Không tự khớp)
}

def match_two_columns(col_a: dict, col_b: dict, weights: dict = None) -> dict:
    """Tính điểm tương đồng giữa 2 cột theo 6 thành phần trọng số (Mục 15)."""
    W = dict(DEFAULT_WEIGHTS)
    if weights:
        W.update(weights)

    # 1. Tương đồng tên (30%)
    name_score = name_similarity(col_a["column_name"], col_b["column_name"])

    # 2. Tương đồng kiểu dữ liệu (20%)
    type_a = col_a["data_type"]
    type_b = col_b["data_type"]
    if type_a == type_b and type_a != "empty":
        type_score = 1.0
    elif (type_a in ("number", "text") and type_b in ("number", "text")):
        type_score = 0.5
    elif (type_a in ("date", "text") and type_b in ("date", "text")):
        type_score = 0.5
    else:
        type_score = 0.0

    # 3. Tương đồng mẫu giá trị (20%)
    samples_a = [str(x).strip().lower() for x in col_a.get("sample_values", []) if x is not None]
    samples_b = [str(x).strip().lower() for x in col_b.get("sample_values", []) if x is not None]
    if samples_a and samples_b:
        set_a = set(samples_a)
        set_b = set(samples_b)
        overlap = len(set_a & set_b)
        total_set = len(set_a | set_b)
        jaccard_val = overlap / total_set if total_set > 0 else 0.0

        # Kiểm tra độ tương đồng cấu trúc ký tự của mẫu
        def char_pattern(s):
            return "".join("d" if c.isdigit() else ("a" if c.isalpha() else "p") for c in s)
        pat_a = {char_pattern(s) for s in samples_a}
        pat_b = {char_pattern(s) for s in samples_b}
        pat_overlap = len(pat_a & pat_b) / len(pat_a | pat_b) if (pat_a | pat_b) else 0.0

        val_score = max(jaccard_val * 1.5, pat_overlap)
        val_score = min(1.0, val_score)
    else:
        val_score = 0.3 if type_score > 0.5 else 0.0

    # 4. Tương đồng ngữ nghĩa (15%)
    sem_a = col_a.get("semantic_hint", {}).get("type", "unknown")
    sem_b = col_b.get("semantic_hint", {}).get("type", "unknown")
    if sem_a == sem_b and sem_a != "unknown":
        sem_score = 1.0
    elif {sem_a, sem_b} <= {"price", "number", "quantity"}:
        sem_score = 0.70
    elif {sem_a, sem_b} <= {"customer_id", "product_id", "text"}:
        sem_score = 0.50
    else:
        sem_score = 0.0

    # 5. Tương đồng định dạng (10%)
    fmt_a = col_a.get("format_distribution", {})
    fmt_b = col_b.get("format_distribution", {})
    fmt_score = 0.5  # mặc định
    if type_a == "date" and type_b == "date":
        df_a = set(fmt_a.get("date_formats", {}).keys())
        df_b = set(fmt_b.get("date_formats", {}).keys())
        fmt_score = 1.0 if (df_a & df_b) else 0.7
    elif type_a == "number" and type_b == "number":
        nf_a = set(fmt_a.get("number_formats", {}).keys())
        nf_b = set(fmt_b.get("number_formats", {}).keys())
        fmt_score = 1.0 if (nf_a & nf_b) else 0.7

    # 6. Thống kê (5%)
    null_diff = abs(col_a.get("null_ratio", 0) - col_b.get("null_ratio", 0))
    uniq_diff = abs(col_a.get("unique_ratio", 0) - col_b.get("unique_ratio", 0))
    stats_score = max(0.0, 1.0 - (0.5 * null_diff + 0.5 * uniq_diff))

    # Điểm tổng hợp có trọng số
    total_score = (
        W["name"] * name_score
        + W["data_type"] * type_score
        + W["value"] * val_score
        + W["semantic"] * sem_score
        + W["format"] * fmt_score
        + W["stats"] * stats_score
    )
    total_score = round(min(1.0, max(0.0, total_score)), 4)

    return {
        "score": total_score,
        "details": {
            "name": round(name_score, 4),
            "data_type": round(type_score, 4),
            "value": round(val_score, 4),
            "semantic": round(sem_score, 4),
            "format": round(fmt_score, 4),
            "stats": round(stats_score, 4),
        },
    }


def match_schemas(schema_a: dict, schema_b: dict, weights: dict = None, thresholds: dict = None) -> dict:
    """So khớp toàn diện 2 bảng dữ liệu schema_a và schema_b (Mục 15, 20, 21).
    Phân định trạng thái: SAFE (>= 90%), REVIEW_REQUIRED (50%-89%), UNSAFE (< 50%).
    """
    TH = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        TH.update(thresholds)

    cols_a = schema_a["columns"]
    cols_b = schema_b["columns"]

    # Ma trận tính điểm cho mọi cặp (col_a, col_b)
    pair_scores = []
    for ca in cols_a:
        for cb in cols_b:
            res = match_two_columns(ca, cb, weights)
            score = res["score"]
            pair_scores.append({
                "source_index": ca["index"],
                "source_name": ca["column_name"],
                "target_index": cb["index"],
                "target_name": cb["column_name"],
                "score": score,
                "details": res["details"],
            })

    # Thuật toán ghép 1-1 tối ưu (Greedy theo điểm số cao nhất)
    pair_scores.sort(key=lambda x: x["score"], reverse=True)

    matched_sources = set()
    matched_targets = set()
    mappings = []

    for item in pair_scores:
        si = item["source_index"]
        ti = item["target_index"]
        score = item["score"]

        if si in matched_sources or ti in matched_targets:
            continue

        # Phân loại độ tin cậy
        if score >= TH["auto_match"]:
            status = "SAFE"
            match_type = "AUTO_MATCH"
            reason = "Độ tin cậy rất cao (%.1f%%), tự động ghép" % (score * 100)
        elif score >= TH["suggest_confirm"]:
            status = "REVIEW_REQUIRED"
            match_type = "SUGGEST_CONFIRM"
            reason = "Khớp tốt (%.1f%%), cần người dùng xác nhận" % (score * 100)
        elif score >= TH["possible_match"]:
            status = "REVIEW_REQUIRED"
            match_type = "POSSIBLE_MATCH"
            reason = "Có khả năng khớp (%.1f%%), cần kiểm tra" % (score * 100)
        else:
            status = "UNSAFE"
            match_type = "NO_MATCH"
            reason = "Độ tin cậy thấp (%.1f%%), không tự động ghép" % (score * 100)

        # Kiểm tra xung đột kiểu dữ liệu nghiêm trọng
        ca = cols_a[si]
        cb = cols_b[ti]
        if ca["data_type"] in ("date", "number") and cb["data_type"] in ("date", "number") and ca["data_type"] != cb["data_type"]:
            status = "REVIEW_REQUIRED"
            reason += " | Cảnh báo: Lệch kiểu dữ liệu (%s vs %s)" % (ca["data_type"], cb["data_type"])

        matched_sources.add(si)
        matched_targets.add(ti)

        mappings.append({
            "source_index": si,
            "source_name": item["source_name"],
            "target_index": ti,
            "target_name": item["target_name"],
            "score": score,
            "status": status,
            "match_type": match_type,
            "reason": reason,
            "details": item["details"],
        })

    # Liệt kê cột chưa ghép
    unmatched_sources = [ca for ca in cols_a if ca["index"] not in matched_sources]
    unmatched_targets = [cb for cb in cols_b if cb["index"] not in matched_targets]

    # Đề xuất kiểu merge (Mục 12, 28)
    rec = recommend_merge_mode(schema_a, schema_b, mappings)

    return {
        "mappings": mappings,
        "unmatched_sources": [{"index": c["index"], "name": c["column_name"]} for c in unmatched_sources],
        "unmatched_targets": [{"index": c["index"], "name": c["column_name"]} for c in unmatched_targets],
        "recommendation": rec,
        "matrix": pair_scores,
    }


def recommend_merge_mode(schema_a: dict, schema_b: dict, mappings: list) -> dict:
    """Đề xuất chế độ merge tối ưu: Nối dòng (UNION) hay Ghép khóa (JOIN) (Mục 12, 28)."""
    total_cols = max(schema_a["total_columns"], schema_b["total_columns"])
    if total_cols == 0:
        return {"mode": "UNION", "confidence": 1.0, "reason": "Hai bảng rỗng"}

    good_matches = [m for m in mappings if m["score"] >= 0.75]
    overlap_ratio = len(good_matches) / total_cols

    # Kiểm tra có khóa chung không
    keys_a = {k["column_name"] for k in schema_a.get("key_candidates", [])}
    keys_b = {k["column_name"] for k in schema_b.get("key_candidates", [])}

    shared_key = None
    for m in good_matches:
        if m["source_name"] in keys_a and m["target_name"] in keys_b:
            shared_key = m
            break

    # Nếu cấu trúc cột giống nhau từ 70% trở lên -> đề xuất nối dòng (UNION)
    if overlap_ratio >= 0.70:
        return {
            "mode": "UNION",
            "confidence": round(overlap_ratio, 2),
            "reason": "Hai bảng có %d/%d cột tương đồng cao (%.0f%%), phù hợp gộp thêm dòng (Append/Union)" % (len(good_matches), total_cols, overlap_ratio * 100),
        }
    elif shared_key is not None:
        return {
            "mode": "JOIN",
            "confidence": 0.90,
            "shared_key": shared_key["source_name"],
            "reason": "Tìm thấy khóa chung '%s' với độ tin cậy cao, phù hợp ghép theo khóa (Join/Match)" % shared_key["source_name"],
        }
    else:
        return {
            "mode": "REVIEW_REQUIRED",
            "confidence": 0.50,
            "reason": "Cấu trúc cột khác biệt (chỉ khớp %.0f%%) và không tìm thấy khóa chung rõ ràng; người dùng cần chỉ định chế độ" % (overlap_ratio * 100),
        }


# ----------------- 7. Kiểm tra Đối chiếu Độc lập (Independent Validation - Mục 0 điểm 10 & Mục 39) -----------------

def independent_match_check(schema_a: dict, schema_b: dict, mappings: list) -> dict:
    """Bộ kiểm tra độc lập đối chiếu kết quả so khớp cột.
    Được viết bằng giải thuật kiểm tra độc lập, không dùng chung ma trận điểm với bộ chính.
    """
    errors = []
    warnings = []

    src_map = {c["index"]: c for c in schema_a["columns"]}
    tgt_map = {c["index"]: c for c in schema_b["columns"]}

    seen_src = set()
    seen_tgt = set()

    for m in mappings:
        si = m["source_index"]
        ti = m["target_index"]

        # Kiểm tra chỉ số hợp lệ
        if si not in src_map:
            errors.append("Chỉ số cột nguồn %s không tồn tại trong schema nguồn" % si)
            continue
        if ti not in tgt_map:
            errors.append("Chỉ số cột đích %s không tồn tại trong schema đích" % ti)
            continue

        # Kiểm tra trùng lặp ánh xạ (1 cột không được ánh xạ 2 lần)
        if si in seen_src:
            errors.append("Cột nguồn '%s' bị gán nhiều hơn 1 lần" % src_map[si]["column_name"])
        if ti in seen_tgt:
            errors.append("Cột đích '%s' bị gán nhiều hơn 1 lần" % tgt_map[ti]["column_name"])

        seen_src.add(si)
        seen_tgt.add(ti)

        # Kiểm tra xung đột kiểu dữ liệu
        ca = src_map[si]
        cb = tgt_map[ti]
        if ca["data_type"] == "number" and cb["data_type"] == "date":
            errors.append("Không thể ghép cột số '%s' với cột ngày '%s'" % (ca["column_name"], cb["column_name"]))
        elif ca["data_type"] == "date" and cb["data_type"] == "number":
            errors.append("Không thể ghép cột ngày '%s' với cột số '%s'" % (ca["column_name"], cb["column_name"]))

        # Kiểm tra trạng thái an toàn: điểm < 90% không được có trạng thái SAFE
        if m.get("score", 0) < 0.90 and m.get("status") == "SAFE":
            errors.append("Vi phạm nguyên tắc an toàn: điểm %.2f (< 90%%) không được đặt là SAFE" % m.get("score", 0))

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "mapped_count": len(mappings),
    }
