import os, sys, random, datetime as dt, time
os.environ["APP_PASSWORD"] = "t"; sys.path.insert(0, ".")
import formula as F, server as S
D = dt.date
pn = lambda L: S.E.parse_col(L, "num", S.to_num); pd = lambda L: S.E.parse_col(L, "date", S.to_date)
def derive(rows, ops):
    names0 = [str(x) for x in rows[0]]; types = [S.detect([r[c] for r in rows[1:]]) for c in range(len(names0))]
    return F.derive(rows, names0, ops, types, pn, pd), names0, types
def op(i, target, expr, en=True): return {"id": "rule_%03d" % i, "type": "FORMULA", "target": target, "expression": expr, "enabled": en}
H = ["Số lượng", "Đơn giá", "Điểm", "Tên", "Họ", "Ngày", "Ghi chú"]
ROWS = [H, [5, 20000, 4, "An", "Nguyễn", dt.datetime(2026, 1, 31), "x"], [10, 25000, 6, "Bình", "Trần", dt.datetime(2026, 2, 28), ""],
        [0, 1000, 9, "an", "Lê", None, None], [None, 5, 8.5, "Đức", "Đặng", dt.datetime(2024, 2, 29), "abc"]]
fails = []
def chk(name, got, exp):
    if got != exp: fails.append((name, got, exp))
def val(expr, extra=None, rows=ROWS):
    d, _, _ = derive(rows, (extra or []) + [op(9, "R", expr)])
    if d["errors"]: return "ERR:" + d["errors"][0]["code"] + ":" + d["errors"][0]["message"]
    c = next(c for c in d["cols"] if c["target"] == "R"); return c["values"]
def code(expr, **k):
    v = val(expr, **k); return v.split(":")[1] if isinstance(v, str) else v
chk("nhân tên bare", val("Số lượng * Đơn giá")[:3], [100000, 250000, 0]); chk("nhân null", val("Số lượng * Đơn giá")[3], "ERROR_NULL")
chk("nhân ngoặc vuông + hoa thường", val("[số lượng]*[ĐƠN GIÁ]")[:2], [100000, 250000])
chk("ưu tiên", val("2+3*4")[0], 14); chk("ngoặc", val("(2+3)*4")[0], 20); chk("âm", val("-2+5")[0], 3); chk("mod", val("10 % 3")[0], 1); chk("mod âm", val("-7 % 3")[0], 2)
chk("chia", val("7/2")[0], 3.5); chk("nhiễu số thực", val("0.1+0.2 = 0.3")[0], True); chk("so sánh chuỗi không phân biệt hoa thường", val('IF([Tên]="an","x","y")'), ["x", "y", "x", "y"])
chk("IF lồng", val('IF(Điểm<5,"Yếu",IF(Điểm<8,"Khá","Giỏi"))'), ["Yếu", "Khá", "Giỏi", "Giỏi"])
chk("IF lười", val("IF([Số lượng]=0, 0, 100/[Số lượng])")[:3], [20, 10, 0])
chk("chia 0", val("100/[Số lượng]")[2], "ERROR_DIV_ZERO"); chk("kiểu", val("[Tên]*2")[0], "ERROR_TYPE")
chk("cột không tồn tại", code("[Giá]*2"), "ERROR_COLUMN"); chk("tên trần không tồn tại", code("abc + 1"), "ERROR_COLUMN")
for e in ["FOO(1)", "2 +", "(1+2", '"abc', "1 2", "ROUND()", "IF(1,2)", "1.5.2", "@"]: chk("cú pháp " + e, code(e), "ERROR_SYNTAX")
d, _, _ = derive(ROWS, [op(1, "A", "B+1"), op(2, "B", "A+1")]); chk("vòng", d["errors"][0]["code"], "CIRCULAR_DEPENDENCY")
d, _, _ = derive(ROWS, [op(1, "A", "A+1")]); chk("tự tham chiếu", d["errors"][0]["code"], "CIRCULAR_DEPENDENCY")
d, _, _ = derive(ROWS, [op(1, "D", "C*2"), op(2, "C", "[Số lượng]+[Điểm]")]); chk("thứ tự phụ thuộc", [c["target"] for c in d["cols"]], ["D", "C"]); chk("giá trị phụ thuộc", d["cols"][0]["values"][:3], [18, 32, 18])
d, _, _ = derive(ROWS, [op(1, "C", "[Điểm]+1", en=False), op(2, "D", "C*2")]); chk("phụ thuộc cột đã tắt", d["errors"][0]["code"], "ERROR_COLUMN")
d, _, _ = derive(ROWS, [op(1, "Điểm", "1")]); chk("trùng tên", d["errors"][0]["code"], "DUPLICATE_COLUMN")
d, _, _ = derive(ROWS, [op(1, "a[b]", "1")]); chk("tên sai", d["errors"][0]["code"], "INVALID_NAME")
chk("ngày +30", val("[Ngày]+30")[:2], [dt.datetime(2026, 3, 2), dt.datetime(2026, 3, 30)]); chk("ngày - ngày", val("[Ngày]-[Ngày]")[0], 0)
chk("năm tháng ngày", [val(f"{f}([Ngày])")[0] for f in ("YEAR", "MONTH", "DAY")], [2026, 1, 31]); chk("ngày nhuận", val("[Ngày]+1")[3], dt.datetime(2024, 3, 1))
chk("ngày rỗng", val("YEAR([Ngày])")[2], "ERROR_NULL"); chk("ngày kiểu", val("YEAR([Tên])")[0], "ERROR_TYPE"); chk("ngày tràn", val("[Ngày]+99999999"), ["ERROR_DATE"] * 2 + ["ERROR_NULL", "ERROR_DATE"])
chk("CONCAT", val('CONCAT([Họ]," ",[Tên])')[:2], ["Nguyễn An", "Trần Bình"]); chk("&", val('[Họ] & "-" & [Số lượng]')[0], "Nguyễn-5")
chk("ROUND nửa lên", [val(f"ROUND({a})")[0] for a in ("2.5", "-2.5", "0.5")], [3, -3, 1]); chk("ROUND 2", val("ROUND(0.125,2)")[0], 0.13); chk("ROUND âm", val("ROUND(1234.5,-2)")[0], 1200)
chk("tràn POWER", val("POWER(10,400)")[0], "ERROR_OVERFLOW"); chk("tràn nhân", val("99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999*99999999999999999999")[0], "ERROR_OVERFLOW")
chk("SQRT", [val("SQRT(16)")[0], val("SQRT(-1)")[0]], [4, "ERROR_TYPE"]); chk("POWER", val("POWER(2,10)")[0], 1024); chk("POWER âm lẻ", val("POWER(-8,0.5)")[0], "ERROR_TYPE"); chk("0^-1", val("POWER(0,-1)")[0], "ERROR_DIV_ZERO")
chk("tổng", [val("SUM([Số lượng],[Điểm],1)")[3], val("AVERAGE([Số lượng],[Điểm])")[3], val("MIN([Số lượng],[Điểm])")[0], val("MAX([Số lượng],[Điểm])")[0]], [9.5, 8.5, 4, 5])
chk("chuỗi", [val(f)[0] for f in ('LEFT("abcdef",2)', 'RIGHT("abcdef",2)', 'MID("abcdef",2,3)', 'LEN("abc")', 'TRIM("  a   b ")', 'UPPER("aB")', 'LOWER("aB")', 'SUBSTITUTE("a-b-c","-","+")', 'REPLACE("abcdef",2,3,"X")')], ["ab", "ef", "bcd", 3, "a b", "AB", "ab", "a+b+c", "aXef"])
chk("ISEMPTY", val("ISEMPTY([Ghi chú])"), [False, True, True, False]); chk("AND OR NOT", [val(e)[0] for e in ("AND(1=1,2=2)", "OR(1=2,2=2)", "NOT(1=1)")], [True, True, False])
chk("hằng bool", val("IF(TRUE,1,2)")[0], 1)
for e in ["__import__('os').system('id')", 'open("x")', "[a].__class__", 'exec("1")', "1; DROP TABLE x", "`ls`", "${x}"]: chk("tiêm mã " + e, code(e), code(e) if code(e) in ("ERROR_SYNTAX", "ERROR_COLUMN") else "KHÔNG AN TOÀN")
chk("quá dài", code("1+" * 600 + "1"), "ERROR_SYNTAX"); chk("lồng sâu", code("(" * 200 + "1" + ")" * 200), "ERROR_SYNTAX"); chk("dấu trừ chuỗi", code("-" * 500 + "1"), "ERROR_SYNTAX")
chk("nhiều số hạng", val("+".join(["1"] * 300))[0], 300); chk("số quá lớn", code("9" * 400), "ERROR_OVERFLOW"); chk("trống", code("   "), "ERROR_SYNTAX")
# số trong cột văn bản không bị ép kiểu âm thầm
T2 = [["A", "B"], ["12", "x"], ["30", "y"], ["abc", "z"], ["40", "w"], ["50", "v"], ["60", "u"], ["70", "t"], ["80", "s"], ["90", "r"], ["100", "q"], ["110", "p"]]
d, _, ty = derive(T2, [op(1, "R", "A*2")]); chk("cột số có ô chữ", [d["cols"][0]["values"][0], d["cols"][0]["values"][2]], [24, "ERROR_TYPE"]); chk("cảnh báo ô không đọc được", len(d["warnings"]), 1)
print("UNIT: %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:15]]

# ---------- so sánh hai bộ tính trên 4000 công thức ngẫu nhiên ----------
rnd = random.Random(11)
def mkrows(n):
    rows = [["N1", "N2", "T", "Dt", "M"]]
    for _ in range(n):
        rows.append([rnd.choice([None, 0, 1, -3, 2.5, 7, 100, 1e9, 12345.678]), rnd.choice([0, 1, 2, 3, 0.1, 0.2, -1, None]), rnd.choice(["", "a", "Ab", "an", "  x  y ", "12", "Đức"]),
                     rnd.choice([None, dt.datetime(2026, 1, 31), dt.datetime(2024, 2, 29), dt.datetime(1999, 12, 31)]), rnd.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "abc", None])])
    return rows
def gnum(d):
    r = rnd.random()
    if d <= 0 or r < .25: return rnd.choice(["[N1]", "[N2]", "[M]", "0", "1", "2.5", "3", "100", "0.1", "[Dt]", "[T]"])
    if r < .55: return "(%s %s %s)" % (gnum(d - 1), rnd.choice("+-*/%"), gnum(d - 1))
    if r < .62: return "-" + gnum(d - 1)
    if r < .72: return "IF(%s, %s, %s)" % (gbool(d - 1), gnum(d - 1), gnum(d - 1))
    f = rnd.choice(["ABS", "ROUND", "CEIL", "FLOOR", "SQRT", "POWER", "MIN", "MAX", "SUM", "AVERAGE", "LEN", "YEAR", "MONTH", "DAY"])
    k = {"ROUND": rnd.choice([1, 2]), "POWER": 2, "MIN": rnd.randint(1, 3), "MAX": rnd.randint(1, 3), "SUM": rnd.randint(1, 3), "AVERAGE": rnd.randint(1, 3)}.get(f, 1)
    a = [gnum(d - 1) for _ in range(k)] if f not in ("LEN", "YEAR", "MONTH", "DAY") else [gstr(d - 1) if f == "LEN" else gdate(d - 1)]
    if f == "ROUND" and k == 2: a[1] = rnd.choice(["0", "1", "2", "-1", "2.5"])
    return "%s(%s)" % (f, ", ".join(a))
def gstr(d):
    r = rnd.random()
    if d <= 0 or r < .3: return rnd.choice(["[T]", '"a"', '""', '"Ab"', "[N1]", "[M]"])
    if r < .5: return "(%s & %s)" % (gstr(d - 1), gstr(d - 1))
    f = rnd.choice(["CONCAT", "LEFT", "RIGHT", "MID", "TRIM", "LOWER", "UPPER", "REPLACE", "SUBSTITUTE", "IF"])
    if f == "IF": return "IF(%s, %s, %s)" % (gbool(d - 1), gstr(d - 1), gstr(d - 1))
    n = {"CONCAT": 2, "LEFT": 2, "RIGHT": 2, "MID": 3, "REPLACE": 4, "SUBSTITUTE": 3}.get(f, 1); a = [gstr(d - 1)] + [gnum(d - 1) if (f in ("LEFT", "RIGHT", "MID") or (f == "REPLACE" and i < 2)) else gstr(d - 1) for i in range(n - 1)]
    return "%s(%s)" % (f, ", ".join(a))
def gbool(d):
    r = rnd.random()
    if d <= 0 or r < .15: return rnd.choice(["TRUE", "FALSE", "ISEMPTY([T])", "ISEMPTY([N1])"])
    if r < .6: return "(%s %s %s)" % ((gnum(d - 1), gstr(d - 1), gdate(d - 1))[rnd.randint(0, 2)] if False else gnum(d - 1), rnd.choice(["=", "<>", ">", "<", ">=", "<="]), gnum(d - 1))
    if r < .7: return "(%s %s %s)" % (gstr(d - 1), rnd.choice(["=", "<>", ">", "<"]), gstr(d - 1))
    if r < .78: return "(%s %s %s)" % (gdate(d - 1), rnd.choice(["=", ">", "<="]), gdate(d - 1))
    f = rnd.choice(["AND", "OR", "NOT"]); return "%s(%s)" % (f, ", ".join(gbool(d - 1) for _ in range(1 if f == "NOT" else rnd.randint(1, 3))))
def gdate(d):
    r = rnd.random()
    if d <= 0 or r < .35: return rnd.choice(["[Dt]", "[Dt]", "[N1]", "[T]"])
    if r < .6: return "(%s %s %s)" % (gdate(d - 1), rnd.choice("+-"), gnum(d - 1))
    if r < .7: return "(%s - %s)" % (gdate(d - 1), gdate(d - 1))
    return "IF(%s, %s, %s)" % (gbool(d - 1), gdate(d - 1), gdate(d - 1))
ROW = mkrows(40); mism = []; total = parsed = 0; kinds = {}
t0 = time.time()
for k in range(4000):
    expr = rnd.choice([gnum, gstr, gbool, gdate])(rnd.randint(1, 4))
    d, names0, types = derive(ROW, [op(1, "R", expr)]); total += 1
    if d["errors"]: mism.append(("LỖI CÚ PHÁP SINH RA", expr, d["errors"][0]["message"])); continue
    parsed += 1
    vals = d["cols"][0]["values"]
    for v in vals: kinds[type(v).__name__] = kinds.get(type(v).__name__, 0) + 1
    got = [list(ROW[0]) + ["R"]] + [list(ROW[i + 1]) + [vals[i]] for i in range(len(vals))]
    n, bad = F.independent_check(ROW, 5, names0, types, d["cols"], list(range(len(ROW))), list(range(6)), got, 1, S.to_num, S.to_date, S.blank)
    if bad: mism.append((expr, bad[0]))
print("SO SÁNH HAI BỘ TÍNH: %d công thức, %d lệch, %.1fs; kiểu kết quả: %s" % (total, len(mism), time.time() - t0, kinds)); [print("  ✗", m) for m in mism[:8]]

sys.exit(1 if (fails or mism) else 0)
