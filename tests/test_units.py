"""Kiểm thử đơn vị (mục 63.1): đọc số, đọc ngày, thứ tự tiếng Việt, số trong chữ, phát hiện trùng, chuẩn hóa khóa sắp xếp."""
import os, sys, io, random, datetime as dt
os.environ["APP_PASSWORD"] = "t"; sys.path.insert(0, ".")
import openpyxl, server as S
from engine import text_keys, nat
fails = []
def chk(n, got, exp=True):
    if got != exp: fails.append((n, got, exp))
# đọc số (mục 3.6)
for s, v in [("1234", 1234), ("1,234.5", 1234.5), ("1.234,5", 1234.5), ("1000₫", 1000), ("1.000.000 VND", 1000000), ("10%", 10), ("12,5", 12.5), ("-3,5", -3.5), ("1.234", 1234), ("abc", None), ("", None), ("1.2.3", None)]:
    chk("to_num(%r)" % s, S.to_num(s), v if v is None else float(v))
for s, y in [("31/01/2026", (2026, 1, 31)), ("2026-02-28", (2026, 2, 28)), ("29/02/2024", (2024, 2, 29)), ("1/3/2026", (2026, 3, 1))]:
    o = S.to_date(s); chk("to_date(%r)" % s, dt.date.fromordinal(int(o)).timetuple()[:3], y)
for s in ["31/02/2024", "29/02/2023", "abc", "", "13/13/2026", "2026-13-01", "1/1/0000"]: chk("to_date(%r) không hợp lệ" % s, S.to_date(s), None)
# số trong chữ và thứ tự tiếng Việt (khóa sắp xếp)
def order(names): return sorted(names, key=lambda x: tuple(nat(k) for k in text_keys(x)))
chk("KH2 trước KH10 trước KH100", order(["KH10", "KH2", "KH100", "KH1"]), ["KH1", "KH2", "KH10", "KH100"])
chk("thứ tự tiếng Việt: đ sau d, trước e", order(["Em", "Đức", "Dũng", "Ăn", "An", "Âu", "Ba", "bình"]), ["An", "Ăn", "Âu", "Ba", "bình", "Dũng", "Đức", "Em"])
# sắp xếp qua máy chủ: bộ xử lý C++ (nếu có) và bản Python dự phòng phải cho cùng kết quả, ô trống luôn cuối
H = {"X-Requested-With": "datadesk"}; c = S.app.test_client(); c.post("/login", json={"password": "t"})
rows = [["Tên", "Mã", "Số"], ["Đức", "KH10", 3], ["An", "KH2", None], ["Dũng", "KH25", 1], ["Ăn", "KH100", 2], ["", "KH7", 5], ["Em", "KH3", "abc"], ["Âu", "KH1", 4]]
wb = openpyxl.Workbook(); ws = wb.active
for r in rows: ws.append(r)
b = io.BytesIO(); wb.save(b); b.seek(0); sid = c.post("/api/analyze", data={"file": (b, "u.xlsx")}, content_type="multipart/form-data", headers=H).get_json()["id"]
def sorted_col(col, direction="asc", native=True, typ="auto"):
    S.E.native = native and S.E.lib is not None
    r = c.post("/api/process", json=dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": col, "dir": direction, "type": typ}]), headers=H).get_json(); S.E.native = S.E.lib is not None
    return [x[col] for x in r["preview"][1:]], r["ok"]
for native in ([True, False] if S.E.lib is not None else [False]):
    tag = "C++" if native else "Python"
    v, ok = sorted_col(0, "asc", native); chk("sắp theo tên (%s): đúng thứ tự, ô trống cuối" % tag, v, ["An", "Ăn", "Âu", "Dũng", "Đức", "Em", ""]); chk("kiểm tra độc lập đạt (%s)" % tag, ok)
    v, _ = sorted_col(1, "asc", native); chk("sắp theo mã (%s): KH2 trước KH10" % tag, v, ["KH1", "KH2", "KH3", "KH7", "KH10", "KH25", "KH100"])
    v, _ = sorted_col(2, "desc", native, "number"); chk("sắp số giảm dần (%s): ô trống và ô không đọc được cuối, vẫn giữ nguyên" % tag, [str(x) for x in v], ["5", "4", "3", "2", "1", "", "abc"])
# phát hiện trùng: C++ và Python giống nhau
if S.E.lib is not None:
    rnd = random.Random(2); keys = [rnd.choice(["a", "b", "c", "dd", None, "é", "e"]) for _ in range(500)]; got = S.E.dups(keys)
    from collections import Counter
    cnt = Counter(k for k in keys if k is not None); chk("phát hiện trùng C++ == Python", [bool(x) for x in got], [k is not None and cnt[k] > 1 for k in keys])
print("ĐƠN VỊ: %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:12]]
sys.exit(1 if fails else 0)
