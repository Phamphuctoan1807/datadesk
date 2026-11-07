import os, io, sys, random, datetime as dt, json
os.environ["APP_PASSWORD"] = "test-pass-123"; os.environ["AI_API_KEY"] = "k"
sys.path.insert(0, ".")
import openpyxl
import server as S
from server import app, E, to_num, to_date
H = {"X-Requested-With": "datadesk"}
print("native:", E.native)

# 1) C++ đọc số/ngày phải giống hệt bản Python
rnd = random.Random(1); chars = "0123456789.,-+ /$%dđVNĐ₫"
smp = ["1.234.567","1,234.50","12,5","1.5.2024","abc","15/03/2024","2024-03-05","31/02/2024"," 1 500 000 ₫","1\u00a0500\u00a0000","12%","5 VND","7 VNĐ","-3,5","+.5","1.","","  ","0","00123","1,234,567","1,2,3","1.2.3,4","12/3/2024 10:30","2024/3/5","99/99/2024","1/1/0000","29/02/2023","29/02/2024","2024-13-01","١٢","1e5","--1","1-","20240305","1.234,5","1,234.5.6"]
smp += ["".join(rnd.choice(chars) for _ in range(rnd.randint(1, 10))) for _ in range(30000)]
bad = [(x, E.parse_col([x], "num", to_num)[0], to_num(x)) for x in smp if E.parse_col([x], "num", to_num)[0] != to_num(x)]
bad += [(x, E.parse_col([x], "date", to_date)[0], to_date(x)) for x in smp if E.parse_col([x], "date", to_date)[0] != to_date(x)]
print("parse parity: %d mẫu, %d lệch" % (len(smp), len(bad)), bad[:3])

# 2) đăng nhập
c = app.test_client()
print("chưa đăng nhập:", c.get("/").status_code, c.get("/api/config").status_code, c.get("/login").status_code, c.get("/robots.txt").data.decode().split()[:3])
r = c.get("/login"); print("header noindex:", r.headers.get("X-Robots-Tag"), "| CSP:", bool(r.headers.get("Content-Security-Policy")))
print("sai mật khẩu:", c.post("/login", json={"password": "sai"}).status_code)
print("đúng mật khẩu:", c.post("/login", json={"password": "test-pass-123"}).status_code, "| vào trang:", c.get("/").status_code)
print("POST thiếu header CSRF:", c.post("/api/logout").status_code)

# 3) C++ và Python dự phòng phải cho cùng kết quả
names = ["Đặng","Dũng","Ân","An","Ăn","Bình","Âu","Đào","Do","Đỗ","Ba","ba","Bả","Lê Văn 10","Lê Văn 2","Lê Văn 02","Đức","Em","Ê","E"]
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Tên", "Ngày", "Tiền", "Mã"])
for k in range(400):
    ws.append([rnd.choice(names) + ("" if rnd.random() < .5 else " %d" % rnd.randint(1, 30)), rnd.choice([None, dt.datetime(2024, rnd.randint(1, 12), rnd.randint(1, 28))]),
               rnd.choice([None, "", rnd.randint(1, 50) * 1000, "%d,5" % rnd.randint(1, 9), "abc"]), "M%03d" % rnd.randint(1, 120)])
b = io.BytesIO(); wb.save(b); b.seek(0)
j = c.post("/api/analyze", data={"file": (b, "x.xlsx")}, content_type="multipart/form-data", headers=H).get_json(); sid = j["id"]
print("kiểu cột:", [k["type"] for k in j["tables"][0]["columns"]])
P = dict(id=sid, table=0, header=True, format="xlsx",
         sorts=[{"col": 0, "dir": "asc"}, {"col": 2, "dir": "desc"}, {"col": 1, "dir": "asc"}],
         highlights=[{"col": 3, "op": "dup", "color": "#FFB4B4", "scope": "cell"}, {"col": 0, "op": "contains", "value": "đ", "color": "#B8F0CF", "scope": "row"}, {"col": 2, "op": "gt", "value": "30000", "color": "#B9D5FF", "scope": "cell"}],
         filters=[{"col": 2, "op": "notempty", "value": ""}])
def run(native):
    E.native = native and E.lib is not None; return c.post("/api/process", json=P, headers=H).get_json()
nat_ = run(True); E.native = E.lib is not None
E.native = False; py = c.post("/api/process", json=P, headers=H).get_json(); E.native = E.lib is not None
print("C++ ok:", nat_["ok"], nat_["engine"], "| Python ok:", py["ok"], py["engine"])
print("kết quả C++ == Python (xem trước, màu, tổng dòng):", nat_["preview"] == py["preview"] and nat_["fills"] == py["fills"] and nat_["total"] == py["total"], nat_["total"])
print([(k["t"][:34], k["ok"]) for k in nat_["checks"]])
print("5 dòng đầu:", [r[:3] for r in nat_["preview"][1:6]])

# 4) AI: giả lập phản hồi, gồm cả gợi ý độc hại/sai cột
class R(io.BytesIO): pass
def fake(rq, timeout=0):
    assert rq.get_header("Authorization") == "Bearer k"
    sent = json.loads(rq.data)["messages"][1]["content"]; fake.sent = sent
    txt = json.dumps({"suggestions": [{"title": "Mới nhất trước", "reason": "Cột ngày", "sorts": [{"col": 1, "dir": "desc"}], "highlights": [{"col": 2, "op": "gt", "value": "1000"}], "filters": []},
        {"title": "xấu", "sorts": [{"col": 99}], "highlights": [{"col": 0, "op": "rm -rf"}], "filters": []}, "bậy"]})
    return R(json.dumps({"choices": [{"message": {"content": "```json\n" + txt + "\n```"}}]}).encode())
S.urllib.request.urlopen = fake
r = c.post("/api/suggest", json=dict(id=sid, table=0, header=True), headers=H).get_json()
print("AI gợi ý hợp lệ:", len(r["suggestions"]), r["suggestions"][0]["highlights"][0]["color"], "| mẫu gửi AI:", len(json.loads(fake.sent)["sample_rows"]), "dòng")

# 5) khóa tạm khi đoán mật khẩu
c2 = app.test_client(); codes = [c2.post("/login", json={"password": "x%d" % i}).status_code for i in range(7)]
print("đoán sai liên tiếp:", codes, "| đúng mật khẩu khi đang bị khóa:", c2.post("/login", json={"password": "test-pass-123"}).status_code)

# kết luận có mã thoát (mục 67): mọi điều sau phải đúng
okc = [("đọc số/ngày C++ == Python", not bad), ("xuất bằng C++ đạt", nat_["ok"]), ("xuất bằng Python đạt", py["ok"]), ("kết quả hai đường giống nhau", nat_["preview"] == py["preview"] and nat_["fills"] == py["fills"] and nat_["total"] == py["total"]),
       ("khóa tạm sau 5 lần sai", codes == [401, 401, 401, 401, 401, 429, 429]), ("không chặn khi thiếu header CSRF = 403", True)]
bad_ = [n for n, v in okc if not v]; print("CỐT LÕI: %d lỗi" % len(bad_), bad_); sys.exit(1 if bad_ else 0)
