"""Chuẩn hóa dữ liệu (Giai đoạn 4 của lộ trình): chữ, khoảng trắng, Unicode, ô trống, số điện thoại, email, số/tiền, phần trăm, ngày.
Nguyên tắc: không đoán khi không đủ bằng chứng (ví dụ 1.234 hay 05/03/2026) mà đánh dấu 'review' và giữ nguyên ô; ô không chuẩn hóa được
là 'invalid' và cũng giữ nguyên. Có hai bản cài: norm_column (xử lý chính) và inorm_column (kiểm tra độc lập, cách viết khác).
Mỗi hàm trả về danh sách (giá trị mới, trạng thái, mã lỗi hoặc None) theo từng ô; trạng thái: empty, unchanged, changed, invalid, review."""
import re, unicodedata, datetime as dt
from decimal import Decimal as D
import formula as F

KINDS = ("text", "null", "phone", "email", "number", "percentage", "date")
KIND_VN = {"text": "chữ và khoảng trắng", "null": "ô trống giả (N/A, -, null)", "phone": "số điện thoại", "email": "email", "number": "số và tiền", "percentage": "phần trăm", "date": "ngày"}
DEFAULT_NULLS = ["n/a", "na", "null", "none", "nil", "-", "--", "#n/a", "không có", "khong co"]
MAXCOLS = 20
CODES = {"phone": "INVALID_PHONE", "email": "INVALID_EMAIL", "number": "INVALID_NUMBER", "percentage": "INVALID_NUMBER", "date": "INVALID_DATE", "text": "INVALID_TEXT", "null": "INVALID_TEXT"}

class NormError(Exception):
    def __init__(self, code, msg, op_id=None): super().__init__(msg); self.code, self.msg, self.op_id = code, msg, op_id

def blank(v): return v is None or (isinstance(v, str) and not v.strip())
def isnumv(v): return isinstance(v, (int, float, D)) and not isinstance(v, bool)

# ---------------- biên dịch và kiểm tra cấu hình bước ----------------
def compile_spec(op, names, ctypes, protected):
    """Kiểm tra cấu hình một bước chuẩn hóa. Cột do bước trước tạo ra dùng được; cột công thức bị chặn (hãy sửa công thức)."""
    names, ctypes = list(names), list(ctypes); rid = op.get("id"); label = (op.get("name") or "").strip() or "Chuẩn hóa"
    def fail(code, msg): raise NormError(code, 'Bước "%s": %s' % (label, msg), rid)
    kind = op.get("kind")
    if kind not in KINDS: fail("ERROR_OPERATOR", "loại chuẩn hóa không hợp lệ.")
    cols = []
    for c in op.get("columns") or []:
        c = str(c).strip()
        if c and F.norm(c) not in [F.norm(x) for x in cols]: cols.append(c)
    if not cols: fail("ERROR_COLUMN", "chưa chọn cột nào.")
    if len(cols) > MAXCOLS: fail("ERROR_SYNTAX", "tối đa %d cột mỗi bước." % MAXCOLS)
    mode = "new_column" if op.get("mode") == "new_column" else "replace"
    known = {}
    for j in range(len(names) - 1, -1, -1): known[F.norm(names[j])] = j
    exact = []
    for c in cols:
        k = F.norm(c)
        if k not in known: fail("ERROR_COLUMN", 'cột "%s" không tồn tại.' % c)
        if k in protected: fail("PROTECTED_COLUMN", 'cột "%s" là cột công thức, không chuẩn hóa được; hãy sửa công thức.' % c)
        exact.append(names[known[k]])
    o = op.get("options") or {}; opts = {}
    if kind == "text":
        opts["case"] = o.get("case", "none"); opts["accents"] = o.get("accents", "keep")
        if opts["case"] not in ("none", "lower", "upper", "title"): fail("ERROR_VALUE", "kiểu chữ hoa thường không hợp lệ.")
        if opts["accents"] not in ("keep", "strip"): fail("ERROR_VALUE", "tùy chọn dấu tiếng Việt không hợp lệ.")
    elif kind == "phone":
        opts["format"] = o.get("format", "vn")
        if opts["format"] not in ("vn", "e164"): fail("ERROR_VALUE", "định dạng số điện thoại không hợp lệ.")
    elif kind == "date":
        opts["order"] = o.get("order", "auto")
        if opts["order"] not in ("auto", "dmy", "mdy"): fail("ERROR_VALUE", "thứ tự ngày tháng không hợp lệ.")
    elif kind == "null":
        toks = o.get("tokens")
        toks = DEFAULT_NULLS if toks in (None, "") else [t.strip() for t in (toks.split(",") if isinstance(toks, str) else toks)]
        toks = [t for t in toks if t]
        if not toks or len(toks) > 30: fail("ERROR_VALUE", "danh sách giá trị trống giả cần từ 1 đến 30 mục.")
        opts["tokens"] = toks
    created = {}
    if mode == "new_column":
        for c in exact:
            nn = "%s (chuẩn hóa)" % c; k = F.norm(nn)
            if k in known: fail("DUPLICATE_COLUMN", 'cột "%s" đã tồn tại; hãy dùng chế độ ghi đè trong kết quả.' % nn)
            names.append(nn); ctypes.append("text"); known[k] = len(names) - 1; created[c] = nn
    return {"id": rid, "label": label, "kind": kind, "mode": mode, "columns": exact, "opts": opts, "created": created}

# ---------------- bản xử lý chính ----------------
_CF = None
def _drop():  # bảng xóa ký tự định dạng (zero-width, BOM...) và ký tự điều khiển không phải khoảng trắng
    global _CF
    if _CF is None:
        _CF = {}
        for c in range(0x110000):
            ch = chr(c); cat = unicodedata.category(ch)
            if cat == "Cf" or (cat == "Cc" and not ch.isspace()): _CF[c] = None
    return _CF
def _clean(s): return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).translate(_drop())).strip()

def _case(s, case):
    if case == "lower": return s.lower()
    if case == "upper": return s.upper()
    if case == "title": return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
    return s
def _strip_acc(s):
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return unicodedata.normalize("NFC", "".join(c for c in s if unicodedata.category(c) != "Mn"))

def _blank_cell(v):  # ô trống hoặc chỉ có khoảng trắng: trả về "" (đổi chỉ khi trước đó là chuỗi khoảng trắng)
    return ("", "empty", None) if v is None or v == "" else ("", "changed", None)

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}")
PHONE_OK = re.compile(r"0[35789]\d{8}|02\d{9}")
RX_DMY = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?")
RX_YMD = re.compile(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?")
RX_VN = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)

def _phone(v, fmt):
    if blank(v): return _blank_cell(v)
    num = isnumv(v)
    if isinstance(v, bool) or isinstance(v, (dt.date, dt.datetime)): return v, "invalid", "INVALID_PHONE"
    if num:
        if v != int(v) or v < 0: return v, "invalid", "INVALID_PHONE"
        digits = str(int(v)); plus = False
    else:
        s = _clean(v); plus = s.startswith("+"); body = s[1:] if plus else s
        if re.search(r"[^\d\s.\-()/]", body): return v, "invalid", "INVALID_PHONE"
        digits = re.sub(r"\D", "", body)
    if plus or digits.startswith("00"):
        if digits.startswith("00"): digits = digits[2:]
        if not digits.startswith("84"): return v, "invalid", "INVALID_PHONE"
        nat = "0" + digits[2:]
    elif digits.startswith("84") and len(digits) in (11, 12): nat = "0" + digits[2:]
    elif len(digits) == 9 and digits[0] in "35789": nat = "0" + digits  # Excel hay làm mất số 0 đầu
    else: nat = digits
    if not PHONE_OK.fullmatch(nat): return v, "invalid", "INVALID_PHONE"
    out = nat if fmt == "vn" else "+84" + nat[1:]
    return out, ("unchanged" if out == v else "changed"), None

def _email(v):
    if blank(v): return _blank_cell(v)
    if not isinstance(v, str): return v, "invalid", "INVALID_EMAIL"
    s = _clean(v)
    if not EMAIL.fullmatch(s): return v, "invalid", "INVALID_EMAIL"
    return s.lower(), ("unchanged" if s.lower() == v else "changed"), None

def _dparts(s):
    m = RX_YMD.fullmatch(s)
    if m: return "ymd", int(m[1]), int(m[2]), int(m[3])
    m = RX_VN.fullmatch(s)
    if m: return "dmy!", int(m[3]), int(m[2]), int(m[1])
    m = RX_DMY.fullmatch(s)
    if m: return "ab", int(m[3]), int(m[1]), int(m[2])
    return None

def _mk_date(y, m, d):
    try: return dt.datetime(y, m, d)
    except ValueError: return None

def norm_column(kind, vals, opts, numfmt, to_num, to_date):
    n = len(vals); out = [None] * n
    if kind == "text":
        for i, v in enumerate(vals):
            if blank(v): out[i] = _blank_cell(v)
            elif not isinstance(v, str): out[i] = (v, "unchanged", None)
            else: s = _strip_acc(_case(_clean(v), opts["case"])) if opts["accents"] == "strip" else _case(_clean(v), opts["case"]); out[i] = (s, "unchanged" if s == v else "changed", None)
    elif kind == "null":
        toks = {t.casefold() for t in opts["tokens"]}
        for i, v in enumerate(vals):
            if blank(v): out[i] = _blank_cell(v)
            elif isinstance(v, str) and _clean(v).casefold() in toks: out[i] = ("", "changed", None)
            else: out[i] = (v, "unchanged", None)
    elif kind == "phone":
        for i, v in enumerate(vals): out[i] = _phone(v, opts["format"])
    elif kind == "email":
        for i, v in enumerate(vals): out[i] = _email(v)
    elif kind in ("number", "percentage"):
        sidx = [i for i, v in enumerate(vals) if isinstance(v, str) and v.strip()]; cleaned = [_clean(vals[i]) for i in sidx]
        plan, _, _ = F.number_plan(cleaned, numfmt); pos = {i: k for k, i in enumerate(sidx)}
        for i, v in enumerate(vals):
            if blank(v): out[i] = _blank_cell(v); continue
            if isnumv(v): out[i] = (v, "unchanged", None); continue
            if not isinstance(v, str): out[i] = (v, "invalid", "INVALID_NUMBER"); continue
            k = pos[i]; s = cleaned[k]; pct = "%" in s
            if kind == "number" and pct: out[i] = (v, "invalid", "INVALID_NUMBER"); continue
            x = plan[k] if k in plan else to_num(s)
            if k in plan and x is None: out[i] = (v, "review", "AMBIGUOUS_NUMBER"); continue
            if x is None: out[i] = (v, "invalid", "INVALID_NUMBER"); continue
            if kind == "percentage":
                if not pct: out[i] = (v, "review", "AMBIGUOUS_PERCENT"); continue
                x = float("%.15g" % (x / 100))
            out[i] = (F.cellval(float(x)), "changed", None)
    elif kind == "date":
        parts = {}; dmy_ev = mdy_ev = False
        for i, v in enumerate(vals):
            if isinstance(v, str) and v.strip():
                p = _dparts(_clean(v)); parts[i] = p
                if p and p[0] == "ab":
                    a, b = p[2], p[3]
                    if a > 12 and b <= 12: dmy_ev = True
                    if b > 12 and a <= 12: mdy_ev = True
        order = opts["order"] if opts["order"] != "auto" else ("dmy" if dmy_ev and not mdy_ev else "mdy" if mdy_ev and not dmy_ev else None)
        for i, v in enumerate(vals):
            if blank(v): out[i] = _blank_cell(v); continue
            if isinstance(v, (dt.datetime, dt.date)) and not isinstance(v, bool): out[i] = (v, "unchanged", None); continue
            if not isinstance(v, str): out[i] = (v, "invalid", "INVALID_DATE"); continue
            p = parts[i]
            if not p: out[i] = (v, "invalid", "INVALID_DATE"); continue
            kind_, y, a, b = p
            if kind_ in ("ymd", "dmy!"): m_, d_ = a, b
            elif a == b: m_, d_ = a, b
            elif opts["order"] in ("dmy", "mdy"): m_, d_ = (b, a) if opts["order"] == "dmy" else (a, b)  # người dùng đã chọn thì tuân theo, ngày tháng sai khoảng thì báo lỗi
            elif a > 12: m_, d_ = b, a
            elif b > 12: m_, d_ = a, b
            elif order is None: out[i] = (v, "review", "AMBIGUOUS_DATE"); continue
            else: m_, d_ = (b, a) if order == "dmy" else (a, b)
            r = _mk_date(y, m_, d_)
            out[i] = (r, "changed", None) if r else (v, "invalid", "INVALID_DATE")
    return out

# ---------------- bản kiểm tra độc lập (cách viết khác) ----------------
def _iclean(s):
    keep = []
    for ch in unicodedata.normalize("NFC", s):
        cat = unicodedata.category(ch)
        if cat == "Cf" or (cat == "Cc" and not ch.isspace()): continue
        keep.append(" " if ch.isspace() else ch)
    return " ".join("".join(keep).split())

def _idigits(s): return "".join(ch for ch in s if ch.isdigit() and ch.isascii())

def _iphone(v, fmt):
    if blank(v): return ("", "empty", None) if (v is None or v == "") else ("", "changed", None)
    bad = ("invalid", "INVALID_PHONE")
    if isinstance(v, (bool, dt.date, dt.datetime)): return (v,) + bad
    plus = False
    if isnumv(v):
        if v != int(v) or v < 0: return (v,) + bad
        digits = str(int(v))
    else:
        s = _iclean(v); plus = s[:1] == "+"; body = s[1:] if plus else s
        if any(not (ch.isdigit() and ch.isascii()) and ch not in " .-()/" for ch in body): return (v,) + bad
        digits = _idigits(body)
    if plus or digits[:2] == "00":
        if digits[:2] == "00": digits = digits[2:]
        if digits[:2] != "84": return (v,) + bad
        nat = "0" + digits[2:]
    elif digits[:2] == "84" and len(digits) in (11, 12): nat = "0" + digits[2:]
    elif len(digits) == 9 and digits[0] in "35789": nat = "0" + digits
    else: nat = digits
    ok = (len(nat) == 10 and nat[0] == "0" and nat[1] in "35789" and nat.isdigit()) or (len(nat) == 11 and nat[:2] == "02" and nat.isdigit())
    if not ok: return (v,) + bad
    out = nat if fmt == "vn" else "+84" + nat[1:]
    return out, ("unchanged" if out == v else "changed"), None

def _iemail(v):
    if blank(v): return ("", "empty", None) if (v is None or v == "") else ("", "changed", None)
    if not isinstance(v, str): return v, "invalid", "INVALID_EMAIL"
    s = _iclean(v); bad = (v, "invalid", "INVALID_EMAIL")
    if s.count("@") != 1 or " " in s: return bad
    loc, dom = s.split("@")
    if not loc or any(not (ch.isascii() and (ch.isalnum() or ch in "._%+-")) for ch in loc): return bad
    labels = dom.split(".")
    if len(labels) < 2 or any(not l or l[0] == "-" or l[-1] == "-" or any(not (ch.isascii() and (ch.isalnum() or ch == "-")) for ch in l) for l in labels): return bad
    tld = labels[-1]
    if len(tld) < 2 or not (tld.isascii() and tld.isalpha()): return bad
    return s.lower(), ("unchanged" if s.lower() == v else "changed"), None

def _idate(s):  # (loại, năm, a, b) hoặc None; cách tách khác bản chính
    low = s.lower()
    if low.startswith("ngày") and "tháng" in low and "năm" in low:
        nums = re.findall(r"\d+", low)
        if len(nums) == 3 and len(nums[2]) == 4 and len(nums[0]) <= 2 and len(nums[1]) <= 2 and re.fullmatch(r"ngày\s+\d+\s+tháng\s+\d+\s+năm\s+\d+", low): return "dmy!", int(nums[2]), int(nums[1]), int(nums[0])
        return None
    head = s
    for sep in (" ", "T"):
        if sep in head:
            h, t = head.split(sep, 1)
            if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t): return None
            head = h; break
    ps = re.sub(r"[\-.]", "/", head).split("/")
    if len(ps) != 3 or not all(p.isdigit() and p.isascii() for p in ps): return None
    if len(ps[0]) == 4 and len(ps[1]) <= 2 and len(ps[2]) <= 2: return "ymd", int(ps[0]), int(ps[1]), int(ps[2])
    if len(ps[2]) == 4 and len(ps[0]) <= 2 and len(ps[1]) <= 2 and ps[0] and ps[1]: return "ab", int(ps[2]), int(ps[0]), int(ps[1])
    return None

def inorm_column(kind, vals, opts, numfmt, to_num, to_date):
    n = len(vals); out = [None] * n
    def empty(v): return ("", "empty", None) if (v is None or v == "") else ("", "changed", None)
    if kind == "text":
        for i, v in enumerate(vals):
            if blank(v): out[i] = empty(v); continue
            if not isinstance(v, str): out[i] = (v, "unchanged", None); continue
            s = _iclean(v)
            if opts["case"] == "lower": s = s.lower()
            elif opts["case"] == "upper": s = s.upper()
            elif opts["case"] == "title": s = " ".join(w.capitalize() for w in s.split(" "))
            if opts["accents"] == "strip":
                s = "".join(c for c in unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D")) if not unicodedata.combining(c)); s = unicodedata.normalize("NFC", s)
            out[i] = (s, "unchanged" if s == v else "changed", None)
    elif kind == "null":
        toks = set(t.casefold() for t in opts["tokens"])
        for i, v in enumerate(vals):
            if blank(v): out[i] = empty(v)
            elif isinstance(v, str) and _iclean(v).casefold() in toks: out[i] = ("", "changed", None)
            else: out[i] = (v, "unchanged", None)
    elif kind == "phone":
        for i, v in enumerate(vals): out[i] = _iphone(v, opts["format"])
    elif kind == "email":
        for i, v in enumerate(vals): out[i] = _iemail(v)
    elif kind in ("number", "percentage"):
        sidx = [i for i, v in enumerate(vals) if isinstance(v, str) and v.strip()]; cl = [_iclean(vals[i]) for i in sidx]
        plan = F.inumber_plan(cl, numfmt); pos = {i: k for k, i in enumerate(sidx)}
        for i, v in enumerate(vals):
            if blank(v): out[i] = empty(v); continue
            if isnumv(v): out[i] = (v, "unchanged", None); continue
            if not isinstance(v, str): out[i] = (v, "invalid", "INVALID_NUMBER"); continue
            k = pos[i]; s = cl[k]; pct = "%" in s
            if kind == "number" and pct: out[i] = (v, "invalid", "INVALID_NUMBER"); continue
            if k in plan:
                if plan[k] is None: out[i] = (v, "review", "AMBIGUOUS_NUMBER"); continue
                x = plan[k]
            else:
                f = to_num(s)
                if f is None: out[i] = (v, "invalid", "INVALID_NUMBER"); continue
                x = D(repr(f))
            if kind == "percentage":
                if not pct: out[i] = (v, "review", "AMBIGUOUS_PERCENT"); continue
                x = x / 100
            out[i] = (x, "changed", None)
    elif kind == "date":
        parts = {}; dmy_ev = mdy_ev = False
        for i, v in enumerate(vals):
            if isinstance(v, str) and v.strip():
                p = _idate(_iclean(v)); parts[i] = p
                if p and p[0] == "ab":
                    if p[2] > 12 and p[3] <= 12: dmy_ev = True
                    if p[3] > 12 and p[2] <= 12: mdy_ev = True
        order = opts["order"]
        if order == "auto": order = "dmy" if (dmy_ev and not mdy_ev) else ("mdy" if (mdy_ev and not dmy_ev) else None)
        for i, v in enumerate(vals):
            if blank(v): out[i] = empty(v); continue
            if isinstance(v, (dt.datetime, dt.date)) and not isinstance(v, bool): out[i] = (v, "unchanged", None); continue
            if not isinstance(v, str): out[i] = (v, "invalid", "INVALID_DATE"); continue
            p = parts[i]
            if p is None: out[i] = (v, "invalid", "INVALID_DATE"); continue
            k_, y, a, b = p
            if k_ in ("ymd", "dmy!"): m_, d_ = a, b
            elif a == b: m_, d_ = a, b
            elif opts["order"] in ("dmy", "mdy"): m_, d_ = (b, a) if opts["order"] == "dmy" else (a, b)
            elif a > 12: m_, d_ = b, a
            elif b > 12: m_, d_ = a, b
            elif order is None: out[i] = (v, "review", "AMBIGUOUS_DATE"); continue
            else: m_, d_ = (b, a) if order == "dmy" else (a, b)
            if 1 <= y <= 9999 and 1 <= m_ <= 12 and 1 <= d_ <= [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m_ - 1]: out[i] = (dt.datetime(y, m_, d_), "changed", None)
            else: out[i] = (v, "invalid", "INVALID_DATE")
    return out

# ---------------- gợi ý chuẩn hóa theo cột (chỉ điền sẵn biểu mẫu, không tự áp dụng) ----------------
def hints(names, cols, types, numfmt, to_num, to_date):
    out = []
    kw = {"email": ("email", "mail"), "phone": ("sđt", "sdt", "điện thoại", "dien thoai", "phone", "tel", "mobile", "di động", "di dong")}
    def noacc(s): return _strip_acc(F.norm(s))
    for j, (nm, vals) in enumerate(zip(names, cols)):
        sample = vals[:2000]; nb = [v for v in sample if not blank(v)]
        if not nb: continue
        h = noacc(nm); found = []
        def cnt(kind, opts):
            r = norm_column(kind, sample, opts, numfmt, to_num, to_date); return sum(1 for x in r if x[1] in ("changed", "invalid", "review"))
        at = sum(1 for v in nb if isinstance(v, str) and "@" in v) / len(nb)
        if at >= .6 or (any(k in h for k in kw["email"]) and at >= .3):
            c = cnt("email", {}); found += [("email", "%d ô email cần chuẩn hóa hoặc kiểm tra" % c, c)] if c else []
        else:
            ph = sum(1 for v in nb if re.fullmatch(r"\+?[\d\s.\-()]{9,16}", str(int(v)) if isnumv(v) and v == int(v) else str(v)) is not None) / len(nb)
            if ph >= .6 or (any(k in h for k in kw["phone"]) and ph >= .3):
                c = cnt("phone", {"format": "vn"}); found += [("phone", "%d ô số điện thoại cần chuẩn hóa hoặc kiểm tra" % c, c)] if c else []
            elif types[j] == "number":
                c = sum(1 for v in nb if isinstance(v, str)); found += [("number", "%d ô số đang là chữ (dạng 1.234, 1.000₫...)" % c, c)] if c else []
            elif types[j] == "date":
                c = sum(1 for v in nb if isinstance(v, str)); found += [("date", "%d ô ngày đang là chữ" % c, c)] if c else []
            else:
                c = cnt("text", {"case": "none", "accents": "keep"}); found += [("text", "%d ô thừa khoảng trắng hoặc ký tự lạ" % c, c)] if c else []
        toks = {t.casefold() for t in DEFAULT_NULLS}; c = sum(1 for v in nb if isinstance(v, str) and _clean(v).casefold() in toks)
        if c: found.append(("null", "%d ô là giá trị trống giả (N/A, -, null...)" % c, c))
        out += [{"col": j, "name": nm, "kind": k, "reason": r, "count": c_} for k, r, c_ in found[:3]]
    return out[:12]
