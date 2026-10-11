"""Formula Engine (Giai đoạn 2 của lộ trình). DSL giới hạn: toán tử, hàm, cột, hằng số, điều kiện.
Không dùng eval/exec/compile, không đụng tới tệp hay mạng. Có hai bộ tính tách biệt:
  - ev: bộ tính chính (số thực), dùng để tạo dữ liệu;
  - ieval: bộ tính độc lập (Decimal, cơ chế báo lỗi khác), chỉ dùng để kiểm tra lại kết quả đã xuất."""
import re, math, unicodedata, datetime as dt
from collections import Counter
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, InvalidOperation, localcontext, Context

# Kiểu biến đổi dùng chung cho các giai đoạn sau (mới hỗ trợ FORMULA)
OP_TYPES = ["FORMULA", "SET_VALUE", "REPLACE", "DELETE_VALUE", "CREATE_COLUMN", "CONDITIONAL", "FILTER", "SORT",
            "FILL_MISSING", "MARK", "COLOR", "NORMALIZE", "TYPE_CONVERT", "MERGE_COLUMN", "SPLIT_COLUMN"]
MAXLEN, MAXDEPTH, MAXOPS, MAXAST = 1000, 40, 30, 400
NUM = re.compile(r"[0-9]+(?:\.[0-9]+)?|\.[0-9]+")
IDENT = re.compile(r"[^\W\d]\w*")
CMP = ("=", "!=", ">", "<", ">=", "<=")
ARITY = {"ABS": (1, 1), "ROUND": (1, 2), "CEIL": (1, 1), "FLOOR": (1, 1), "MIN": (1, 99), "MAX": (1, 99), "SUM": (1, 99),
         "AVERAGE": (1, 99), "POWER": (2, 2), "SQRT": (1, 1), "CONCAT": (1, 99), "LEFT": (1, 2), "RIGHT": (1, 2), "MID": (3, 3),
         "LEN": (1, 1), "TRIM": (1, 1), "LOWER": (1, 1), "UPPER": (1, 1), "REPLACE": (4, 4), "SUBSTITUTE": (3, 3), "IF": (3, 3),
         "AND": (1, 99), "OR": (1, 99), "NOT": (1, 1), "YEAR": (1, 1), "MONTH": (1, 1), "DAY": (1, 1), "ISEMPTY": (1, 1), "ISNUMBER": (1, 1), "ISDATE": (1, 1), "CONTAINS": (2, 2), "STARTSWITH": (2, 2), "ENDSWITH": (2, 2)}

class FormulaError(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code, self.msg = code, msg
class Err:
    __slots__ = ("code",)
    def __init__(self, code): self.code = code
class Raise(Exception):
    def __init__(self, code): self.code = code

def norm(s): return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s))).strip().casefold()
def isnum(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def isdate(x): return isinstance(x, dt.date) and not isinstance(x, dt.datetime)
def dstr(d): return "%02d/%02d/%04d" % (d.day, d.month, d.year)

# ---------------- phân tích cú pháp ----------------
def _pats(names):
    out = []
    for nm in sorted(set(names), key=lambda s: -len(s)):
        words = [w for w in norm(nm).split(" ") if w]
        if not words or not (words[0][0].isalpha() or words[0][0] == "_"): continue
        out.append((re.compile(r"\s+".join(re.escape(w) for w in words) + r"(?![\w])(?!\s*\()", re.I), nm))
    return out

def tokenize(src, pats):
    src = unicodedata.normalize("NFC", src); toks = []; i = 0; n = len(src)
    while i < n:
        c = src[i]
        if c.isspace(): i += 1; continue
        m = NUM.match(src, i)
        if m:
            v = float(m.group())
            if not math.isfinite(v) or v >= 1e300: raise FormulaError("ERROR_OVERFLOW", "Số quá lớn trong công thức.")
            toks.append(("num", v)); i = m.end(); continue
        if c == '"':
            j = i + 1; buf = []
            while True:
                if j >= n: raise FormulaError("ERROR_SYNTAX", "Chuỗi chưa đóng dấu nháy kép.")
                if src[j] == '"':
                    if j + 1 < n and src[j + 1] == '"': buf.append('"'); j += 2; continue
                    break
                buf.append(src[j]); j += 1
            toks.append(("str", "".join(buf))); i = j + 1; continue
        if c == "[":
            j = src.find("]", i)
            if j < 0: raise FormulaError("ERROR_SYNTAX", "Thiếu dấu ] để đóng tên cột.")
            toks.append(("col", src[i + 1:j].strip())); i = j + 1; continue
        if src[i:i + 2] in (">=", "<=", "<>", "!="):
            toks.append(("op", "!=" if src[i:i + 2] in ("<>", "!=") else src[i:i + 2])); i += 2; continue
        if c in "+-*/%&()=<>,;":
            toks.append(("op", "," if c == ";" else c)); i += 1; continue
        if c.isalpha() or c == "_":
            hit = None
            for pat, orig in pats:
                m = pat.match(src, i)
                if m: hit = (m, orig); break
            if hit: toks.append(("col", hit[1])); i = hit[0].end(); continue
            m = IDENT.match(src, i); toks.append(("id", m.group())); i = m.end(); continue
        raise FormulaError("ERROR_SYNTAX", "Ký tự không hợp lệ trong công thức: %s" % c)
    return toks

class P:
    def __init__(s, toks): s.t, s.i, s.d = toks, 0, 0
    def peek(s): return s.t[s.i] if s.i < len(s.t) else ("end", None)
    def eat(s, kind=None, val=None):
        k = s.peek()
        if (kind and k[0] != kind) or (val is not None and k[1] != val):
            raise FormulaError("ERROR_SYNTAX", "Công thức sai cú pháp gần %s." % (repr(k[1]) if k[0] != "end" else "cuối công thức"))
        s.i += 1; return k
    def enter(s):
        s.d += 1
        if s.d > MAXDEPTH: raise FormulaError("ERROR_SYNTAX", "Công thức lồng nhau quá sâu.")
    def expr(s):
        s.enter(); a = s.add()
        while s.peek()[0] == "op" and s.peek()[1] in CMP:
            op = s.eat()[1]; a = ("bin", op, a, s.add())
        s.d -= 1; return a
    def add(s):
        a = s.mul()
        while s.peek()[0] == "op" and s.peek()[1] in ("+", "-", "&"):
            op = s.eat()[1]; a = ("bin", op, a, s.mul())
        return a
    def mul(s):
        a = s.unary()
        while s.peek()[0] == "op" and s.peek()[1] in ("*", "/", "%"):
            op = s.eat()[1]; a = ("bin", op, a, s.unary())
        return a
    def unary(s):
        if s.peek() == ("op", "-"):
            s.eat(); s.enter(); x = s.unary(); s.d -= 1; return ("neg", x)
        return s.prim()
    def prim(s):
        k, v = s.peek()
        if k in ("num", "str", "col"): s.eat(); return (k, v)
        if k == "op" and v == "(":
            s.eat(); e = s.expr(); s.eat("op", ")"); return e
        if k == "id":
            s.eat(); u = v.upper()
            if s.peek() != ("op", "("):
                if u in ("TRUE", "FALSE"): return ("bool", u == "TRUE")
                raise FormulaError("ERROR_COLUMN", 'Cột "%s" không tồn tại. Tên cột có dấu cách hãy đặt trong [ ].' % v)
            s.eat(); args = []
            if s.peek() != ("op", ")"):
                args.append(s.expr())
                while s.peek() == ("op", ","): s.eat(); args.append(s.expr())
            s.eat("op", ")"); return ("call", u, args)
        raise FormulaError("ERROR_SYNTAX", "Công thức sai cú pháp gần %s." % (repr(v) if k != "end" else "cuối công thức"))

def parse(src, pats):
    p = P(tokenize(src, pats))
    try: a = p.expr()
    except RecursionError: raise FormulaError("ERROR_SYNTAX", "Công thức quá phức tạp.")
    if p.peek()[0] != "end": raise FormulaError("ERROR_SYNTAX", "Công thức sai cú pháp gần %r." % (p.peek()[1],))
    return a

def analyze(ast, known):
    """Kiểm tra cột và hàm tồn tại, đúng số đối số; trả về danh sách cột được tham chiếu."""
    refs = []; stack = [(ast, 1)]
    while stack:
        n, d = stack.pop()
        if d > MAXAST: raise FormulaError("ERROR_SYNTAX", "Công thức quá phức tạp.")
        k = n[0]
        if k == "col":
            if norm(n[1]) not in known: raise FormulaError("ERROR_COLUMN", 'Cột "%s" không tồn tại.' % n[1])
            if n[1] not in refs: refs.append(n[1])
        elif k == "neg": stack.append((n[1], d + 1))
        elif k == "bin": stack += [(n[3], d + 1), (n[2], d + 1)]
        elif k == "call":
            if n[1] not in ARITY: raise FormulaError("ERROR_SYNTAX", "Hàm %s không tồn tại." % n[1])
            lo, hi = ARITY[n[1]]
            if not lo <= len(n[2]) <= hi: raise FormulaError("ERROR_SYNTAX", "Hàm %s nhận %s đối số, công thức đang có %d." % (n[1], str(lo) if lo == hi else "từ %d đến %s" % (lo, hi if hi < 99 else "nhiều"), len(n[2])))
            stack += [(a, d + 1) for a in reversed(n[2])]
    return refs

# ---------------- bộ tính chính ----------------
def clean(x):
    if not math.isfinite(x) or abs(x) >= 1e300: return Err("ERROR_OVERFLOW")
    return float("%.15g" % x)
def terr(v): return Err("ERROR_NULL" if v is None else "ERROR_TYPE")
def txt(v):
    if v is None: return ""
    if isinstance(v, bool): return "TRUE" if v else "FALSE"
    if isnum(v): return str(int(v)) if v == int(v) and abs(v) < 1e15 else format(v, ".12g")
    if isdate(v): return dstr(v)
    return v
def iarg(v, lo=None):
    if not isnum(v): return terr(v)
    if v != int(v): return Err("ERROR_TYPE")
    v = int(v)
    return Err("ERROR_TYPE") if lo is not None and v < lo else v
def adddays(d, n):
    if n != int(n): return Err("ERROR_TYPE")
    try: return d + dt.timedelta(days=int(n))
    except OverflowError: return Err("ERROR_DATE")

def cmpop(op, a, b):
    if a is None and b is None: a = b = ""
    if a is None: a = "" if isinstance(b, str) else None
    if b is None: b = "" if isinstance(a, str) else None
    if a is None or b is None: return Err("ERROR_NULL")
    if isinstance(a, str) and isinstance(b, str): a, b = a.casefold(), b.casefold()
    elif isnum(a) and isnum(b): pass
    elif isdate(a) and isdate(b): pass
    elif isinstance(a, bool) and isinstance(b, bool) and op in ("=", "!="): pass
    else: return Err("ERROR_TYPE")
    return {"=": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]

def fmod(a, b):
    """Chia lấy dư theo số thập phân (3 % 0.1 = 0, không phải 0.0999...), dấu theo số chia như Excel."""
    if abs(a / b) >= 1e15: return Err("ERROR_OVERFLOW")
    da, db = D(repr(a)), D(repr(b)); r = da % db
    if r != 0 and (r < 0) != (db < 0): r += db
    return clean(float(r))

def binop(op, a, b):
    for x in (a, b):
        if isinstance(x, Err): return x
    if op == "&": return txt(a) + txt(b)
    if op in CMP: return cmpop(op, a, b)
    if a is None or b is None: return Err("ERROR_NULL")
    if isnum(a) and isnum(b):
        if op == "+": return clean(a + b)
        if op == "-": return clean(a - b)
        if op == "*": return clean(a * b)
        if b == 0: return Err("ERROR_DIV_ZERO")
        return clean(a / b) if op == "/" else fmod(a, b)
    if op == "+" and isdate(a) and isnum(b): return adddays(a, b)
    if op == "+" and isnum(a) and isdate(b): return adddays(b, a)
    if op == "-" and isdate(a) and isnum(b): return adddays(a, -b)
    if op == "-" and isdate(a) and isdate(b): return float((a - b).days)
    return Err("ERROR_TYPE")

def _num1(fn):
    def g(v):
        return terr(v[0]) if not isnum(v[0]) else fn(v[0])
    return g
def _round(v):
    x = v[0]
    if not isnum(x): return terr(x)
    n = iarg(v[1]) if len(v) > 1 else 0
    if isinstance(n, Err): return n
    if not -15 <= n <= 15: return Err("ERROR_TYPE")
    if abs(x) >= 1e15 and n >= 0: return clean(x)
    return clean(float(D(repr(x)).quantize(D(1).scaleb(-n), rounding=ROUND_HALF_UP)))
def _agg(fn, empty):
    def g(v):
        xs = [x for x in v if x is not None]
        if any(not isnum(x) for x in xs): return Err("ERROR_TYPE")
        return empty if not xs else fn(xs)
    return g
def _power(v):
    x, y = v
    if not isnum(x): return terr(x)
    if not isnum(y): return terr(y)
    if x == 0 and y < 0: return Err("ERROR_DIV_ZERO")
    if x < 0 and y != int(y): return Err("ERROR_TYPE")
    try: return clean(float(x) ** float(y))
    except OverflowError: return Err("ERROR_OVERFLOW")
def _left(v):
    s = txt(v[0]); n = iarg(v[1], 0) if len(v) > 1 else 1
    return n if isinstance(n, Err) else s[:n]
def _right(v):
    s = txt(v[0]); n = iarg(v[1], 0) if len(v) > 1 else 1
    return n if isinstance(n, Err) else (s[len(s) - n:] if 0 < n < len(s) else ("" if n == 0 else s))
def _mid(v):
    s = txt(v[0]); a = iarg(v[1], 1); b = iarg(v[2], 0)
    for x in (a, b):
        if isinstance(x, Err): return x
    return s[a - 1:a - 1 + b]
def _replace(v):
    s = txt(v[0]); a = iarg(v[1], 1); b = iarg(v[2], 0)
    for x in (a, b):
        if isinstance(x, Err): return x
    return s[:a - 1] + txt(v[3]) + s[a - 1 + b:]
def _bools(fn):
    def g(v):
        for x in v:
            if not isinstance(x, bool): return terr(x)
        return fn(v)
    return g
def _dpart(f):
    def g(v): return terr(v[0]) if not isdate(v[0]) else float(f(v[0]))
    return g
FN = {"ABS": _num1(abs), "CEIL": _num1(lambda x: float(math.ceil(x))), "FLOOR": _num1(lambda x: float(math.floor(x))),
      "SQRT": _num1(lambda x: Err("ERROR_TYPE") if x < 0 else clean(math.sqrt(x))), "ROUND": _round, "POWER": _power,
      "MIN": _agg(lambda xs: min(xs), Err("ERROR_NULL")), "MAX": _agg(lambda xs: max(xs), Err("ERROR_NULL")),
      "SUM": _agg(lambda xs: clean(sum(xs)), 0.0), "AVERAGE": _agg(lambda xs: clean(sum(xs) / len(xs)), Err("ERROR_DIV_ZERO")),
      "CONCAT": lambda v: "".join(txt(x) for x in v), "LEFT": _left, "RIGHT": _right, "MID": _mid, "LEN": lambda v: float(len(txt(v[0]))),
      "TRIM": lambda v: " ".join(txt(v[0]).split()), "LOWER": lambda v: txt(v[0]).lower(), "UPPER": lambda v: txt(v[0]).upper(),
      "REPLACE": _replace, "SUBSTITUTE": lambda v: txt(v[0]) if txt(v[1]) == "" else txt(v[0]).replace(txt(v[1]), txt(v[2])),
      "AND": _bools(all), "OR": _bools(any), "NOT": _bools(lambda v: not v[0]),
      "YEAR": _dpart(lambda d: d.year), "MONTH": _dpart(lambda d: d.month), "DAY": _dpart(lambda d: d.day),
      "ISEMPTY": lambda v: v[0] is None or (isinstance(v[0], str) and not v[0].strip()),
      "ISNUMBER": lambda v: isnum(v[0]), "ISDATE": lambda v: isdate(v[0]),
      "CONTAINS": lambda v: txt(v[1]).casefold() in txt(v[0]).casefold(), "STARTSWITH": lambda v: txt(v[0]).casefold().startswith(txt(v[1]).casefold()),
      "ENDSWITH": lambda v: txt(v[0]).casefold().endswith(txt(v[1]).casefold())}

def ev(n, row):
    k = n[0]
    if k in ("num", "str", "bool", "date"): return n[1]
    if k == "col": return row(n[1])
    if k == "neg":
        x = ev(n[1], row)
        if isinstance(x, Err): return x
        return -x if isnum(x) else terr(x)
    if k == "bin": return binop(n[1], ev(n[2], row), ev(n[3], row))
    f, a = n[1], n[2]
    if f == "IF":
        c = ev(a[0], row)
        if isinstance(c, Err): return c
        if not isinstance(c, bool): return terr(c)
        return ev(a[1] if c else a[2], row)
    vals = [ev(x, row) for x in a]
    for v in vals:
        if isinstance(v, Err): return v
    return FN[f](vals)

# ---------------- dữ liệu cột có kiểu ----------------
AMB = re.compile(r"[+-]?\d{1,3}[.,]\d{3}")
_CUR = re.compile(r"\s|₫|đ|\$|€|%|VND|VNĐ", re.I)
VI_EV = [re.compile(p) for p in (r"[+-]?\d+,\d{1,2}", r"[+-]?\d{1,3}(?:\.\d{3})+,\d+", r"[+-]?\d{1,3}(?:\.\d{3}){2,}")]
EN_EV = [re.compile(p) for p in (r"[+-]?\d+\.\d{1,2}", r"[+-]?\d{1,3}(?:,\d{3})+\.\d+", r"[+-]?\d{1,3}(?:,\d{3}){2,}")]

def number_plan(strs, numfmt):
    """Giá trị mơ hồ như 1.234 hoặc 1,234 (là 1234 hay 1,234?). numfmt: 'vi' (1.234 = 1234), 'en' (1.234 = 1,234) hoặc 'auto'
    (suy ra từ các ô khác trong cột; không đủ bằng chứng thì KHÔNG tự chuyển). Trả về ({vị trí: số hoặc None}, cách đọc, số ô mơ hồ)."""
    st = [_CUR.sub("", s) for s in strs]; amb = [i for i, s in enumerate(st) if AMB.fullmatch(s)]
    if not amb: return {}, "none", 0
    loc = numfmt if numfmt in ("vi", "en") else None
    if loc is None:
        vi = any(p.fullmatch(s) for s in st for p in VI_EV); en = any(p.fullmatch(s) for s in st for p in EN_EV)
        loc = "vi" if vi and not en else "en" if en and not vi else None
    out = {}
    for i in amb:
        if loc is None: out[i] = None; continue
        core = st[i].lstrip("+-"); sep = "." if "." in core else ","; a, b = core.split(sep)
        v = float(a + b) if (sep == "." and loc == "vi") or (sep == "," and loc == "en") else float(a + "." + b)
        out[i] = -v if st[i].startswith("-") else v
    return out, loc or "unknown", len(amb)

def typed_column(vals, ctype, pn, pd, numfmt="auto"):
    """Ô trống -> None, số/ngày giữ nguyên kiểu. Chuỗi chỉ được đọc thành số/ngày khi cả cột được nhận diện là số/ngày;
    giá trị số mơ hồ không đủ bằng chứng thì giữ nguyên là chữ (báo ERROR_TYPE khi tính). Trả về (danh sách, thông tin)."""
    out = [None] * len(vals); idx = []
    for i, v in enumerate(vals):
        if v is None or (isinstance(v, str) and not v.strip()): continue
        if isinstance(v, bool): out[i] = v
        elif isinstance(v, (int, float)): out[i] = float(v)
        elif isinstance(v, dt.datetime): out[i] = v.date()
        elif isinstance(v, dt.date): out[i] = v
        elif isinstance(v, str): out[i] = v; idx.append(i)
        else: out[i] = str(v)
    info = {"bad": 0, "mixed": False, "amb": 0, "amb_unresolved": 0, "loc": "none"}
    if idx and ctype in ("number", "date"):
        strs = [out[i] for i in idx]; plan = {}
        if ctype == "number": plan, info["loc"], info["amb"] = number_plan(strs, numfmt)
        rest = [k for k in range(len(idx)) if k not in plan]
        for k, r in zip(rest, (pn if ctype == "number" else pd)([strs[k] for k in rest])):
            if r is not None: out[idx[k]] = float(r) if ctype == "number" else dt.date.fromordinal(int(r))
        for k, v in plan.items():
            if v is None: info["amb_unresolved"] += 1
            else: out[idx[k]] = v
        info["bad"] = sum(1 for i in idx if isinstance(out[i], str))
    elif ctype == "text": info["mixed"] = any(isinstance(v, float) for v in out) and any(isinstance(v, str) for v in out)
    return out, info

def cellval(v):
    if isinstance(v, Err): return v.code
    if v is None: return ""
    if isinstance(v, bool): return v
    if isnum(v): return int(v) if v == int(v) and abs(v) < 1e15 else v
    if isdate(v): return dt.datetime(v.year, v.month, v.day)
    return v

def _cycle(deps, nodes):
    cur = nodes[0]; seen = []
    while cur not in seen:
        seen.append(cur); cur = next(d for d in deps[cur] if d in nodes)
    return seen[seen.index(cur):] + [cur]

def _show(v):
    if v is None: return "(trống)"
    if isinstance(v, Err): return v.code
    return v if isinstance(v, str) else str(txt(v))

def derive(n, names0, ops, typed_fn):
    """Tính các cột công thức. n: số dòng dữ liệu; names0: tên mọi cột hiện có; typed_fn(c): danh sách giá trị có kiểu của cột c.
    Trả về errors (nghiêm trọng) hoặc cols, order, stats, warnings, errlog (báo cáo lỗi từng ô)."""
    errors, warnings = [], []
    def bad(code, msg, o=None): errors.append({"code": code, "message": msg, "op_id": o.get("id") if o else None})
    en = [o for o in ops if o.get("enabled", True)]
    if len(en) > MAXOPS: bad("TOO_MANY_OPS", "Tối đa %d công thức đang bật." % MAXOPS)
    targets = []
    for o in en:
        t = str(o.get("target", "")).strip(); targets.append(t)
        if o.get("type", "FORMULA") != "FORMULA": bad("UNSUPPORTED_OP", "Loại biến đổi %s chưa được hỗ trợ." % o.get("type"), o)
        if not t or len(t) > 60 or re.search(r'[\[\]"]', t): bad("INVALID_NAME", "Tên cột mới không hợp lệ (1 đến 60 ký tự, không chứa [ ] hoặc dấu nháy kép).", o)
    seen = {norm(x) for x in names0}
    for o, t in zip(en, targets):
        if norm(t) in seen: bad("DUPLICATE_COLUMN", 'Tên cột "%s" đã tồn tại.' % t, o)
        seen.add(norm(t))
    if errors: return {"errors": errors}
    pats = _pats(list(names0) + targets); asts, refs = {}, {}
    for o, t in zip(en, targets):
        try:
            src = str(o.get("expression", ""))
            if not src.strip(): raise FormulaError("ERROR_SYNTAX", "Công thức đang trống.")
            if len(src) > MAXLEN: raise FormulaError("ERROR_SYNTAX", "Công thức quá dài (tối đa %d ký tự)." % MAXLEN)
            asts[o["id"]] = parse(src, pats); refs[o["id"]] = analyze(asts[o["id"]], seen)
        except FormulaError as e: bad(e.code, "%s: %s" % (t, e.msg), o)
    if errors: return {"errors": errors}
    tmap = {norm(t): o["id"] for o, t in zip(en, targets)}; label = {o["id"]: t for o, t in zip(en, targets)}
    deps = {o["id"]: {tmap[norm(r)] for r in refs[o["id"]] if norm(r) in tmap} for o in en}
    order, left = [], [o["id"] for o in en]
    while left:  # thứ tự tính theo phụ thuộc: cột nào cần cột nào thì tính cột đó trước
        pick = next((x for x in left if all(d in order for d in deps[x])), None)
        if pick is None:
            bad("CIRCULAR_DEPENDENCY", "Phát hiện công thức tham chiếu vòng: " + " → ".join(label[x] for x in _cycle(deps, left)))
            return {"errors": errors}
        order.append(pick); left.remove(pick)
    srcT, res, stats, elog = {}, {}, {}, []
    byname = {}
    for c in range(len(names0) - 1, -1, -1): byname[norm(names0[c])] = c
    for nm, k in Counter(norm(x) for x in names0).items():
        if k > 1: warnings.append('Có %d cột trùng tên "%s": công thức sẽ dùng cột đầu tiên.' % (k, nm))
    def getcol(key):
        if key in tmap: return res[tmap[key]]
        c = byname[key]
        if c not in srcT: srcT[c] = typed_fn(c)
        return srcT[c]
    for oid in order:
        ast = asts[oid]; L = {r: getcol(norm(r)) for r in refs[oid]}; out = []; cnt = Counter(); logged = 0
        try:
            for i in range(n):
                v = ev(ast, lambda nm, i=i: L[nm][i])
                if isinstance(v, Err):
                    cnt[v.code] += 1
                    if logged < 100:
                        logged += 1; elog.append({"op_id": oid, "target": label[oid], "row": i, "code": v.code, "inputs": "; ".join("%s = %s" % (r_, _show(L[r_][i])) for r_ in refs[oid])})
                out.append(v)
        except RecursionError:
            bad("ERROR_SYNTAX", "%s: Công thức quá phức tạp để tính." % label[oid]); return {"errors": errors}
        res[oid] = out; stats[oid] = {"errors": dict(cnt), "rows": n}
    cols = [{"id": o["id"], "target": t, "values": [cellval(v) for v in res[o["id"]]], "typed": [v.code if isinstance(v, Err) else v for v in res[o["id"]]],
             "date": any(isdate(v) for v in res[o["id"]]), "ast": asts[o["id"]]} for o, t in zip(en, targets)]
    return {"errors": [], "warnings": warnings, "cols": cols, "order": order, "stats": stats, "refs": refs, "errlog": elog}

# ---------------- giao diện hàm nội bộ (mục 50 của lộ trình) ----------------
def parse_formula(expression, names):
    """Chuỗi công thức -> cây cú pháp. names: danh sách tên cột. Ném FormulaError nếu sai cú pháp."""
    return parse(expression, _pats(names))
def validate_formula(ast, names):
    """Kiểm tra cột và hàm tồn tại, đủ đối số. Trả về danh sách cột được dùng."""
    return analyze(ast, {norm(x) for x in names})
def evaluate_formula(ast, row):
    """Tính một dòng. row: hàm (tên cột) -> giá trị có kiểu. Trả về (giá trị, mã lỗi hoặc None, cảnh báo hoặc None)."""
    v = ev(ast, row)
    return (None, v.code, None) if isinstance(v, Err) else (v, None, None)
def evaluate_batch(ast, dataset):
    """dataset: {tên cột: danh sách giá trị có kiểu}. Trả về danh sách (giá trị, mã lỗi, cảnh báo) cho từng dòng."""
    n = len(next(iter(dataset.values()))) if dataset else 0
    return [evaluate_formula(ast, lambda nm, i=i: dataset[nm][i]) for i in range(n)]

# ---------------- bộ tính độc lập (kiểm tra lại) ----------------
def iclean(r):
    if abs(r) >= D("1e300"): raise Raise("ERROR_OVERFLOW")
    return D(format(r, ".15g"))
def itxt(v):
    if v is None: return ""
    if isinstance(v, bool): return "TRUE" if v else "FALSE"
    if isinstance(v, D): return str(int(v)) if v == v.to_integral_value() and abs(v) < D("1e15") else format(float(v), ".12g")
    if isinstance(v, dt.date): return dstr(v)
    return v
def _in(x):
    if isinstance(x, D): return x
    raise Raise("ERROR_NULL" if x is None else "ERROR_TYPE")
def _ii(x, lo=None):
    x = _in(x)
    if x != x.to_integral_value(): raise Raise("ERROR_TYPE")
    x = int(x)
    if lo is not None and x < lo: raise Raise("ERROR_TYPE")
    return x
def _xs(v):
    xs = [x for x in v if x is not None]
    if any(not isinstance(x, D) for x in xs): raise Raise("ERROR_TYPE")
    return xs
def _iround(v):
    x = _in(v[0]); n = _ii(v[1]) if len(v) > 1 else 0
    if not -15 <= n <= 15: raise Raise("ERROR_TYPE")
    if abs(x) >= D("1e15") and n >= 0: return iclean(x)
    return iclean(x.quantize(D(1).scaleb(-n), rounding=ROUND_HALF_UP))
def _ipower(v):
    x, y = _in(v[0]), _in(v[1])
    if y == 0: return D(1)
    if x == 0 and y < 0: raise Raise("ERROR_DIV_ZERO")
    if x < 0 and y != y.to_integral_value(): raise Raise("ERROR_TYPE")
    try: return iclean(x ** y)
    except ArithmeticError: raise Raise("ERROR_OVERFLOW")
def _bl(v, fn):
    for x in v:
        if not isinstance(x, bool): raise Raise("ERROR_NULL" if x is None else "ERROR_TYPE")
    return fn(v)
def _dp(v, f):
    if not isinstance(v[0], dt.date): raise Raise("ERROR_NULL" if v[0] is None else "ERROR_TYPE")
    return D(f(v[0]))
def _isqrt(v):
    x = _in(v[0])
    if x < 0: raise Raise("ERROR_TYPE")
    return iclean(x.sqrt())
def _imid(v):
    s = itxt(v[0]); a = _ii(v[1], 1); b = _ii(v[2], 0); return s[a - 1:a - 1 + b]
def _irep(v):
    s = itxt(v[0]); a = _ii(v[1], 1); b = _ii(v[2], 0); return s[:a - 1] + itxt(v[3]) + s[a - 1 + b:]
def _ileft(v):
    s = itxt(v[0]); n = _ii(v[1], 0) if len(v) > 1 else 1; return s[:n]
def _iright(v):
    s = itxt(v[0]); n = _ii(v[1], 0) if len(v) > 1 else 1; return "" if n == 0 else s[max(0, len(s) - n):]
def _imm(fn, empty):
    def g(v):
        xs = _xs(v)
        if not xs:
            if isinstance(empty, str): raise Raise(empty)
            return empty
        return fn(xs)
    return g
IFN = {"ABS": lambda v: abs(_in(v[0])), "CEIL": lambda v: _in(v[0]).to_integral_value(rounding=ROUND_CEILING),
       "FLOOR": lambda v: _in(v[0]).to_integral_value(rounding=ROUND_FLOOR), "SQRT": _isqrt, "ROUND": _iround, "POWER": _ipower,
       "MIN": _imm(min, "ERROR_NULL"), "MAX": _imm(max, "ERROR_NULL"), "SUM": _imm(lambda xs: iclean(sum(xs, D(0))), D(0)),
       "AVERAGE": _imm(lambda xs: iclean(sum(xs, D(0)) / len(xs)), "ERROR_DIV_ZERO"),
       "CONCAT": lambda v: "".join(itxt(x) for x in v), "LEFT": _ileft, "RIGHT": _iright, "MID": _imid,
       "LEN": lambda v: D(len(itxt(v[0]))), "TRIM": lambda v: " ".join(itxt(v[0]).split()), "LOWER": lambda v: itxt(v[0]).lower(),
       "UPPER": lambda v: itxt(v[0]).upper(), "REPLACE": _irep,
       "SUBSTITUTE": lambda v: itxt(v[0]) if itxt(v[1]) == "" else itxt(v[0]).replace(itxt(v[1]), itxt(v[2])),
       "AND": lambda v: _bl(v, all), "OR": lambda v: _bl(v, any), "NOT": lambda v: _bl(v, lambda x: not x[0]),
       "YEAR": lambda v: _dp(v, lambda d: d.year), "MONTH": lambda v: _dp(v, lambda d: d.month), "DAY": lambda v: _dp(v, lambda d: d.day),
       "ISEMPTY": lambda v: v[0] is None or (isinstance(v[0], str) and not v[0].strip()),
       "ISNUMBER": lambda v: isinstance(v[0], D), "ISDATE": lambda v: isinstance(v[0], dt.date),
       "CONTAINS": lambda v: itxt(v[1]).casefold() in itxt(v[0]).casefold(), "STARTSWITH": lambda v: itxt(v[0]).casefold().startswith(itxt(v[1]).casefold()),
       "ENDSWITH": lambda v: itxt(v[0]).casefold().endswith(itxt(v[1]).casefold())}

def icmp(op, a, b):
    if a is None and b is None: a = b = ""
    if a is None and isinstance(b, str): a = ""
    if b is None and isinstance(a, str): b = ""
    if a is None or b is None: raise Raise("ERROR_NULL")
    if isinstance(a, str) and isinstance(b, str): a, b = a.casefold(), b.casefold()
    elif not ((isinstance(a, D) and isinstance(b, D)) or (isinstance(a, dt.date) and isinstance(b, dt.date)) or
              (isinstance(a, bool) and isinstance(b, bool) and op in ("=", "!="))):
        raise Raise("ERROR_TYPE")
    return {"=": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]

def iadd(d, n):
    if n != n.to_integral_value(): raise Raise("ERROR_TYPE")
    try: return d + dt.timedelta(days=int(n))
    except OverflowError: raise Raise("ERROR_DATE")

def ibin(op, a, b):
    if op == "&": return itxt(a) + itxt(b)
    if op in CMP: return icmp(op, a, b)
    if a is None or b is None: raise Raise("ERROR_NULL")
    na, nb = isinstance(a, D), isinstance(b, D)
    if na and nb:
        if op == "+": return iclean(a + b)
        if op == "-": return iclean(a - b)
        if op == "*": return iclean(a * b)
        if b == 0: raise Raise("ERROR_DIV_ZERO")
        if op == "/": return iclean(a / b)
        q = a / b
        if abs(q) >= D(10) ** 15: raise Raise("ERROR_OVERFLOW")
        return iclean(a - b * q.to_integral_value(rounding=ROUND_FLOOR))
    da, db = isinstance(a, dt.date), isinstance(b, dt.date)
    if op == "+" and da and nb: return iadd(a, b)
    if op == "+" and na and db: return iadd(b, a)
    if op == "-" and da and nb: return iadd(a, -b)
    if op == "-" and da and db: return D((a - b).days)
    raise Raise("ERROR_TYPE")

def ieval(n, get):
    k = n[0]
    if k == "num": return D(repr(n[1]))
    if k in ("str", "bool", "date"): return n[1]
    if k == "col": return get(n[1])
    if k == "neg":
        x = ieval(n[1], get)
        if isinstance(x, D): return -x
        raise Raise("ERROR_NULL" if x is None else "ERROR_TYPE")
    if k == "bin": return ibin(n[1], ieval(n[2], get), ieval(n[3], get))
    f, a = n[1], n[2]
    if f == "IF":
        c = ieval(a[0], get)
        if not isinstance(c, bool): raise Raise("ERROR_NULL" if c is None else "ERROR_TYPE")
        return ieval(a[1] if c else a[2], get)
    return IFN[f]([ieval(x, get) for x in a])

def ityped(v, ctype, to_num, to_date, blank):
    if blank(v): return None
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return D(repr(float(v)))
    if isinstance(v, dt.datetime): return v.date()
    if isinstance(v, dt.date): return v
    if isinstance(v, str):
        if ctype == "number":
            x = to_num(v)
            if x is not None: return D(repr(x))
        if ctype == "date":
            o = to_date(v)
            if o is not None: return dt.date.fromordinal(int(o))
        return v
    return str(v)

def same(e, g):
    if isinstance(e, bool): return g is e or g == ("TRUE" if e else "FALSE")
    if isinstance(e, D):
        if isinstance(g, bool) or g is None: return False
        try: x = float(g)
        except (TypeError, ValueError): return False
        return abs(x - float(e)) <= max(1e-9, 1e-9 * abs(float(e)))
    if isinstance(e, dt.date):
        if isinstance(g, dt.datetime): return g.date() == e
        return g == e if isinstance(g, dt.date) else g == dstr(e)
    if e is None: return g in (None, "")
    return (g if g is not None else "") == e

def inumber_plan(strs, numfmt):
    """Bản cài độc lập của number_plan (dùng Decimal)."""
    cl = [re.sub(r"\s|₫|đ|\$|€|%|VND|VNĐ", "", s, flags=re.I) for s in strs]
    amb = {}
    for i, s in enumerate(cl):
        m = re.fullmatch(r"([+-]?)(\d{1,3})([.,])(\d{3})", s)
        if m: amb[i] = m.groups()
    if not amb: return {}
    if numfmt in ("vi", "en"): loc = numfmt
    else:
        vi = en = False
        for s in cl:
            if re.fullmatch(r"[+-]?\d+,\d{1,2}", s) or re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+,\d+", s) or re.fullmatch(r"[+-]?\d{1,3}(\.\d{3}){2,}", s): vi = True
            if re.fullmatch(r"[+-]?\d+\.\d{1,2}", s) or re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+\.\d+", s) or re.fullmatch(r"[+-]?\d{1,3}(,\d{3}){2,}", s): en = True
        loc = "vi" if vi and not en else ("en" if en and not vi else None)
    out = {}
    for i, (sign, a, sep, b) in amb.items():
        if loc is None: out[i] = None; continue
        v = D(a + b) if (loc == "vi") == (sep == ".") else D(a + "." + b)
        out[i] = -v if sign == "-" else v
    return out

def ityped_col(vals, ctype, numfmt, to_num, to_date, blank):
    out = [ityped(v, None, to_num, to_date, blank) for v in vals]
    idx = [i for i, v in enumerate(vals) if isinstance(v, str) and not blank(v)]
    if ctype == "number" and idx:
        plan = inumber_plan([vals[i] for i in idx], numfmt)
        for k, i in enumerate(idx):
            if k in plan: out[i] = plan[k] if plan[k] is not None else vals[i]
            else:
                x = to_num(vals[i]); out[i] = D(repr(x)) if x is not None else vals[i]
    elif ctype == "date":
        for i in idx:
            o = to_date(vals[i]); out[i] = dt.date.fromordinal(int(o)) if o is not None else vals[i]
    return out
