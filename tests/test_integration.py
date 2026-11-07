import os, io, sys, json, time, copy, datetime as dt
os.environ["APP_PASSWORD"] = "t"; os.environ["AI_API_KEY"] = ""; sys.path.insert(0, ".")
import openpyxl, server as S
H = {"X-Requested-With": "datadesk"}; fails = []
def chk(n, got, exp=True):
    if got != exp: fails.append((n, got, exp))
c = S.app.test_client()
chk("chưa đăng nhập: formula", c.post("/api/formula/preview", json={}, headers=H).status_code, 401)
c.post("/login", json={"password": "t"})
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Don"
ws.append(["Mã", "Số lượng", "Đơn giá", "Điểm", "Ngày", "Ghi chú"])
data = [["A1", 5, 20000, 4, dt.datetime(2026, 1, 31), ""], ["A2", 10, 25000, 6, dt.datetime(2026, 2, 28), "ok"], ["A3", 0, 1000, 9, dt.datetime(2026, 3, 5), None],
        ["A4", 3, 1500.5, 8.5, None, "x"], ["A5", "ba", 100, 7, dt.datetime(2026, 4, 1), ""], ["A6", 7, 300, 2, dt.datetime(2026, 5, 9), ""]]
for r in data: ws.append(r)
for r in range(2, 8): ws.cell(r, 5).number_format = "dd/mm/yyyy"
b = io.BytesIO(); wb.save(b); b.seek(0)
j = c.post("/api/analyze", data={"file": (b, "t.xlsx")}, content_type="multipart/form-data", headers=H).get_json(); sid = j["id"]
orig = copy.deepcopy(S.STORE[sid]["tables"][0]["rows"]); N0 = len(j["tables"][0]["columns"])
def fp(path, **k):
    p = dict(id=sid, table=0, header=True); p.update(k); r = c.post(path, json=p, headers=H); return r.get_json()
def state(): return c.get("/api/transform/state?id=%s&t=0" % sid).get_json()["data"]
# xem trước, lỗi, header
r = fp("/api/formula/preview", target="Thành tiền", expression="Số lượng * Đơn giá"); chk("preview ok", r["success"]); chk("preview dòng", r["data"]["rows"][0], ["5", "20000", "100000"]); chk("preview cột", r["data"]["columns"], ["Số lượng", "Đơn giá", "Thành tiền"])
chk("cảnh báo ô chữ trong cột số", any("không thể đọc thành số" in w for w in r["warnings"]), True); chk("đếm lỗi kiểu", r["data"]["error_counts"], {"ERROR_TYPE": 1})
r = fp("/api/formula/preview", target="X", expression="[Giá]*2"); chk("cột không có", (r["success"], r["errors"][0]["code"]), (False, "ERROR_COLUMN"))
r = fp("/api/formula/preview", target="X", expression="1", header=False); chk("cần header", r.get("error", "").startswith("Công thức cần dòng tiêu đề"), True)
chk("preview không lưu", len(state()["list"]), 0)
# áp dụng ba công thức phụ thuộc nhau
for t, e in [("Thành tiền", "[Số lượng] * [Đơn giá]"), ("Đánh giá", 'IF(Điểm<5,"Yếu",IF(Điểm<8,"Khá","Giỏi"))'), ("Gấp đôi", "[Thành tiền] * 2"), ("Hạn", "[Ngày] + 30")]:
    r = fp("/api/formula/apply", target=t, expression=e); chk("apply " + t, r["success"], True)
chk("số công thức", [o["target"] for o in state()["list"]], ["Thành tiền", "Đánh giá", "Gấp đôi", "Hạn"])
chk("dữ liệu gốc bất biến", S.STORE[sid]["tables"][0]["rows"], orig)
t = c.get("/api/table?id=%s&t=0&header=0" % sid).get_json(); chk("bảng có cột mới (header ép bật)", [x["name"] for x in t["columns"]][N0:], ["Thành tiền", "Đánh giá", "Gấp đôi", "Hạn"]); chk("kiểu cột mới", [x["type"] for x in t["columns"]][N0:], ["number", "text", "number", "date"])
pg = c.get("/api/rows?id=%s&t=0&start=1&n=3" % sid).get_json(); chk("trang dữ liệu có cột mới", pg["rows"][0][N0:], ["100000", "Yếu", "200000", "02/03/2026"])
# xuất: sắp theo cột mới, tô màu theo cột mới, kiểm tra độc lập
P = dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": N0, "dir": "desc"}], highlights=[{"col": N0 + 1, "op": "contains", "value": "Yếu", "color": "#FFB4B4", "scope": "row"}])
r = c.post("/api/process", json=P, headers=H).get_json(); chk("process ok", r["ok"], True); names = [k["t"] for k in r["checks"]]; chk("có bước kiểm tra công thức", "Công thức khớp bản tính độc lập" in names, True); chk("mọi bước đạt", [k["t"] for k in r["checks"] if not k["ok"]], [])
w = openpyxl.load_workbook(io.BytesIO(c.get("/api/download/" + r["token"]).data)).active
rows = [[x.value for x in row] for row in w.iter_rows(min_row=1, max_row=7)]
chk("tiêu đề xuất", rows[0][N0:], ["Thành tiền", "Đánh giá", "Gấp đôi", "Hạn"]); vals = [x[N0] for x in rows[1:] if isinstance(x[N0], (int, float))]; chk("thứ tự số giảm dần", vals, sorted(vals, reverse=True))
chk("ô lỗi hiện mã lỗi", "ERROR_TYPE" in [x[N0] for x in rows[1:]], True); chk("hạn là ngày", isinstance(rows[1][N0 + 3], dt.datetime) or rows[1][N0 + 3] is None, True)
chk("dòng Yếu có màu", [str(w.cell(i + 2, 1).fill.fgColor.rgb)[-6:] for i, x in enumerate(rows[1:]) if x[N0 + 1] == "Yếu"][0], "FFB4B4")
r = c.post("/api/process", json=dict(P, format="csv"), headers=H).get_json(); chk("csv ok có kiểm tra công thức", (r["ok"], "Công thức khớp bản tính độc lập" in [k["t"] for k in r["checks"]]), (True, True))
r = c.post("/api/process", json=dict(P, columns=[0, 1, N0 + 2]), headers=H).get_json(); chk("xuất một phần cột", r["ok"], True)
r = c.post("/api/process", json=dict(P, columns=[0, 1]), headers=H).get_json(); chk("không xuất cột công thức: bỏ qua bước", "Công thức khớp bản tính độc lập" in [k["t"] for k in r["checks"]], False)
# chia cho 0 hiển thị lỗi, vẫn xuất được
r = fp("/api/formula/apply", target="Tỷ lệ", expression="[Đơn giá]/[Số lượng]"); chk("apply chia 0 cho phép", r["success"], True); chk("thống kê lỗi", state()["list"][-1]["stats"]["errors"], {"ERROR_DIV_ZERO": 1, "ERROR_TYPE": 1})
r = c.post("/api/process", json=P, headers=H).get_json(); chk("xuất khi có ô lỗi", r["ok"], True)
# vòng, xóa cột đang được dùng, hoàn tác
r = fp("/api/formula/apply", target="Vòng", expression="[Vòng2]+1"); chk("công thức vòng bị chặn", r["success"], False)
r = fp("/api/formula/apply", target="Vòng2", expression="[Gấp đôi]+1"); chk("thêm Vòng2 ok", r["success"], True)
r = fp("/api/formula/apply", target="Gấp đôi", expression="[Vòng2]", op_id=state()["list"][2]["id"]); chk("sửa gây vòng bị chặn", (r["success"], r["errors"][0]["code"]), (False, "CIRCULAR_DEPENDENCY"))
r = fp("/api/transform/update", action="delete", op_id=state()["list"][0]["id"]); chk("xóa cột đang được dùng bị chặn", (r["success"], r["errors"][0]["code"]), (False, "ERROR_COLUMN"))
n = len(state()["list"]); r = fp("/api/transform/undo"); chk("hoàn tác", (r["success"], len(r["data"]["list"])), (True, n - 1)); r = fp("/api/transform/redo"); chk("làm lại", (r["success"], len(r["data"]["list"])), (True, n))
r = fp("/api/transform/update", action="toggle", op_id=state()["list"][-1]["id"]); chk("tắt công thức cuối (Vòng2)", r["success"], True)
r = fp("/api/transform/update", action="move_up", op_id=state()["list"][1]["id"]); chk("đổi thứ tự", (r["success"], state()["list"][0]["target"]), (True, "Đánh giá"))
r = fp("/api/transform/update", action="toggle", op_id=state()["list"][1]["id"]); chk("tắt công thức đang được dùng bị chặn", r["success"], False)
while state()["can_undo"]: fp("/api/transform/undo")
chk("hoàn tác hết về bảng gốc", (len(state()["list"]), len(c.get("/api/table?id=%s&t=0&header=1" % sid).get_json()["columns"])), (0, N0)); chk("dữ liệu gốc vẫn bất biến", S.STORE[sid]["tables"][0]["rows"], orig)
chk("hoàn tác khi hết", fp("/api/transform/undo")["success"], False)
r = c.post("/api/process", json=dict(P, sorts=[], highlights=[]), headers=H).get_json(); chk("xuất bảng gốc không công thức", r["ok"], True)
print("TÍCH HỢP: %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:12]]
# hiệu năng: 50.000 dòng, 3 công thức
if os.environ.get("DATADESK_FAST"): sys.exit(1 if fails else 0)
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["A", "B", "C"])
import random; rnd = random.Random(1)
for i in range(50000): ws.append([rnd.randint(1, 100), rnd.choice([100, 2500.5, 7]), rnd.choice(["x", "y", "zz"])])
b = io.BytesIO(); wb.save(b); b.seek(0)
j = c.post("/api/analyze", data={"file": (b, "big.xlsx")}, content_type="multipart/form-data", headers=H).get_json(); sid = j["id"]
t0 = time.time()
for t, e in [("T", "A*B"), ("U", 'IF(T>5000,"cao","thấp")'), ("V", "ROUND(T/3,2)")]: assert fp("/api/formula/apply", target=t, expression=e)["success"]
t1 = time.time(); r = c.post("/api/process", json=dict(id=sid, table=0, header=True, format="xlsx", sorts=[{"col": 3, "dir": "desc"}]), headers=H).get_json()
print("HIỆU NĂNG 50.000 dòng: áp dụng 3 công thức %.1fs, xuất + kiểm tra độc lập %.1fs, ok=%s, kiểm tra: %s" % (t1 - t0, time.time() - t1, r["ok"], [k["ok"] for k in r["checks"]]))

sys.exit(1 if (fails or not r["ok"]) else 0)
