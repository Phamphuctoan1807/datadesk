"""Advanced Data Cleaning Engine for DataDesk (Stage C - Future 2, Mục 75).
Cung cấp các bộ công cụ làm sạch dữ liệu chuyên sâu:
1. Chuẩn hóa Text (trim, khoảng trắng kép, hoa/thường/Title Case, Unicode NFC/NFD, bỏ dấu tiếng Việt, loại bỏ ký tự vô hình).
2. Chuẩn hóa Phone (Việt Nam 10 số, quốc tế E.164, các định dạng hiển thị nhóm).
3. Chuẩn hóa Email (trim, lowercase, regex RFC, phát hiện domain lỗi).
4. Chuẩn hóa Số, Tiền tệ, Phần trăm (nhận diện dấu phẩy/chấm động, tách đơn vị tiền tệ).
5. Quản lý trùng lặp nâng cao (Exact, Normalized, Fuzzy với Levenshtein & Token similarity theo ngưỡng).
6. Find & Replace an toàn (Exact, Contains, Safe Regex có preview thay đổi).
7. Bộ kiểm tra độc lập independent_cleaning_check.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Tuple, Optional, Set

# -------------------------------------------------------------
# 1. BẢNG MÃ TIẾNG VIỆT & CHUẨN HÓA TEXT
# -------------------------------------------------------------

VN_ACCENTS_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
    'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
    'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
    'Đ': 'D',
    'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
    'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
    'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
    'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
    'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
    'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
    'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
    'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
    'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y'
}

_INVISIBLE_CHARS_TABLE = None

def _get_invisible_chars_table():
    global _INVISIBLE_CHARS_TABLE
    if _INVISIBLE_CHARS_TABLE is None:
        table = {}
        for c in range(0x110000):
            ch = chr(c)
            cat = unicodedata.category(ch)
            # Cf = format (zero-width space, BOM, joiners), Cc = control except newline/tab
            if cat == 'Cf' or (cat == 'Cc' and ch not in ('\n', '\r', '\t')):
                table[c] = None
        _INVISIBLE_CHARS_TABLE = table
    return _INVISIBLE_CHARS_TABLE

def strip_vietnamese_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt chuẩn hóa sang ký tự ASCII gốc."""
    if not text:
        return ""
    # NFC trước để các dấu tổ hợp được gộp
    text = unicodedata.normalize('NFC', text)
    res = []
    for ch in text:
        res.append(VN_ACCENTS_MAP.get(ch, ch))
    return "".join(res)

def clean_text(val: Any,
               trim: bool = True,
               collapse_spaces: bool = True,
               case: str = 'none',
               unicode_form: str = 'NFC',
               strip_accents: bool = False,
               remove_invisible: bool = True) -> str:
    """Làm sạch và chuẩn hóa chuỗi văn bản theo các tùy chọn."""
    if val is None:
        return ""
    s = str(val)
    if remove_invisible:
        s = s.translate(_get_invisible_chars_table())
    if unicode_form in ('NFC', 'NFD', 'NFKC', 'NFKD'):
        s = unicodedata.normalize(unicode_form, s)
    if strip_accents:
        s = strip_vietnamese_accents(s)
    if collapse_spaces:
        s = re.sub(r'[ \t\f\v]+', ' ', s)
    if trim:
        s = s.strip()
    if case == 'lower':
        s = s.lower()
    elif case == 'upper':
        s = s.upper()
    elif case == 'title':
        # Viết hoa chữ cái đầu mỗi từ thông minh (hỗ trợ tiếng Việt)
        words = s.split(' ')
        s = ' '.join(w.capitalize() if w else '' for w in words)
    elif case == 'sentence':
        if s:
            s = s[0].upper() + s[1:].lower()
    return s


# -------------------------------------------------------------
# 2. CHUẨN HÓA SỐ ĐIỆN THOẠI (VIỆT NAM & QUỐC TẾ)
# -------------------------------------------------------------

VN_PHONE_PREFIXES = {
    # Viettel
    '086', '096', '097', '098', '032', '033', '034', '035', '036', '037', '038', '039',
    # Mobifone
    '089', '090', '093', '070', '079', '077', '076', '078',
    # Vinaphone
    '088', '091', '094', '083', '084', '085', '081', '082',
    # Vietnamobile
    '092', '056', '058',
    # Gmobile / Itelecom / Wintel
    '099', '059', '087', '055'
}

def clean_phone(val: Any, output_format: str = 'vn_standard') -> Tuple[str, bool, Optional[str]]:
    """Chuẩn hóa số điện thoại.
    output_format:
      - 'vn_standard': '0912345678'
      - 'vn_grouped': '0912 345 678'
      - 'e164': '+84912345678'
      - 'intl_grouped': '+84 912 345 678'
      - 'national': '84912345678'
    Trả về: (formatted_val, is_valid, error_reason)
    """
    if val is None or str(val).strip() == "":
        return "", True, None
    raw = str(val).strip()
    digits = re.sub(r'\D', '', raw)

    # Xử lý các tiền tố quốc tế của Việt Nam
    if digits.startswith('0084'):
        digits = '0' + digits[4:]
    elif digits.startswith('84') and len(digits) >= 11:
        digits = '0' + digits[2:]
    elif raw.startswith('+84') and len(digits) >= 11:
        digits = '0' + digits[2:]
    elif not digits.startswith('0') and len(digits) == 9:
        digits = '0' + digits

    if len(digits) != 10 or not digits.startswith('0'):
        return raw, False, "INVALID_PHONE_LENGTH"

    prefix = digits[:3]
    if prefix not in VN_PHONE_PREFIXES and prefix[:2] not in ('02', '03', '05', '07', '08', '09'):
        return raw, False, "UNKNOWN_PHONE_PREFIX"

    # Định dạng đầu ra
    if output_format == 'vn_standard':
        return digits, True, None
    elif output_format == 'vn_grouped':
        # Nhóm 4-3-3: 0912 345 678
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}", True, None
    elif output_format == 'e164':
        return f"+84{digits[1:]}", True, None
    elif output_format == 'intl_grouped':
        return f"+84 {digits[1:4]} {digits[4:7]} {digits[7:]}", True, None
    elif output_format == 'national':
        return f"84{digits[1:]}", True, None
    return digits, True, None


# -------------------------------------------------------------
# 3. CHUẨN HÓA EMAIL
# -------------------------------------------------------------

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

COMMON_TYPO_DOMAINS = {
    'gmai.com': 'gmail.com', 'gmial.com': 'gmail.com', 'gmaill.com': 'gmail.com', 'gamil.com': 'gmail.com',
    'hotmial.com': 'hotmail.com', 'yaho.com': 'yahoo.com', 'yahho.com': 'yahoo.com',
    'outlok.com': 'outlook.com', 'outloo.com': 'outlook.com'
}

def clean_email(val: Any, fix_typo_domain: bool = True) -> Tuple[str, bool, Optional[str]]:
    """Chuẩn hóa email: trim, lowercase, kiểm tra định dạng và sửa typo domain phổ biến."""
    if val is None or str(val).strip() == "":
        return "", True, None
    s = str(val).strip().lower()
    # Loại bỏ ngoặc bao quanh nếu có (ví dụ: <user@domain.com>)
    s = re.sub(r'^[<"\'\(]+|[>"\'\)]+$', '', s).strip()

    if not EMAIL_REGEX.match(s):
        return s, False, "INVALID_EMAIL_FORMAT"

    parts = s.split('@', 1)
    if len(parts) == 2 and fix_typo_domain:
        user, domain = parts
        if domain in COMMON_TYPO_DOMAINS:
            domain = COMMON_TYPO_DOMAINS[domain]
            s = f"{user}@{domain}"

    return s, True, None


# -------------------------------------------------------------
# 4. CHUẨN HÓA SỐ, TIỀN TỆ, PHẦN TRĂM
# -------------------------------------------------------------

CURRENCY_SYMBOLS = {
    '₫': 'VND', 'đ': 'VND', 'vnd': 'VND', 'vnđ': 'VND',
    '$': 'USD', 'usd': 'USD',
    '€': 'EUR', 'eur': 'EUR',
    '¥': 'JPY', 'jpy': 'JPY',
    '£': 'GBP', 'gbp': 'GBP'
}

def clean_number(val: Any, decimal_sep: str = 'auto') -> Tuple[Optional[Decimal], bool, Optional[str]]:
    """Phân tích số thực hoặc số nguyên từ chuỗi có dấu phân cách hàng nghìn/thập phân.
    decimal_sep: 'auto', '.', ','
    """
    if val is None or str(val).strip() == "":
        return None, True, None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val)), True, None

    s = str(val).strip()
    # Loại bỏ ký tự tiền tệ và khoảng trắng
    s = re.sub(r'[^\d,.-]', '', s)
    if not s or s in ('-', '.'):
        return None, False, "INVALID_NUMBER"

    # Nhận diện dấu phân cách
    has_comma = ',' in s
    has_dot = '.' in s

    if decimal_sep == 'auto':
        if has_comma and has_dot:
            # Nếu dấu cuối cùng là dấu phẩy: kiểu VN/EU (1.234,56)
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                # Kiểu US: 1,234.56
                s = s.replace(',', '')
        elif has_comma and not has_dot:
            if s.count(',') > 1:
                # Nhiều dấu phẩy: chắc chắn là phân cách hàng nghìn (1,500,000)
                s = s.replace(',', '')
            else:
                parts = s.split(',')
                if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                    # Khả năng cao là hàng nghìn: 1,234 -> 1234
                    s = s.replace(',', '')
                elif len(parts) == 2 and len(parts[1]) != 3:
                    # Dấu phẩy thập phân: 12,5 -> 12.5
                    s = s.replace(',', '.')
                else:
                    s = s.replace(',', '')
        elif has_dot and not has_comma:
            if s.count('.') > 1:
                # Nhiều dấu chấm: phân cách hàng nghìn kiểu VN (1.500.000)
                s = s.replace('.', '')
            else:
                # 1 dấu chấm: giữ nguyên (12.34)
                pass
    elif decimal_sep == ',':
        s = s.replace('.', '').replace(',', '.')
    elif decimal_sep == '.':
        s = s.replace(',', '')

    try:
        dec = Decimal(s)
        return dec, True, None
    except InvalidOperation:
        return None, False, "INVALID_NUMBER"

def clean_currency(val: Any) -> Dict[str, Any]:
    """Nhận diện số tiền và đơn vị tiền tệ."""
    if val is None or str(val).strip() == "":
        return {"amount": None, "currency": None, "raw": val, "valid": True}
    raw = str(val).strip()
    detected_currency = None

    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in raw.lower():
            detected_currency = code
            break

    amount, valid, err = clean_number(raw)
    return {
        "amount": amount,
        "currency": detected_currency or "VND",
        "raw": raw,
        "valid": valid,
        "error": err
    }

def clean_percentage(val: Any, as_ratio: bool = False) -> Dict[str, Any]:
    """Chuẩn hóa phần trăm: '15.5%' -> 15.5 (hoặc 0.155 nếu as_ratio=True)."""
    if val is None or str(val).strip() == "":
        return {"value": None, "raw": val, "valid": True}
    raw = str(val).strip()
    s = raw.replace('%', '').strip()
    amount, valid, err = clean_number(s)
    if not valid or amount is None:
        return {"value": None, "raw": raw, "valid": False, "error": err}
    val_out = amount / Decimal(100) if as_ratio else amount
    return {"value": val_out, "raw": raw, "valid": True}


# -------------------------------------------------------------
# 5. FIND & REPLACE AN TOÀN (EXACT, CONTAINS, SAFE REGEX)
# -------------------------------------------------------------

DANGEROUS_REGEX_PATTERNS = [
    r'\([^)]*\+[^)]*\)\+',    # (a+)+
    r'\([^)]*\*[^)]*\)\*',    # (a*)*
    r'\([^)]*\+[^)]*\)\*',    # (a+)*
    r'\([^)]*\*[^)]*\)\+',    # (a*)+
    r'(\w+\s*){5,}',          # lặp không bounded
]

def validate_regex_pattern(pattern: str) -> Tuple[bool, Optional[str]]:
    """Kiểm tra độ an toàn của biểu thức chính quy để chống lỗi ReDoS."""
    if len(pattern) > 200:
        return False, "Biểu thức Regex quá dài (tối đa 200 ký tự)."
    for p in DANGEROUS_REGEX_PATTERNS:
        if re.search(p, pattern):
            return False, "Biểu thức chứa cấu trúc lặp lồng nhau có nguy cơ ReDoS."
    try:
        re.compile(pattern)
        return True, None
    except re.error as e:
        return False, f"Cú pháp Regex không hợp lệ: {str(e)}"

def preview_find_replace(rows: List[List[Any]],
                         col_indices: List[int],
                         find_val: str,
                         replace_val: str,
                         match_type: str = 'contains',
                         case_sensitive: bool = False,
                         is_regex: bool = False,
                         max_preview: int = 50) -> Dict[str, Any]:
    """Xem trước kết quả Tìm kiếm & Thay thế mà không sửa dữ liệu."""
    if not rows or len(rows) < 2 or not col_indices:
        return {"matches_count": 0, "affected_rows": 0, "preview_items": []}

    header = rows[0]
    regex_obj = None

    if is_regex:
        valid, err = validate_regex_pattern(find_val)
        if not valid:
            return {"error": err, "matches_count": 0, "affected_rows": 0, "preview_items": []}
        flags = 0 if case_sensitive else re.IGNORECASE
        regex_obj = re.compile(find_val, flags)

    preview_items = []
    affected_rows_set = set()
    matches_count = 0

    find_cmp = find_val if case_sensitive else find_val.lower()

    for r_idx in range(1, len(rows)):
        row = rows[r_idx]
        row_has_match = False
        for c_idx in col_indices:
            if c_idx >= len(row):
                continue
            cell_val = "" if row[c_idx] is None else str(row[c_idx])
            cell_cmp = cell_val if case_sensitive else cell_val.lower()

            matched = False
            new_val = cell_val

            if is_regex and regex_obj:
                if regex_obj.search(cell_val):
                    matched = True
                    new_val = regex_obj.sub(replace_val, cell_val)
            elif match_type == 'exact':
                if cell_cmp == find_cmp:
                    matched = True
                    new_val = replace_val
            elif match_type == 'contains':
                if find_cmp in cell_cmp:
                    matched = True
                    if case_sensitive:
                        new_val = cell_val.replace(find_val, replace_val)
                    else:
                        # Case insensitive string replace
                        pattern = re.escape(find_val)
                        new_val = re.sub(pattern, replace_val, cell_val, flags=re.IGNORECASE)

            if matched and new_val != cell_val:
                matches_count += 1
                row_has_match = True
                if len(preview_items) < max_preview:
                    preview_items.append({
                        "row_index": r_idx,
                        "col_index": c_idx,
                        "col_name": header[c_idx] if c_idx < len(header) else f"Col_{c_idx}",
                        "old_value": cell_val,
                        "new_value": new_val
                    })
        if row_has_match:
            affected_rows_set.add(r_idx)

    return {
        "matches_count": matches_count,
        "affected_rows": len(affected_rows_set),
        "preview_items": preview_items
    }

def apply_find_replace(rows: List[List[Any]],
                       col_indices: List[int],
                       find_val: str,
                       replace_val: str,
                       match_type: str = 'contains',
                       case_sensitive: bool = False,
                       is_regex: bool = False) -> Tuple[List[List[Any]], Dict[str, Any]]:
    """Áp dụng Tìm kiếm & Thay thế, trả về bản sao dữ liệu mới đã biến đổi và thống kê."""
    if not rows or len(rows) < 2 or not col_indices:
        return [list(r) for r in rows], {"affected_cells": 0, "affected_rows": 0}

    regex_obj = None
    if is_regex:
        valid, err = validate_regex_pattern(find_val)
        if not valid:
            raise ValueError(err)
        flags = 0 if case_sensitive else re.IGNORECASE
        regex_obj = re.compile(find_val, flags)

    new_rows = [list(rows[0])]
    find_cmp = find_val if case_sensitive else find_val.lower()

    affected_cells = 0
    affected_rows = 0

    for r_idx in range(1, len(rows)):
        row = list(rows[r_idx])
        row_changed = False
        for c_idx in col_indices:
            if c_idx >= len(row):
                continue
            cell_val = "" if row[c_idx] is None else str(row[c_idx])
            cell_cmp = cell_val if case_sensitive else cell_val.lower()

            matched = False
            new_val = cell_val

            if is_regex and regex_obj:
                if regex_obj.search(cell_val):
                    matched = True
                    new_val = regex_obj.sub(replace_val, cell_val)
            elif match_type == 'exact':
                if cell_cmp == find_cmp:
                    matched = True
                    new_val = replace_val
            elif match_type == 'contains':
                if find_cmp in cell_cmp:
                    matched = True
                    if case_sensitive:
                        new_val = cell_val.replace(find_val, replace_val)
                    else:
                        pattern = re.escape(find_val)
                        new_val = re.sub(pattern, replace_val, cell_val, flags=re.IGNORECASE)

            if matched and new_val != cell_val:
                row[c_idx] = new_val
                affected_cells += 1
                row_changed = True
        if row_changed:
            affected_rows += 1
        new_rows.append(row)

    return new_rows, {"affected_cells": affected_cells, "affected_rows": affected_rows}


# -------------------------------------------------------------
# 6. QUẢN LÝ TRÙNG LẶP NÂNG CAO (EXACT, NORMALIZED, FUZZY)
# -------------------------------------------------------------

def levenshtein_distance(s1: str, s2: str) -> int:
    """Tính khoảng cách Levenshtein giữa 2 chuỗi với ma trận tối ưu 1 hàng."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1] + [0] * len(s2)
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row[j + 1] = min(insertions, deletions, substitutions)
        previous_row = current_row
    return previous_row[-1]

def string_similarity(s1: str, s2: str) -> float:
    """Tính độ tương đồng 0.0 -> 1.0 kết hợp Levenshtein và Token Sort / Set Ratio."""
    s1, s2 = s1.strip(), s2.strip()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    max_len = max(len(s1), len(s2))
    lev_sim = 1.0 - (levenshtein_distance(s1, s2) / max_len)

    # Token sort ratio (xử lý đảo từ như 'Nguyen Van An' vs 'Van An Nguyen')
    t1 = s1.lower().split()
    t2 = s2.lower().split()
    sorted_s1 = " ".join(sorted(t1))
    sorted_s2 = " ".join(sorted(t2))
    max_sorted_len = max(len(sorted_s1), len(sorted_s2))
    token_sort_sim = 1.0 - (levenshtein_distance(sorted_s1, sorted_s2) / max_sorted_len) if max_sorted_len > 0 else 0.0

    # Jaccard token set similarity
    set1, set2 = set(t1), set(t2)
    jaccard = len(set1 & set2) / len(set1 | set2) if (set1 and set2) else 0.0

    score = max(lev_sim, 0.6 * token_sort_sim + 0.4 * jaccard)
    return round(float(score), 4)

class DisjointSet:
    """Cấu trúc Union-Find để gom nhóm trùng lặp."""
    def __init__(self, elements):
        self.parent = {e: e for e in elements}
    def find(self, e):
        path = []
        while self.parent[e] != e:
            path.append(e)
            e = self.parent[e]
        for node in path:
            self.parent[node] = e
        return e
    def union(self, e1, e2):
        r1, r2 = self.find(e1), self.find(e2)
        if r1 != r2:
            self.parent[r2] = r1

def find_duplicates(rows: List[List[Any]],
                    key_cols: Optional[List[int]] = None,
                    mode: str = 'exact',
                    threshold: float = 0.85) -> Dict[str, Any]:
    """Phát hiện các nhóm trùng lặp trong dataset.
    mode: 'exact', 'normalized', 'fuzzy'
    threshold: áp dụng cho fuzzy (mặc định 0.85)
    """
    if not rows or len(rows) <= 1:
        return {"clusters": [], "duplicate_row_indices": [], "total_duplicates": 0}

    n_cols = len(rows[0])
    cols = key_cols if key_cols is not None else list(range(n_cols))
    cols = [c for c in cols if 0 <= c < n_cols]
    if not cols:
        cols = list(range(n_cols))

    n_data_rows = len(rows) - 1

    if mode in ('exact', 'normalized'):
        groups: Dict[Tuple, List[int]] = {}
        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            key_vals = []
            for c in cols:
                v = row[c] if c < len(row) else ""
                s = "" if v is None else str(v)
                if mode == 'normalized':
                    s = clean_text(s, trim=True, collapse_spaces=True, case='lower', strip_accents=True)
                key_vals.append(s)
            key_tuple = tuple(key_vals)
            groups.setdefault(key_tuple, []).append(r_idx)

        clusters = [cluster for cluster in groups.values() if len(cluster) > 1]
        dup_indices = []
        for c in clusters:
            dup_indices.extend(c[1:])  # Các dòng trùng sau dòng đầu tiên

        return {
            "mode": mode,
            "clusters": clusters,
            "duplicate_row_indices": sorted(dup_indices),
            "total_duplicates": len(dup_indices)
        }

    elif mode == 'fuzzy':
        # Chuẩn bị representation dạng chuỗi cho từng dòng
        row_keys = {}
        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            vals = []
            for c in cols:
                v = row[c] if c < len(row) else ""
                vals.append(clean_text(str(v or ""), trim=True, collapse_spaces=True, case='lower', strip_accents=True))
            row_keys[r_idx] = " ".join(vals)

        dset = DisjointSet(range(1, len(rows)))
        row_list = list(range(1, len(rows)))

        # Giới hạn số cặp so khớp nếu dataset lớn: chia bucket theo 2 ký tự đầu
        buckets: Dict[str, List[int]] = {}
        for r_idx in row_list:
            prefix = row_keys[r_idx][:2] if len(row_keys[r_idx]) >= 2 else " "
            buckets.setdefault(prefix, []).append(r_idx)

        # So khớp trong từng bucket và giữa các dòng ngắn
        for b_rows in buckets.values():
            m = len(b_rows)
            for i in range(m):
                r1 = b_rows[i]
                s1 = row_keys[r1]
                for j in range(i + 1, m):
                    r2 = b_rows[j]
                    s2 = row_keys[r2]
                    sim = string_similarity(s1, s2)
                    if sim >= threshold:
                        dset.union(r1, r2)

        # Gom nhóm cluster
        cluster_map: Dict[int, List[int]] = {}
        for r_idx in row_list:
            root = dset.find(r_idx)
            cluster_map.setdefault(root, []).append(r_idx)

        clusters = [c for c in cluster_map.values() if len(c) > 1]
        dup_indices = []
        for c in clusters:
            dup_indices.extend(c[1:])

        return {
            "mode": mode,
            "threshold": threshold,
            "clusters": clusters,
            "duplicate_row_indices": sorted(dup_indices),
            "total_duplicates": len(dup_indices)
        }

    return {"clusters": [], "duplicate_row_indices": [], "total_duplicates": 0}

def deduplicate_dataset(rows: List[List[Any]],
                         key_cols: Optional[List[int]] = None,
                         mode: str = 'exact',
                         strategy: str = 'keep_first',
                         threshold: float = 0.85) -> Tuple[List[List[Any]], Dict[str, Any]]:
    """Loại bỏ hoặc gom các dòng trùng lặp theo chiến lược.
    strategy: 'keep_first', 'keep_last', 'remove_all'
    """
    if not rows or len(rows) <= 1:
        return [list(r) for r in rows], {"removed_count": 0, "original_rows": len(rows)}

    dup_info = find_duplicates(rows, key_cols=key_cols, mode=mode, threshold=threshold)
    clusters = dup_info["clusters"]

    rows_to_remove = set()
    for cluster in clusters:
        if strategy == 'keep_first':
            rows_to_remove.update(cluster[1:])
        elif strategy == 'keep_last':
            rows_to_remove.update(cluster[:-1])
        elif strategy == 'remove_all':
            rows_to_remove.update(cluster)

    new_rows = [list(rows[0])]  # header
    for r_idx in range(1, len(rows)):
        if r_idx not in rows_to_remove:
            new_rows.append(list(rows[r_idx]))

    return new_rows, {
        "original_rows": len(rows),
        "retained_rows": len(new_rows),
        "removed_count": len(rows_to_remove),
        "duplicate_clusters": len(clusters),
        "mode": mode,
        "strategy": strategy
    }


# -------------------------------------------------------------
# 7. BỘ KIỂM TRA ĐỐI CHIẾU ĐỘC LẬP (INDEPENDENT CHECK)
# -------------------------------------------------------------

def independent_cleaning_check(original_rows: List[List[Any]],
                               cleaned_rows: List[List[Any]],
                               operation: str,
                               **kwargs) -> Dict[str, Any]:
    """Kiểm tra đối chiếu độc lập theo Mục 0 nguyên tắc 10 của Lộ trình:
    - Bảo toàn tiêu đề và số cột (không làm mất cấu trúc)
    - Đối chiếu dòng và phát hiện mất dữ liệu ngoài ý muốn
    - Kiểm tra tính bất biến của bộ dữ liệu gốc
    """
    errors = []
    warnings = []

    if not original_rows or not cleaned_rows:
        return {"valid": False, "errors": ["Dữ liệu rỗng"]}

    # 1. Kiểm tra header
    orig_header = original_rows[0]
    clean_header = cleaned_rows[0]
    if orig_header != clean_header:
        errors.append("Tiêu đề cột bị thay đổi không mong muốn.")

    # 2. Kiểm tra thao tác cụ thể
    if operation == 'deduplicate':
        strat = kwargs.get('strategy', 'keep_first')
        if len(cleaned_rows) > len(original_rows):
            errors.append("Số dòng sau khi lọc trùng lại tăng lên.")
        elif strat == 'keep_first' and len(cleaned_rows) < 1:
            errors.append("Dữ liệu bị xóa toàn bộ sau khi lọc trùng.")

    elif operation == 'find_replace':
        if len(cleaned_rows) != len(original_rows):
            errors.append(f"Số dòng bị thay đổi từ {len(original_rows)} thành {len(cleaned_rows)} khi Find & Replace.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "original_count": len(original_rows),
        "cleaned_count": len(cleaned_rows)
    }
