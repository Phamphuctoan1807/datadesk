import os, sys, io, random, datetime as dt, copy, time, json
os.environ["APP_PASSWORD"] = "t"; os.environ["AI_API_KEY"] = ""; sys.path.insert(0, ".")
import openpyxl, server as S, formula as F, rules as RL, pipeline as PL
fails = []
def chk(n, got, exp=True):
    if got != exp: fails.append((n, got, exp))
D = dt.datetime
H = ["Mã", "Điểm", "Tên", "Ngày", "Ghi chú"]
BASE = [H, ["A1", 4, "An", D(2026, 1, 5), ""], ["A2", 6, "Bình", D(2026, 2, 5), "ok"], ["A3", 9, "an", None, None], ["A4", 8.5, "Đức", D(2026, 3, 1), "gấp"],
        ["A5", None, "Lê", D(2026, 4, 1), "ok"], ["A6", "abc", "Hồ", D(2026, 5, 1), ""], ["A1", 7, "Vũ", D(2026, 6, 1), ""]]
def C(col, op, val="", **k): return dict({"column": col, "operator": op, "value": val}, **k)
def rule(i, items, then, els=None, logic="AND", name="", en=True): return {"id": "rule_%03d" % i, "type": "CONDITIONAL", "enabled": en, "name": name, "when": {"logic": logic, "items": items}, "then": then, "else": els or []}
def SV(t, v, vt="text"): return {"type": "set_value", "target": t, "value": v, "value_type": vt}
def MK(label, target=""): return {"type": "mark", "target": target, "value": label}
def COL(color="#FF0000", scope="row", target=""): return {"type": "color", "color": color, "scope": scope, "target": target}
def run(ops, rows=BASE): return S.derive_table(S.mk("T", rows), ops)
def col(d, name): j = d["view"]["rows"][0].index(name); return [r[j] for r in d["view"]["rows"][1:]]
def err(ops, rows=BASE): d = run(ops, rows); return d["errors"][0]["code"] if d.get("errors") else "OK"
d = run([rule(1, [C("Điểm", "<", "5")], [SV("Xếp loại", "Yếu")], [SV("Xếp loại", "Đạt")])])
chk("THEN/ELSE + ô lỗi không chạy nhánh nào", col(d, "Xếp loại"), ["Yếu", "Đạt", "Đạt", "Đạt", "Đạt", "", "Đạt"])
chk("thống kê", (d["stats"]["rule_001"]["matched"], d["stats"]["rule_001"]["errors"]), (1, {"ERROR_TYPE": 1}))
def matched(items, logic="AND", rows=BASE): d = run([rule(1, items, [MK("x", "M")], logic=logic)], rows); return [i for i, v in enumerate(col(d, "M")) if v == "x"]
chk("AND", matched([C("Điểm", ">=", "6"), C("Tên", "contains", "n")]), [1, 2]); chk("OR", matched([C("Ghi chú", "=", "gấp"), C("Điểm", "<", "5")], "OR"), [0, 3])
chk("starts_with", matched([C("Tên", "starts_with", "b")]), [1]); chk("ends_with", matched([C("Tên", "ends_with", "N")]), [0, 2]); chk("= không phân biệt hoa thường", matched([C("Tên", "=", "AN")]), [0, 2])
chk("in", matched([C("Mã", "in", "A2; A4")]), [1, 3]); chk("not_in", matched([C("Mã", "not_in", "A1;A2;A3;A4")]), [4, 5]); chk("is_empty", matched([C("Ghi chú", "is_empty")]), [0, 2, 5, 6]); chk("is_not_empty", matched([C("Ghi chú", "is_not_empty")]), [1, 3, 4])
chk("trùng", matched([C("Mã", "is_duplicate")]), [0, 6]); chk("duy nhất", matched([C("Mã", "is_unique")]), [1, 2, 3, 4, 5]); chk("khác với ô trống", matched([C("Ghi chú", "!=", "ok")]), [0, 2, 3, 5, 6])
chk("ngày lớn hơn", matched([C("Ngày", ">", "01/03/2026")]), [4, 5, 6]); chk("ngày rỗng không khớp", 2 in matched([C("Ngày", "<", "01/01/2030")]), False); chk("NOT từng điều kiện", matched([C("Tên", "contains", "n", **{"not": True})]), [3, 4, 5, 6])
chk("số lẫn chữ: ô số so như số", matched([C("Điểm", "=", "7")]), [6]); chk("bằng số khi cột lẫn chữ", matched([C("Điểm", "=", "abc")]), [5])
# hành động
d = run([rule(1, [C("Ghi chú", "=", "ok")], [{"type": "clear", "target": "Ghi chú"}])]); chk("clear", col(d, "Ghi chú"), ["", "", "", "gấp", "", "", ""]); chk("đếm ghi đè", d["stats"]["rule_001"]["overwritten"], 2)
d = run([rule(1, [C("Tên", "contains", "n")], [{"type": "replace", "target": "Tên", "find": "n", "with": "N"}])]); chk("replace phân biệt hoa thường", col(d, "Tên"), ["AN", "BìNh", "aN", "Đức", "Lê", "Hồ", "Vũ"])
d = run([rule(1, [C("Điểm", ">=", "6")], [MK("Cao")]), rule(2, [C("Tên", "contains", "n")], [MK("Có n")])]); chk("đánh dấu nối nhãn", col(d, "Đánh dấu"), ["Có n", "Cao; Có n", "Cao; Có n", "Cao", "", "", "Cao"])
d = run([rule(1, [C("Điểm", ">=", "6")], [MK("Cao")]), rule(2, [C("Điểm", ">=", "6")], [MK("Cao")])]); chk("không lặp nhãn", col(d, "Đánh dấu")[1], "Cao")
d = run([rule(1, [C("Điểm", ">=", "6")], [SV("Hạng", "5", "number")])]); chk("điền số", col(d, "Hạng")[1:4], [5, 5, 5]); chk("kiểu cột số", d["view"]["derived"]["ctypes"][5], "number")
d = run([rule(1, [C("Ghi chú", "is_empty")], [SV("Ghi chú", "thiếu")]), rule(2, [C("Ghi chú", "=", "thiếu")], [COL("#ff0000")], [COL("#00ff00", "cell", "Tên")])])
chk("tuần tự: quy tắc sau thấy kết quả trước", [d["view"]["cfills"].get((i + 1, 0)) for i in range(7)], ["#FF0000", None, "#FF0000", None, None, "#FF0000", "#FF0000"]); chk("màu ô ở nhánh ELSE", d["view"]["cfills"].get((2, 2)), "#00FF00")
d = run([rule(1, [C("Điểm", "<", "5")], [COL("#FF0000")]), rule(2, [C("Mã", "=", "A1")], [COL("#0000FF", "cell", "Mã")])]); chk("quy tắc sau ghi đè màu", (d["view"]["cfills"][(1, 0)], d["view"]["cfills"][(1, 1)]), ("#0000FF", "#FF0000"))
d = run([{"id": "rule_001", "type": "FORMULA", "target": "Gấp đôi", "expression": "[Điểm] * 2", "enabled": True}, rule(2, [C("Gấp đôi", ">", "10")], [MK("Cao")])]); chk("điều kiện trên cột công thức", col(d, "Đánh dấu"), ["", "Cao", "Cao", "Cao", "", "", "Cao"])
chk("cột công thức bị bảo vệ", err([{"id": "rule_001", "type": "FORMULA", "target": "G", "expression": "1", "enabled": True}, rule(2, [C("Mã", "=", "A1")], [SV("G", "x")])]), "PROTECTED_COLUMN")
chk("cột không tồn tại", err([rule(1, [C("Xyz", "=", "1")], [MK("a")])]), "ERROR_COLUMN"); chk("cột đích không tồn tại khi xóa", err([rule(1, [C("Mã", "=", "A1")], [{"type": "clear", "target": "Nope"}])]), "ERROR_COLUMN")
chk("màu sai", err([rule(1, [C("Mã", "=", "A1")], [COL("đỏ")])]), "ERROR_VALUE"); chk("không có THEN", err([rule(1, [C("Mã", "=", "A1")], [])]), "ERROR_SYNTAX"); chk("không có điều kiện", err([rule(1, [], [MK("a")])]), "ERROR_SYNTAX")
chk("toán tử sai", err([rule(1, [C("Mã", "~", "A1")], [MK("a")])]), "ERROR_OPERATOR"); chk("danh sách rỗng", err([rule(1, [C("Mã", "in", " ; ")], [MK("a")])]), "ERROR_VALUE"); chk("contains rỗng", err([rule(1, [C("Mã", "contains", "")], [MK("a")])]), "ERROR_VALUE")
chk("nhãn có ;", err([rule(1, [C("Mã", "=", "A1")], [MK("a;b")])]), "ERROR_VALUE"); chk("tên cột mới sai", err([rule(1, [C("Mã", "=", "A1")], [SV("a[b]", "x")])]), "INVALID_NAME"); chk("ngày sai", err([rule(1, [C("Ngày", ">", "abc")], [MK("a")])]), "ERROR_VALUE")
chk("số sai cho cột số", err([rule(1, [C("Điểm", "<", "x")], [MK("a")])], BASE[:5] + [["A9", 3, "Z", None, ""]]), "ERROR_VALUE"); chk("giá trị số sai", err([rule(1, [C("Mã", "=", "A1")], [SV("N", "abc", "number")])]), "ERROR_VALUE")
chk("thiếu chữ thay", err([rule(1, [C("Mã", "=", "A1")], [{"type": "replace", "target": "Tên", "find": "", "with": "x"}])]), "ERROR_VALUE")
chk("quy tắc tắt bị bỏ qua", run([rule(1, [C("Mã", "=", "A1")], [MK("x", "M")], en=False)])["view"]["rows"][0], H)
t = S.mk("T", BASE); snap = copy.deepcopy(t["rows"]); S.derive_table(t, [rule(1, [C("Điểm", "<", "9")], [SV("Ghi chú", "ĐÃ SỬA"), COL()], [{"type": "clear", "target": "Tên"}])]); chk("bảng gốc bất biến", t["rows"], snap)
# ---- API ----
H_ = {"X-Requested-With": "datadesk"}; c = S.app.test_client()
chk("chưa đăng nhập", c.post("/api/rule/preview", json={}, headers=H_).status_code, 401); c.post("/login", json={"password": "t"})
wb = openpyxl.Workbook(); ws = wb.active; ws.append(H)
for r in [["A1", 4, "An", D(2026, 1, 5), ""], ["A2", 6, "Bình", D(2026, 2, 5), "ok"], ["A3", 9, "an", None, None], ["A4", 8.5, "Đức", D(2026, 3, 1), "gấp"], ["A5", None, "Lê", D(2026, 4, 1), "ok"], ["A6", 3, "Hồ", D(2026, 5, 1), ""], ["A7", 7, "Vũ", D(2026, 6, 1), ""], ["A8", 2, "Mai", D(2026, 7, 1), "x"]]: ws.append(r)
for r_ in range(2, 10): ws.cell(r_, 4).number_format = "dd/mm/yyyy"
b = io.BytesIO(); wb.save(b); b.seek(0)
sid = c.post("/api/analyze", data={"file": (b, "t.xlsx")}, content_type="multipart/form-data", headers=H_).get_json()["id"]; orig = copy.deepcopy(S.STORE[sid]["tables"][0]["rows"])
def post(path, **k): p = dict(id=sid, table=0, header=True); p.update(k); return c.post(path, json=p, headers=H_).get_json()
def state(): return c.get("/api/transform/state?id=%s&t=0" % sid).get_json()["data"]
R1 = {"name": "Xếp loại", "when": {"logic": "AND", "items": [C("Điểm", "<", "5")]}, "then": [SV("Xếp loại", "Yếu"), COL("#FFB4B4")], "else": [SV("Xếp loại", "Đạt")]}
r = post("/api/rule/preview", rule=R1); chk("preview ok", r["success"]); chk("preview thống kê", (r["data"]["matched"], r["data"]["new_columns"], r["data"]["overwritten"], r["data"]["colored_cells"]), (3, ["Xếp loại"], 0, 18)); chk("preview mẫu", r["data"]["rows"][0], [2, "Yếu"])
chk("preview không lưu", len(state()["list"]), 0); chk("cần tiêu đề", "cần dòng tiêu đề" in post("/api/rule/preview", rule=R1, header=False).get("error", ""), True)
chk("apply 1", post("/api/rule/apply", rule=R1)["success"], True)
R2 = {"name": "Giỏi", "when": {"logic": "AND", "items": [C("Điểm", ">=", "8")]}, "then": [SV("Ghi chú", "Giỏi")]}
r = post("/api/rule/apply", rule=R2); chk("ghi đè cần xác nhận", (r["success"], r["errors"][0]["code"], r["data"]["overwritten"]), (False, "NEEDS_CONFIRM", 1)); chk("chưa lưu khi chưa xác nhận", len(state()["list"]), 1)
chk("xác nhận ghi đè", post("/api/rule/apply", rule=R2, confirm=True)["success"], True); chk("bảng gốc vẫn bất biến", S.STORE[sid]["tables"][0]["rows"], orig)
t_ = c.get("/api/table?id=%s&t=0&header=0" % sid).get_json(); chk("cột mới có trong bảng", [x["name"] for x in t_["columns"]][-1], "Xếp loại")
P = dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": 5, "dir": "asc"}], highlights=[], marks=[])
r = c.post("/api/process", json=P, headers=H_).get_json(); chk("xuất ok", r["ok"], True); chk("có bước kiểm tra quy tắc", "Quy tắc điều kiện khớp bản tính độc lập" in [k["t"] for k in r["checks"]], True); chk("mọi bước đạt", [k["t"] for k in r["checks"] if not k["ok"]], [])
w = openpyxl.load_workbook(io.BytesIO(c.get("/api/download/" + r["token"]).data)).active; rows = [[x.value for x in row] for row in w.iter_rows(min_row=1, max_row=9)]
chk("tiêu đề", rows[0][5], "Xếp loại"); chk("sắp theo cột do quy tắc tạo (thứ tự tiếng Việt: Đạt trước Yếu)", [x[5] for x in rows[1:]], ["Đạt"] * 5 + ["Yếu"] * 3); chk("ghi đè Giỏi", sorted([x[4] for x in rows[1:] if x[4] == "Giỏi"]), ["Giỏi"] * 2)
yeu = [i + 2 for i, x in enumerate(rows[1:]) if x[5] == "Yếu"]; chk("dòng Yếu có màu", [str(w.cell(i, 1).fill.fgColor.rgb)[-6:] for i in yeu], ["FFB4B4"] * 3); chk("dòng Đạt không màu", all(w.cell(i + 2, 1).fill.fill_type is None for i, x in enumerate(rows[1:]) if x[5] != "Yếu"), True)
chk("csv ok", c.post("/api/process", json=dict(P, format="csv"), headers=H_).get_json()["ok"], True)
chk("công thức + quy tắc", post("/api/formula/apply", target="Gấp đôi", expression="[Điểm]*2")["success"], True)
r = post("/api/rule/apply", rule={"when": {"items": [C("Gấp đôi", ">", "10")]}, "then": [MK("Cao")]}); chk("quy tắc dùng cột công thức", r["success"], True)
r = post("/api/rule/apply", rule={"when": {"items": [C("Mã", "=", "A1")]}, "then": [SV("Gấp đôi", "x")]}); chk("ghi đè cột công thức bị chặn", (r["success"], r["errors"][0]["code"]), (False, "PROTECTED_COLUMN"))
r = c.post("/api/process", json=P, headers=H_).get_json(); chk("xuất công thức + quy tắc", (r["ok"], [k["t"] for k in r["checks"] if not k["ok"]]), (True, [])); chk("có cả hai bước kiểm tra độc lập", [k["t"] for k in r["checks"] if "độc lập" in k["t"]], ["Công thức khớp bản tính độc lập", "Quy tắc điều kiện khớp bản tính độc lập"])
r = c.post("/api/process", json=dict(P, columns=[0, 5]), headers=H_).get_json(); chk("xuất một phần cột", r["ok"], True)
ids = [o["id"] for o in state()["list"]]; types = [o["type"] for o in state()["list"]]; chk("danh sách thao tác", types, ["CONDITIONAL", "CONDITIONAL", "FORMULA", "CONDITIONAL"])
r = post("/api/transform/update", action="move_up", op_id=ids[3]); chk("không cho đưa quy tắc lên trước công thức nó cần", (r["success"], "được tạo ở bước" in r["errors"][0]["message"]), (False, True))
chk("đổi thứ tự công thức lên trên quy tắc", (post("/api/transform/update", action="move_up", op_id=ids[2])["success"], [o["id"] for o in state()["list"]]), (True, [ids[0], ids[2], ids[1], ids[3]]))
post("/api/transform/undo")
chk("sửa quy tắc", post("/api/rule/apply", rule=dict(R1, name="Xếp loại v2"), op_id=ids[0], confirm=True)["success"], True); chk("tên sau sửa", [o.get("name") for o in state()["list"] if o["id"] == ids[0]], ["Xếp loại v2"])
n_ = len(state()["list"]); chk("hoàn tác", (post("/api/transform/undo")["success"], len(state()["list"])), (True, n_)); post("/api/transform/redo")
chk("quy tắc dùng cột do quy tắc trước tạo", post("/api/rule/apply", rule={"when": {"items": [C("Xếp loại", "=", "Yếu")]}, "then": [MK("Y")]}, confirm=True)["success"], True)
r = post("/api/transform/update", action="delete", op_id=ids[0]); chk("xóa quy tắc tạo cột đang được dùng bị chặn", (r["success"], r["errors"][0]["code"]), (False, "ERROR_COLUMN"))
while state()["can_undo"]: post("/api/transform/undo")
chk("hoàn tác hết", (len(state()["list"]), S.STORE[sid]["tables"][0]["rows"] == orig), (0, True))
print("QUY TẮC (đơn vị + API): %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:15]]
# ---- so sánh bộ chính và bộ độc lập trên quy tắc ngẫu nhiên ----
rnd = random.Random(5); NEW = ["X", "Y", "Nhãn", "Đánh dấu"]; SRC = ["Mã", "Điểm", "Tên", "Ngày", "Ghi chú"]
def vals_for(cn):
    return {"Mã": ["A1", "A", "", "A2;A3", "a1"], "Điểm": ["5", "7", "abc", "8.5", "0"], "Tên": ["an", "n", "Đức", "", "Vũ"], "Ngày": ["01/03/2026", "15/02/2026", "abc", "31/12/2026"], "Ghi chú": ["ok", "", "gấp", "x;ok"]}.get(cn, ["x", "1", "", "ok"])
def rcond(names):
    cn = rnd.choice(names); op = rnd.choice(RL.COND_OPS); return dict(C(cn, op, rnd.choice(vals_for(cn))), **{"not": rnd.random() < .15})
def ract(names):
    t = rnd.choice(["set_value", "set_value", "clear", "replace", "color", "mark", "add_to_list", "append_last"]); tg = rnd.choice(names + NEW)
    if t == "set_value": return SV(tg, rnd.choice(["Yếu", "5", "", "x y"]), rnd.choice(["text", "number"]))
    if t == "clear": return {"type": t, "target": rnd.choice(names)}
    if t == "replace": return {"type": t, "target": rnd.choice(names), "find": rnd.choice(["n", "o", "A", "1"]), "with": rnd.choice(["", "N", "zz"])}
    if t == "color": return COL(rnd.choice(["#FF0000", "#00ff00", "#0000FF"]), rnd.choice(["row", "cell"]), rnd.choice(names))
    if t == "append_last": return {"type": t, "value": rnd.choice(["Cuối", "Xem lại"])}
    if t == "add_to_list": return {"type": t, "target": rnd.choice(["", "Danh sách", "Nhãn"]), "value": rnd.choice(["Cần kiểm tra", "Thiếu"])}
    return MK(rnd.choice(["Cao", "Thiếu", "Lỗi"]), rnd.choice(["", "Đánh dấu", "Nhãn", "Ghi chú"]))
def rrows(n):
    return [H] + [[rnd.choice(["A1", "A2", "A3", "a1", ""]), rnd.choice([None, 0, 4, 5, 7, 8.5, 9, "abc"]), rnd.choice(["An", "an", "Đức", "", "Vũ", "Bình"]), rnd.choice([None, D(2026, 2, 15), D(2026, 3, 1), D(2026, 12, 31)]), rnd.choice(["", "ok", "gấp", None, "x"])] for _ in range(n)]
tot = ok_ = mis = 0; bad_ex = []; t0 = time.time()
for k in range(3000):
    rows = rrows(rnd.randint(5, 25)); names = list(SRC); ops = []
    for i in range(rnd.randint(1, 4)):
        ops.append(rule(i + 1, [rcond(names + ([rnd.choice(NEW)] if rnd.random() < .3 else [])) for _ in range(rnd.randint(1, 3))], [ract(names) for _ in range(rnd.randint(1, 2))], [ract(names) for _ in range(rnd.randint(0, 1))], rnd.choice(["AND", "OR"])))
    d = S.derive_table(S.mk("T", rows), ops); tot += 1
    if d.get("errors"): continue
    ok_ += 1; v = d["view"]; dv = v["derived"]; rr = v["rows"]; W = len(rr[0])
    outidx = list(range(len(rr))); pos = {i: i + 1 for i in outidx}; gfill = {(i + 1, j + 1): col_ for (i, j), col_ in (v.get("cfills") or {}).items()}
    nf_, bf_, n_, bad = PL.independent_pipeline_check(dv, outidx, list(range(W)), rr, gfill, pos, set(), [S.disp(x) for x in rr[0]], True, S.to_num, S.to_date, S.blank)
    bad = bad + bf_
    if bad: mis += 1; bad_ex.append((json.dumps(ops, ensure_ascii=False)[:400], bad[:2]))
print("SO SÁNH QUY TẮC: %d bộ ngẫu nhiên, %d hợp lệ, %d lệch, %.1fs" % (tot, ok_, mis, time.time() - t0)); [print("  ✗", m) for m in bad_ex[:4]]
# ---- hiệu năng ----
if os.environ.get("DATADESK_FAST"): sys.exit(1 if (fails or mis) else 0)
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["A", "B", "C"]); rr_ = random.Random(1)
for i in range(50000): ws.append([rr_.randint(1, 100), rr_.choice([100, 2500.5, 7]), rr_.choice(["x", "y", "zz"])])
b = io.BytesIO(); wb.save(b); b.seek(0); sid = c.post("/api/analyze", data={"file": (b, "big.xlsx")}, content_type="multipart/form-data", headers=H_).get_json()["id"]
t0 = time.time()
for nm, w_, th in [("r1", C("A", ">", "50"), [SV("Nhóm", "Cao")]), ("r2", C("C", "in", "x;y"), [MK("XY")]), ("r3", C("B", "is_duplicate"), [COL("#FF0000")])]:
    assert post("/api/rule/apply", rule={"name": nm, "when": {"items": [w_]}, "then": th}, confirm=True)["success"]
t1 = time.time(); r = c.post("/api/process", json=dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": 3, "dir": "asc"}]), headers=H_).get_json()
print("HIỆU NĂNG 50.000 dòng: áp dụng 3 quy tắc %.1fs, xuất + kiểm tra độc lập %.1fs, ok=%s" % (t1 - t0, time.time() - t1, r["ok"]), [k["t"][:14] for k in r["checks"] if not k["ok"]])
sys.exit(1 if (fails or mis or not r["ok"]) else 0)
