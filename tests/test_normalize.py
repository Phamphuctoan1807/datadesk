"""Chuẩn hóa dữ liệu (Giai đoạn 4): ví dụ trong lộ trình, so sánh hai bản cài trên dữ liệu ngẫu nhiên, tính lũy đẳng, quy trình, API, xuất file."""
import os, sys, io, json, copy, random, time, datetime as dt
os.environ["APP_PASSWORD"] = "t"; os.environ["AI_API_KEY"] = ""; sys.path.insert(0, ".")
import openpyxl, server as S, formula as F, pipeline as PL, normalize as NZ
D = dt.datetime; fails = []
def chk(n, got, exp=True):
    if got != exp: fails.append((n, got, exp))
OPT = {"text": {"case": "none", "accents": "keep"}, "phone": {"format": "vn"}, "date": {"order": "auto"}, "null": {"tokens": NZ.DEFAULT_NULLS}}
def col(kind, vals, opts=None, nf="auto"):
    o = dict(OPT.get(kind, {})); o.update(opts or {}); return NZ.norm_column(kind, vals, o, nf, S.to_num, S.to_date)
def vs(kind, vals, opts=None, nf="auto"): return [x[0] for x in col(kind, vals, opts, nf)]
def st(kind, vals, opts=None, nf="auto"): return [x[1] for x in col(kind, vals, opts, nf)]
# --- ví dụ trong lộ trình (mục 10) ---
chk("tên: ba biến thể về một dạng", vs("text", [" Nguyễn Văn A ", "NGUYỄN VĂN A", "Nguyễn  Văn A"], {"case": "title"}), ["Nguyễn Văn A"] * 3)
chk("điện thoại: ba biến thể về một dạng", vs("phone", ["0912 345 678", "0912345678", "+84 912 345 678"]), ["0912345678"] * 3)
chk("điện thoại E.164", vs("phone", ["0912 345 678", "+84 912 345 678", "84912345678"], {"format": "e164"}), ["+84912345678"] * 3)
chk("điện thoại mất số 0 đầu (Excel)", vs("phone", [912345678, "912345678", 84912345678]), ["0912345678"] * 3)
chk("điện thoại bàn Hà Nội", vs("phone", ["(024) 3123 4567", "+84 24 3123 4567"]), ["02431234567"] * 2)
chk("điện thoại sai", st("phone", ["abc", "123", "+1 202 555 0100", "0912 345", 912345678.5, True]), ["invalid"] * 6)
chk("email", (vs("email", [" An@Mail.COM ", "x@y.vn"]), st("email", ["a b@c.com", "bad", "a@b", "a@b.c", "a@-b.com", 5])), (["an@mail.com", "x@y.vn"], ["invalid"] * 6))
# --- số, tiền, phần trăm (mục 3.6): không đủ bằng chứng thì không tự chuyển ---
chk("số có bằng chứng kiểu Việt Nam", vs("number", ["1.234", "12,5", "1.234,5", "7"]), [1234, 12.5, 1234.5, 7])
chk("số có bằng chứng kiểu quốc tế", vs("number", ["1,234", "12.5", "1,234.5"]), [1234, 12.5, 1234.5])
chk("số mơ hồ, không đủ bằng chứng: không tự đổi", (st("number", ["1.234", "2.500", "3,100"]), [x[2] for x in col("number", ["1.234"])]), (["review"] * 3, ["AMBIGUOUS_NUMBER"]))
chk("số mơ hồ: chọn Việt Nam", vs("number", ["1.234", "1,234"], nf="vi"), [1234, 1.234]); chk("số mơ hồ: chọn quốc tế", vs("number", ["1.234", "1,234"], nf="en"), [1.234, 1234])
chk("tiền", vs("number", ["1000₫", "1.000.000 VND", "$1,234.50", " 7 "]), [1000, 1000000, 1234.5, 7]); chk("số có % thì báo lỗi ở loại số", st("number", ["10%"]), ["invalid"])
chk("phần trăm", (vs("percentage", ["10%", "12,5%", "0.1%"]), st("percentage", ["10", "abc"])), ([0.1, 0.125, 0.001], ["review", "invalid"]))
# --- ngày ---
chk("ngày: đủ bằng chứng ngày/tháng", [str(v)[:10] for v in vs("date", ["05/03/2026", "13/03/2026"])], ["2026-03-05", "2026-03-13"])
chk("ngày: đủ bằng chứng tháng/ngày", [str(v)[:10] for v in vs("date", ["05/03/2026", "03/13/2026"])], ["2026-05-03", "2026-03-13"])
chk("ngày: mơ hồ thì không tự đổi", (st("date", ["05/03/2026"]), [x[2] for x in col("date", ["05/03/2026"])]), (["review"], ["AMBIGUOUS_DATE"]))
chk("ngày: chọn thứ tự", ([str(v)[:10] for v in vs("date", ["05/03/2026"], {"order": "dmy"})], [str(v)[:10] for v in vs("date", ["05/03/2026"], {"order": "mdy"})]), (["2026-03-05"], ["2026-05-03"]))
chk("ngày: thứ tự chọn rõ thì tuân theo, ngày sai khoảng báo lỗi", st("date", ["05/13/2026", "13/05/2026"], {"order": "dmy"}), ["invalid", "changed"])
chk("ngày: các dạng không mơ hồ", [str(v)[:10] for v in vs("date", ["2026-03-05", "ngày 5 tháng 3 năm 2026", "5.3.2026 10:30", "29/02/2024", "2026/3/5 10:30"], {"order": "dmy"})], ["2026-03-05", "2026-03-05", "2026-03-05", "2024-02-29", "2026-03-05"])
chk("ngày không tồn tại", st("date", ["31/02/2024", "29/02/2023", "abc", "1/1/0000", 5, "05/03/26"], {"order": "dmy"}), ["invalid"] * 6); chk("ô đã là ngày giữ nguyên", st("date", [D(2026, 1, 2)]), ["unchanged"])
# --- chữ, Unicode, ô trống ---
nfd = "Nguye\u0302\u0303n Va\u0306n A"; chk("Unicode NFD về NFC", vs("text", [nfd]), ["Nguyễn Văn A"]); chk("bỏ ký tự vô hình và khoảng trắng lạ", vs("text", ["a\u200bb\u00a0 c\ufeff", "\t x \n y "]), ["ab c", "x y"])
chk("kiểu chữ", (vs("text", ["nGuyễn vĂN"], {"case": "lower"}), vs("text", ["nguyễn đức"], {"case": "upper"}), vs("text", ["nGUYỄN  đỨC"], {"case": "title"})), (["nguyễn văn"], ["NGUYỄN ĐỨC"], ["Nguyễn Đức"]))
chk("bỏ dấu tiếng Việt (đ thành d)", vs("text", ["Nguyễn Đức Hà", "đường"], {"accents": "strip"}), ["Nguyen Duc Ha", "duong"])
chk("trạng thái ô trống và ô không phải chữ", (st("text", ["", None, "   ", 5, "ok"]), vs("text", ["", None, "   ", 5])), (["empty", "empty", "changed", "unchanged", "unchanged"], ["", "", "", 5]))
chk("ô trống giả", (vs("null", ["N/A", "-", "ok", " NA ", "Không có", 0, "null"]), vs("null", ["x", "y"], {"tokens": ["x"]})), (["", "", "ok", "", "", 0, ""], ["", "y"]))
# --- cấu hình sai ---
def spec(**k):
    op = {"id": "r1", "type": "NORMALIZE", "kind": "text", "columns": ["A"], "options": {}}; op.update(k)
    try: NZ.compile_spec(op, ["A", "B"], ["text", "text"], {"b"}); return "OK"
    except NZ.NormError as e: return e.code
chk("cấu hình hợp lệ", spec(), "OK"); chk("loại sai", spec(kind="x"), "ERROR_OPERATOR"); chk("chưa chọn cột", spec(columns=[]), "ERROR_COLUMN"); chk("cột không có", spec(columns=["Z"]), "ERROR_COLUMN")
chk("cột công thức bị chặn", spec(columns=["B"]), "PROTECTED_COLUMN"); chk("kiểu chữ sai", spec(options={"case": "x"}), "ERROR_VALUE"); chk("cột mới trùng tên", spec(mode="new_column", columns=["A"]) , "OK")
# --- so sánh hai bản cài và tính lũy đẳng trên dữ liệu ngẫu nhiên ---
rnd = random.Random(21)
POOL = {"text": ["  An  ", "AN", "nguyễn  văn a", "Nguyễn\u00a0Văn\u200bA", "Nguye\u0302\u0303n", "", None, 5, 2.5, "  ", "Đặng", "ĐẶNG", "a\tb\n"],
        "null": ["N/A", "-", "ok", "  ", "null", " NA ", None, "Không có", 0, "khong co"],
        "phone": ["0912 345 678", "0912345678", "+84 912 345 678", "84912345678", "091.234.5678", "(024) 3123 4567", 912345678, 84912345678, "abc", "123", "", None, "+1 202 555 0100", "0012345", 912345678.5, True, "0084 912 345 678"],
        "email": [" An@Mail.COM", "x@y.vn", "a b@c.com", "bad", "a@b", "a@b.c", "A.B-C@d-e.f.com", "", None, 5, "a@-b.com", "a@b-.com", "A@B.CO "],
        "number": ["1.234", "1,234", "1.234,5", "1,234.5", "12,5", "12.5", "1000₫", "1.000.000 VND", "10%", "abc", "", None, 5, 2.5, "-3,5", "1.2.3", " 7 ", "+8", "1.234.567", "1,234,567"],
        "percentage": ["10%", "12,5%", "10", "0.1%", "abc", "", 0.1, "1.234%", None],
        "date": ["05/03/2026", "13/03/2026", "2026-03-05", "ngày 5 tháng 3 năm 2026", "31/02/2024", "abc", "", "5.3.2026", "03/05/2026", "2026/3/5 10:30", "29/02/2024", "1/1/0000", D(2026, 1, 2), 5, "03/13/2026", "5/5/2026"]}
def eqv(a, b):  # b: bản độc lập (Decimal, chuỗi, ngày)
    if isinstance(a, bool) or isinstance(b, bool): return a is b
    return F.same(b, a)
bad = []; idem = []; tot = 0
for it in range(1500):
    kind = rnd.choice(NZ.KINDS); vals = [rnd.choice(POOL[kind]) for _ in range(rnd.randint(1, 25))]
    o = dict(OPT.get(kind, {})); nf = rnd.choice(["auto", "vi", "en"])
    if kind == "text": o = {"case": rnd.choice(["none", "lower", "upper", "title"]), "accents": rnd.choice(["keep", "strip"])}
    if kind == "phone": o = {"format": rnd.choice(["vn", "e164"])}
    if kind == "date": o = {"order": rnd.choice(["auto", "dmy", "mdy"])}
    a = NZ.norm_column(kind, vals, o, nf, S.to_num, S.to_date); b = NZ.inorm_column(kind, vals, o, nf, S.to_num, S.to_date); tot += 1
    for i, (x, y) in enumerate(zip(a, b)):
        if x[1] != y[1] or x[2] != y[2] or (x[1] in ("changed", "unchanged", "empty") and not eqv(x[0], y[0])): bad.append((kind, vals[i], x, y)); break
    if kind in ("text", "phone", "email", "null"):  # chuẩn hóa hai lần cho kết quả như một lần
        once = [x[0] for x in a]; twice = NZ.norm_column(kind, once, o, nf, S.to_num, S.to_date)
        if any(t[1] == "changed" for t in twice): idem.append((kind, vals, once))
chk("hai bản cài giống nhau (%d bộ ngẫu nhiên)" % tot, bad[:2], []); chk("tính lũy đẳng", idem[:2], [])
# --- quy trình ---
def run(rows, ops, nf="auto"): return S.derive_table(S.mk("T", rows), ops, nf)
def nz(i, kind, cols, mode="replace", options=None, name=""): return {"id": "rule_%03d" % i, "type": "NORMALIZE", "enabled": True, "name": name, "kind": kind, "columns": cols, "mode": mode, "options": options or {}}
def frm(i, t, e): return {"id": "rule_%03d" % i, "type": "FORMULA", "target": t, "expression": e, "enabled": True}
def cl(d, name): v = d["view"]["rows"]; j = v[0].index(name); return [r[j] for r in v[1:]]
def indep(d):
    v = d["view"]; rr = v["rows"]; g = {(i + 1, j + 1): c for (i, j), c in (v.get("cfills") or {}).items()}
    r = PL.independent_pipeline_check(v["derived"], list(range(len(rr))), list(range(len(rr[0]))), rr, g, {i: i + 1 for i in range(len(rr))}, set(), [S.disp(x) for x in rr[0]], True, S.to_num, S.to_date, S.blank); return r[1] + r[3]
DT = [["Tên", "SĐT", "Giá", "Ngày", "Tỷ lệ"], [" nguyễn  văn a ", "0912 345 678", "1.000₫", "13/03/2026", "10%"], ["TRẦN THỊ B", "+84 913 456 789", "2.500₫", "05/03/2026", "12,5%"], ["lê c", "913456780", "12,5", "2026-03-01", "5%"], ["", "abc", "x", "31/02/2026", "7%"]] + [["Hà %d" % i, "0912345%03d" % i, "%d" % (i * 10), "0%d/03/2026" % (i % 9 + 1), "%d%%" % i] for i in range(7)]
d = run(DT, [nz(1, "text", ["Tên"], options={"case": "title"}), nz(2, "phone", ["SĐT"]), nz(3, "number", ["Giá"]), nz(4, "date", ["Ngày"]), nz(5, "percentage", ["Tỷ lệ"])])
chk("quy trình chuẩn hóa không bị từ chối", d.get("errors"), []); chk("tên", cl(d, "Tên")[:3], ["Nguyễn Văn A", "Trần Thị B", "Lê C"]); chk("điện thoại", cl(d, "SĐT")[:4], ["0912345678", "0913456789", "0913456780", "abc"])
chk("số: 1.000₫ và 2.500₫ đủ bằng chứng nhờ ô 12,5", cl(d, "Giá")[:3], [1000, 2500, 12.5]); chk("ngày: 13/03 là bằng chứng ngày/tháng", [str(v)[:10] for v in cl(d, "Ngày")[:3]], ["2026-03-13", "2026-03-05", "2026-03-01"]); chk("ngày sai giữ nguyên", cl(d, "Ngày")[3], "31/02/2026")
chk("phần trăm", cl(d, "Tỷ lệ")[:3], [0.1, 0.125, 0.05]); chk("định dạng ô ngày và phần trăm", (d["view"]["fm"][1][3], d["view"]["fm"][1][4]), ("dd/mm/yyyy", "0.##%"))
chk("trạng thái: có ô không chuẩn hóa được", (d["stats"]["rule_002"]["invalid"], d["stats"]["rule_003"]["invalid"], d["stats"]["rule_004"]["invalid"]), (1, 1, 1)); chk("nhật ký lỗi có dòng và gợi ý", {e["code"] for e in d["errlog"]} >= {"INVALID_PHONE", "INVALID_NUMBER", "INVALID_DATE"}, True)
chk("bộ kiểm tra độc lập khớp", indep(d), [])
d = run(DT, [nz(1, "number", ["Giá"]), frm(2, "Gấp đôi", "[Giá] * 2")]); chk("chuẩn hóa rồi tính công thức", cl(d, "Gấp đôi")[:3], [2000, 5000, 25]); chk("độc lập khớp (chuẩn hóa rồi công thức)", indep(d), [])
d = run(DT, [frm(1, "Gấp đôi", "[Giá] * 2"), nz(2, "number", ["Giá"])]); chk("công thức tự đọc được chuỗi số khi cả cột là cột số, kể cả chưa chuẩn hóa", cl(d, "Gấp đôi")[:3], [2000, 5000, 25])
d = run(DT, [nz(1, "text", ["Tên"], "new_column", {"case": "upper"})]); chk("tạo cột mới, giữ nguyên cột gốc", (d["view"]["rows"][0][-1], cl(d, "Tên (chuẩn hóa)")[:2], cl(d, "Tên")[0]), ("Tên (chuẩn hóa)", ["NGUYỄN VĂN A", "TRẦN THỊ B"], " nguyễn  văn a ")); chk("độc lập khớp (cột mới)", indep(d), [])
d = run(DT, [nz(1, "number", ["Giá"], "new_column"), frm(2, "T", "[Giá (chuẩn hóa)] + 1")]); chk("công thức dùng cột chuẩn hóa mới", cl(d, "T")[:3], [1001, 2501, 13.5]); chk("độc lập khớp (cột mới rồi công thức)", indep(d), [])
d = run(DT, [frm(1, "F", "1"), nz(2, "text", ["F"])]); chk("không chuẩn hóa cột công thức", d["errors"][0]["code"], "PROTECTED_COLUMN")
d = run(DT, [nz(1, "text", ["Không có"])]); chk("cột không tồn tại", d["errors"][0]["code"], "ERROR_COLUMN"); d = run(DT, [frm(1, "X", "[Tên (chuẩn hóa)]"), nz(2, "text", ["Tên"], "new_column")]); chk("dùng cột tạo ở bước sau", (d["errors"][0]["code"], "bước 2" in d["errors"][0]["message"]), ("ERROR_COLUMN", True))
d = run(DT, [nz(1, "date", ["Ngày"], options={"order": "mdy"})]); chk("chọn tháng/ngày", str(cl(d, "Ngày")[1])[:10], "2026-05-03"); chk("độc lập khớp (mdy)", indep(d), [])
d = run(DT, [nz(1, "date", ["Ngày"], options={"order": "dmy"}), nz(2, "date", ["Ngày"], options={"order": "dmy"})]); chk("chuẩn hóa hai lần: lần hai không đổi gì", d["stats"]["rule_002"]["changed"], 0)
snap = copy.deepcopy(S.mk("T", DT)["rows"]); t0 = S.mk("T", DT); S.derive_table(t0, [nz(1, "text", ["Tên"], options={"case": "upper"})]); chk("bảng gốc bất biến", t0["rows"], snap)
# --- API ---
H = {"X-Requested-With": "datadesk"}; c = S.app.test_client(); c.post("/login", json={"password": "t"})
wb = openpyxl.Workbook(); ws = wb.active
for r in DT: ws.append([x for x in r])
b = io.BytesIO(); wb.save(b); b.seek(0); sid = c.post("/api/analyze", data={"file": (b, "n.xlsx")}, content_type="multipart/form-data", headers=H).get_json()["id"]
def post(path, **k): p = dict(id=sid, table=0, header=True); p.update(k); return c.post(path, json=p, headers=H).get_json()
def state(): return c.get("/api/transform/state?id=%s&t=0" % sid).get_json()["data"]
info = c.get("/api/table?id=%s&t=0&header=1" % sid).get_json(); kinds = {(h["name"], h["kind"]) for h in info["hints"]}
chk("gợi ý chuẩn hóa theo dữ liệu", {("SĐT", "phone"), ("Tên", "text")} <= kinds, True)
N1 = {"name": "Họ tên", "kind": "text", "columns": ["Tên"], "options": {"case": "title"}}
r = post("/api/normalize/preview", norm=N1); chk("xem trước", (r["success"], r["data"]["changed"], r["data"]["overwritten"], r["data"]["status"], r["data"]["rows"][0]), (True, 3, 3, "REVIEW_REQUIRED", [2, " nguyễn  văn a  → Nguyễn Văn A"]))
chk("xem trước: có ghi đè", r["data"]["overwritten"] > 0, True); chk("chưa lưu khi xem trước", len(state()["list"]), 0)
r = post("/api/normalize/apply", norm=N1); chk("ghi đè cần xác nhận", (r["success"], r["errors"][0]["code"]), (False, "NEEDS_CONFIRM")); r = post("/api/normalize/apply", norm=N1, confirm=True); chk("xác nhận rồi áp dụng", r["success"], True)
r = post("/api/transform/apply", op=dict(N1, type="NORMALIZE", name="x", kind="phone", columns=["SĐT"], options={}), confirm=True); chk("giao diện chung: chuẩn hóa", r["success"], True)
r = post("/api/transform/preview", op={"type": "NORMALIZE", "kind": "phone", "columns": ["SĐT"], "mode": "new_column"}); chk("xem trước tạo cột mới", r["data"]["new_columns"], ["SĐT (chuẩn hóa)"]); chk("vấn đề kèm gợi ý sửa", r["data"]["problems"][0]["row"] > 0 and bool(r["data"]["problems"][0]["fix"]), True) if r["data"]["problems"] else chk("có ô cần kiểm tra", False)
rep = c.get("/api/validate/report?id=%s&t=0" % sid).get_json()["data"]; chk("báo cáo lỗi có ô không chuẩn hóa được", "INVALID_PHONE" in {e["type"] for e in rep["errors"]}, True)
P = dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": 0, "dir": "asc"}]); r = c.post("/api/process", json=P, headers=H).get_json(); chk("xuất ok, kiểm tra độc lập đạt", (r["ok"], [k["t"] for k in r["checks"] if not k["ok"]]), (True, [])); chk("trạng thái cần kiểm tra vì còn ô lỗi", r["status"], "REVIEW_REQUIRED")
w = openpyxl.load_workbook(io.BytesIO(c.get("/api/download/" + r["token"]).data)).active; hdr = [x.value for x in w[1]]; chk("xuất: tên đã chuẩn hóa", sorted(x.value for x in w["A"][1:] if x.value)[:2], ["Hà 0", "Hà 1"])
st_ = state(); chk("nhật ký ghi bước chuẩn hóa", [x["action"] for x in st_["log"][:2]], ["thêm", "thêm"]); post("/api/transform/undo"); post("/api/transform/redo"); chk("hoàn tác và làm lại", len(state()["list"]), 2)
chk("csv ok", c.post("/api/process", json=dict(P, format="csv"), headers=H).get_json()["ok"], True)
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["SĐT", "Ngày", "Tỷ lệ"])
for i in range(30): ws.append(["0912 345 %03d" % i, "%02d/03/2026" % (i % 28 + 1), "%d%%" % (i % 100)])
b = io.BytesIO(); wb.save(b); b.seek(0); sid = c.post("/api/analyze", data={"file": (b, "m.xlsx")}, content_type="multipart/form-data", headers=H).get_json()["id"]
for k, cols_, o in (("phone", ["SĐT"], {}), ("date", ["Ngày"], {}), ("percentage", ["Tỷ lệ"], {})): chk("áp dụng " + k, post("/api/normalize/apply", norm={"kind": k, "columns": cols_, "options": o}, confirm=True)["success"], True)
r = c.post("/api/process", json=dict(id=sid, table=0, header=True, format="xlsx"), headers=H).get_json(); chk("xuất nhiều bước chuẩn hóa", (r["ok"], r["status"]), (True, "SAFE"))
w = openpyxl.load_workbook(io.BytesIO(c.get("/api/download/" + r["token"]).data)).active
chk("ô ngày là ngày thật có định dạng", (isinstance(w["B2"].value, D), w["B2"].number_format), (True, "dd/mm/yyyy")); chk("phần trăm là số có định dạng %", (w["C3"].value, w["C3"].number_format), (0.01, "0.##%")); chk("điện thoại là chuỗi", w["A2"].value, "0912345000")
# --- hiệu năng ---
if not os.environ.get("DATADESK_FAST"):
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Tên", "SĐT", "Giá"]); rr = random.Random(3)
    for i in range(50000): ws.append([rr.choice([" nguyễn  văn a ", "TRẦN THỊ B", "lê c"]), rr.choice(["0912 345 678", "+84 913 456 789", "913456780"]), rr.choice(["1.000₫", "2.500₫", "12,5"])])
    b = io.BytesIO(); wb.save(b); b.seek(0); sid = c.post("/api/analyze", data={"file": (b, "big.xlsx")}, content_type="multipart/form-data", headers=H).get_json()["id"]; t0 = time.time()
    for k, cols_, o in (("text", ["Tên"], {"case": "title"}), ("phone", ["SĐT"], {}), ("number", ["Giá"], {})): assert post("/api/normalize/apply", norm={"kind": k, "columns": cols_, "options": o}, confirm=True)["success"]
    t1 = time.time(); r = c.post("/api/process", json=dict(id=sid, table=0, header=True, format="xlsx"), headers=H).get_json()
    print("HIỆU NĂNG 50.000 dòng: áp dụng 3 bước chuẩn hóa %.1fs, xuất + kiểm tra độc lập %.1fs, ok=%s" % (t1 - t0, time.time() - t1, r["ok"])); chk("hiệu năng: xuất đạt", r["ok"], True)
print("CHUẨN HÓA: %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:12]]
sys.exit(1 if fails else 0)
