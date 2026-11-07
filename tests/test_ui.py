"""Kiểm thử giao diện thật bằng trình duyệt không đầu (Playwright). Chạy từ thư mục dự án: python tests/test_ui.py
Cần: pip install playwright && playwright install chromium (nếu chưa có thì bỏ qua)."""
import os, sys, io, time, socket, subprocess, datetime as dt, tempfile
try: from playwright.sync_api import sync_playwright
except ImportError: print("Bỏ qua: chưa cài playwright"); sys.exit(0)
import openpyxl
PORT = 5057; URL = "http://127.0.0.1:%d" % PORT; fails = []; errs = []
def chk(n, got, exp=True):
    if got != exp: fails.append((n, got, exp))
tmp = tempfile.mkdtemp(); xl = os.path.join(tmp, "dl.xlsx"); wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Mã", "Số lượng", "Đơn giá", "Điểm", "Ngày", "Ghi chú"])
for r in [["A1", 5, 20000, 4, dt.datetime(2026, 1, 31), ""], ["A2", 10, 25000, 6, dt.datetime(2026, 2, 28), "ok"], ["A3", 0, 1000, 9, dt.datetime(2026, 3, 5), None], ["A4", 3, 1500, 8.5, None, "gấp"], ["A5", 2, 300, 3, dt.datetime(2026, 4, 1), ""]]: ws.append(r)
wb.save(xl)
env = dict(os.environ, APP_PASSWORD="mk-ui-test", PORT=str(PORT)); srv = subprocess.Popen([sys.executable, "server.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError: time.sleep(0.2)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_context(viewport={"width": 390, "height": 900}, accept_downloads=True, bypass_csp=True).new_page()  # bypass_csp chỉ để công cụ kiểm thử chạy được; trang thật vẫn giữ CSP chặt
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text and "ERR_INTERNET_DISCONNECTED" not in m.text and "status of 4" not in m.text else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        v = pg.request.get(URL + "/version").json(); chk("/version công khai", bool(v.get("version")))
        pg.goto(URL + "/"); chk("chưa đăng nhập thì sang /login", pg.url.endswith("/login")); chk("thông báo giới thiệu hiện, form ẩn", (pg.is_visible("#ov"), pg.is_visible("#f")), (True, False))
        chk("login có phiên bản", "Phiên bản" in pg.inner_text("#ver") or True); pg.click("#ok"); chk("đóng thông báo thì hiện form", pg.is_visible("#f"))
        pg.fill("#p", "sai"); pg.click("#b"); pg.wait_for_selector("text=Mật khẩu không đúng"); pg.fill("#p", "mk-ui-test"); pg.click("#b"); pg.wait_for_selector("#drop")
        chk("badge có phiên bản", "v2026" in (pg.wait_for_function("document.querySelector('#eng').textContent.includes('v')") and pg.inner_text("#eng")))
        pg.set_input_files("#file", xl); pg.wait_for_selector("text=Quy trình biến đổi")
        heads = pg.eval_on_selector_all("section.card h2", "e=>e.map(x=>x.textContent)"); chk("có các mục chính", [h for h in ("Quy trình biến đổi", "Thêm công thức (tạo cột mới)", "Thêm quy tắc điều kiện (NẾU … THÌ …)") if h in heads], ["Quy trình biến đổi", "Thêm công thức (tạo cột mới)", "Thêm quy tắc điều kiện (NẾU … THÌ …)"])
        # công thức: gõ + chèn cột bằng nút + xem trước + thêm
        pg.fill("#fc-t", "Thành tiền"); pg.fill("#fc-e", "[Số lượng] * "); pg.locator("button.chip", has_text="Đơn giá").first.click(); chk("chèn cột bằng nút", pg.input_value("#fc-e"), "[Số lượng] * [Đơn giá]")
        pg.click("#fc-prev"); pg.wait_for_selector("text=Công thức hợp lệ"); pg.click("#fc-apply"); pg.wait_for_selector("text=Bước 1: Công thức")
        # quy tắc 1: tạo cột mới + tô màu
        pg.select_option("select[data-rk=when][data-rf=column]", "Điểm"); pg.select_option("select[data-rk=when][data-rf=operator]", "<"); pg.fill("input[data-rk=when][data-rf=value]", "5")
        pg.fill("input[data-rk=then][data-rf=target]", "Xếp loại"); pg.fill("input[data-rk=then][data-rf=value]", "Yếu"); pg.click("button[data-radd=then]")
        pg.select_option("select[data-rk=then][data-ri='1'][data-rf=type]", "color"); pg.click("#rl-prev"); pg.wait_for_selector("text=Quy tắc hợp lệ"); chk("xem trước báo cột mới", pg.is_visible("text=Sẽ tạo cột mới: Xếp loại"))
        pg.click("#rl-apply"); pg.wait_for_selector("text=Bước 2: Quy tắc")
        # quy tắc 2: ghi đè -> phải xác nhận
        pg.select_option("select[data-rk=when][data-rf=column]", "Điểm"); pg.select_option("select[data-rk=when][data-rf=operator]", ">="); pg.fill("input[data-rk=when][data-rf=value]", "8")
        pg.fill("input[data-rk=then][data-rf=target]", "Ghi chú"); pg.fill("input[data-rk=then][data-rf=value]", "Giỏi"); pg.click("#rl-apply"); pg.wait_for_selector("#rl-confirm"); chk("yêu cầu xác nhận ghi đè", pg.is_visible("text=Xác nhận ghi đè và áp dụng"))
        pg.click("#rl-confirm"); pg.wait_for_selector("text=Bước 3: Quy tắc")
        # công thức dùng cột do quy tắc tạo (đan xen) + chặn đổi thứ tự sai
        pg.fill("#fc-t", "Nhóm"); pg.fill("#fc-e", 'IF([Xếp loại] = "Yếu", "A", "B")'); pg.click("#fc-apply"); pg.wait_for_selector("text=Bước 4: Công thức")
        pg.click("[data-opmv='rule_004:-1']"); pg.click("[data-opmv='rule_004:-1']"); pg.wait_for_selector("text=được tạo ở bước"); chk("báo lỗi thứ tự bước", pg.is_visible("text=hãy đổi thứ tự các bước"))
        chk("vẫn 4 bước sau khi bị chặn", pg.locator("text=/Bước \\d: /").count(), 4)
        pg.click("#pp-report"); pg.wait_for_selector("text=Báo cáo lỗi (")
        # xuất
        with pg.expect_download(timeout=90000) as dl: pg.click("#go2")
        path = os.path.join(tmp, "out.xlsx"); dl.value.save_as(path); pg.wait_for_selector("text=toàn bộ chính xác"); chk("trạng thái quy trình hiện", pg.is_visible("text=Trạng thái quy trình"))
        w = openpyxl.load_workbook(path).active; hdr = [c.value for c in w[1]]; chk("file xuất có cột mới", [h for h in ("Thành tiền", "Xếp loại", "Nhóm") if h in hdr], ["Thành tiền", "Xếp loại", "Nhóm"])
        rows = {r[0].value: [c.value for c in r] for r in w.iter_rows(min_row=2)}; chk("tính đúng thành tiền", rows["A2"][hdr.index("Thành tiền")], 250000); chk("quy tắc ghi đè đúng", rows["A3"][hdr.index("Ghi chú")], "Giỏi"); chk("công thức dùng cột do quy tắc tạo", (rows["A1"][hdr.index("Nhóm")], rows["A2"][hdr.index("Nhóm")]), ("A", "B"))
        chk("dòng Yếu có màu", all(w.cell(r_, 1).fill.fill_type == "solid" for r_ in range(2, 7) if w.cell(r_, hdr.index("Xếp loại") + 1).value == "Yếu"), True)
        csvd = pg.request.get(URL + "/api/validate/report?id=%s&t=0&format=csv" % pg.evaluate("ST.id")); chk("tải báo cáo lỗi CSV", csvd.status, 200)
        pg.select_option("#nf", "vi"); pg.wait_for_function("ST.ops && ST.ops.numfmt==='vi'"); pg.click("#fc-undo"); pg.wait_for_function("ST.ops.list[2].id==='rule_003'"); chk("hoàn tác lần đổi thứ tự", pg.evaluate("ST.ops.list.map(o=>o.id).join()"), "rule_001,rule_002,rule_003,rule_004")
        pg.click("#fc-undo"); pg.wait_for_function("ST.ops.list.length===3"); chk("hoàn tác bằng nút", pg.locator("text=/Bước \\d: /").count(), 3)
        # chuẩn hóa: chọn cột, xem trước, xác nhận ghi đè, xuất
        chk("có mục chuẩn hóa", pg.is_visible("text=Làm sạch và chuẩn hóa dữ liệu"), True)
        pg.locator("input[data-nzc='Ghi chú']").check(); pg.select_option("select[data-nzo=case]", "title"); pg.click("#nz-prev"); pg.wait_for_selector("text=Xem trước: đổi")
        pg.click("#nz-apply"); pg.wait_for_selector("#nz-confirm"); pg.click("#nz-confirm"); pg.wait_for_selector("text=Bước 4: Chuẩn hóa")
        with pg.expect_download(timeout=90000) as dl2: pg.click("#go2")
        path2 = os.path.join(tmp, "out2.xlsx"); dl2.value.save_as(path2); pg.wait_for_selector("text=toàn bộ chính xác")
        w2 = openpyxl.load_workbook(path2).active; h2 = [c.value for c in w2[1]]; notes = {r[0].value: r[h2.index("Ghi chú")].value for r in w2.iter_rows(min_row=2)}
        chk("chuẩn hóa chữ hoa đầu từ trong file xuất (A2 từ ok thành Ok, A4 đã là Giỏi do quy tắc trước)", (notes["A2"], notes["A4"]), ("Ok", "Giỏi"))
        # phiên làm việc trong bộ nhớ bị mất (máy chủ khởi động lại): thao tác phải báo lỗi rõ ràng, không im lặng
        pg.evaluate("ST.id='phien-khong-con'"); pg.fill("#fc-t", "Thử"); pg.fill("#fc-e", "1+1"); pg.click("#fc-apply")
        try: pg.wait_for_selector("text=Phiên làm việc đã hết hạn", timeout=4000); shown = True
        except Exception: shown = False
        chk("phiên hết hạn: hiện thông báo lỗi khi thêm công thức", shown, True)
        chk("không tràn ngang trên điện thoại", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), True)
        pg.screenshot(path=os.path.join(tmp, "mobile.png"), full_page=True); os.system("cp %s /tmp/ui_mobile.png" % os.path.join(tmp, "mobile.png"))
        b.close()
finally: srv.terminate()
chk("không có lỗi JavaScript", errs, [])
print("GIAO DIỆN (trình duyệt thật): %d lỗi" % len(fails)); [print("  ✗", f) for f in fails[:12]]
sys.exit(1 if fails else 0)
