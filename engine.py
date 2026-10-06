"""Cầu nối Python <-> C++ qua ctypes. Chưa biên dịch C++ thì native=False và server dùng bản Python dự phòng."""
import ctypes, os, re, sys, unicodedata
_D = os.path.dirname(os.path.abspath(__file__))
C = ctypes

def nat(s):
    return [(0, int(x), "") if x[0] in "0123456789" else (1, 0, x) for x in re.split(r"([0-9]+)", s) if x != ""]

def text_keys(v):
    """Khóa sắp xếp tiếng Việt: khóa chính bỏ dấu (đ đứng sau d), khóa phụ giữ dấu."""
    s = unicodedata.normalize("NFD", str(v)).casefold()
    return "".join(c for c in s if not unicodedata.combining(c)).replace("đ", "d{"), s

def _strs(L):
    return (C.c_char_p * len(L))(*[(x or "").encode("utf-8", "replace") for x in L])

class Engine:
    def __init__(self):
        name = {"win32": "ddengine.dll", "darwin": "libddengine.dylib"}.get(sys.platform, "libddengine.so")
        try:
            self.lib = C.CDLL(os.path.join(_D, name)); L = self.lib; P = C.c_void_p
            L.dd_parse.argtypes = [C.c_int, P, C.c_int, P, P]
            L.dd_sort.argtypes = [C.c_int, C.c_int, P, P, P, P, P, P, P]
            L.dd_dups.argtypes = [C.c_int, P, P, P]
            L.dd_contains.argtypes = [C.c_int, P, C.c_char_p, P]
            L.dd_cmp.argtypes = [C.c_int, P, P, C.c_int, C.c_double, P]
            self.native = L.dd_version() == 2
        except (OSError, AttributeError):
            self.lib, self.native = None, False

    def parse_col(self, vals, mode, pyfn):
        """mode 'num' hoặc 'date'. Chuỗi do C++ đọc, giá trị khác kiểu chuỗi do pyfn đọc."""
        if not self.native: return [pyfn(v) for v in vals]
        out = [None if isinstance(v, str) else pyfn(v) for v in vals]
        idx = [i for i, v in enumerate(vals) if isinstance(v, str)]
        if idx:
            n = len(idx); o = (C.c_double * n)(); ok = (C.c_ubyte * n)()
            self.lib.dd_parse(n, _strs([vals[i] for i in idx]), 0 if mode == "num" else 1, o, ok)
            for j, i in enumerate(idx): out[i] = o[j] if ok[j] else None
        return [None if (x is None or x != x) else x for x in out]

    def sort(self, body, levels):
        n, k = len(body), len(levels)
        kind = (C.c_int * k)(*[1 if L[2] == "text" else 0 for L in levels])
        desc = (C.c_int * k)(*[1 if L[1] else 0 for L in levels])
        num = (C.c_double * (n * k))(); ok = (C.c_ubyte * (n * k))()
        pk = (C.c_char_p * (n * k))(); sk = (C.c_char_p * (n * k))()
        for j, (ks, _, ty, strs) in enumerate(levels):
            for p, i in enumerate(body):
                o = j * n + p
                if ty == "text":
                    v = strs[i]
                    if v is not None:
                        pk[o] = v[0].encode("utf-8", "replace"); sk[o] = v[1].encode("utf-8", "replace"); ok[o] = 1
                elif ks[i] is not None:
                    num[o] = ks[i]; ok[o] = 1
        out = (C.c_int * n)()
        self.lib.dd_sort(n, k, kind, desc, num, ok, pk, sk, out)
        return [body[x] for x in out]

    def dups(self, keys):
        n = len(keys); ok = (C.c_ubyte * n)(*[0 if k is None else 1 for k in keys]); out = (C.c_ubyte * n)()
        self.lib.dd_dups(n, _strs(keys), ok, out); return list(out)

    def contains(self, hay, needle):
        n = len(hay); out = (C.c_ubyte * n)()
        self.lib.dd_contains(n, _strs(hay), needle.encode("utf-8", "replace"), out); return list(out)

    def cmp_num(self, vals, op, y):
        n = len(vals); v = (C.c_double * n)(*[0.0 if x is None else x for x in vals])
        ok = (C.c_ubyte * n)(*[0 if x is None else 1 for x in vals]); out = (C.c_ubyte * n)()
        self.lib.dd_cmp(n, v, ok, 0 if op == "gt" else 1, y, out); return list(out)
