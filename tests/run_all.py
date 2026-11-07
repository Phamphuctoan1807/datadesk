"""Chạy toàn bộ bộ kiểm thử và in bảng tổng hợp (mục 67: hồi quy). Chạy từ thư mục dự án: python tests/run_all.py
Thêm --fast để bỏ qua phần đo hiệu năng 50.000 dòng."""
import os, sys, subprocess, time
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
env = dict(os.environ); 
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
if "--fast" in sys.argv: env["DATADESK_FAST"] = "1"
names = ["test_units", "test_golden", "test_formula", "test_rules", "test_pipeline", "test_normalize", "test_schema", "test_merge_api", "test_integration", "test_core", "test_ui"]; res = []
for n in names:
    t0 = time.time(); p = subprocess.run([sys.executable, os.path.join("tests", n + ".py")], cwd=root, env=env, capture_output=True, text=True)
    last = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()][-1:] or [""]
    res.append((n, p.returncode, time.time() - t0, last[0][:90]))
print("\n%-18s %-6s %6s  %s" % ("Bộ kiểm thử", "Kết quả", "Giây", "Dòng cuối"))
for n, rc, dt_, last in res: print("%-18s %-6s %6.1f  %s" % (n, "ĐẠT" if rc == 0 else "SAI", dt_, last))
bad = [n for n, rc, _, _ in res if rc != 0]; print("\nTỔNG: %d/%d bộ đạt%s" % (len(res) - len(bad), len(res), "" if not bad else ". CẦN XEM: " + ", ".join(bad))); sys.exit(1 if bad else 0)
