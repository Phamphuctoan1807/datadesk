"""Bộ kiểm thử "đáp án chuẩn" (mục 66 của lộ trình): mỗi tệp trong tests/golden có dữ liệu vào, các bước và kết quả mong đợi (ô, màu, cảnh báo, lỗi)."""
import os, sys, json, glob, datetime as dt
os.environ["APP_PASSWORD"] = "t"; sys.path.insert(0, ".")
import server as S, pipeline as PL
here = os.path.dirname(os.path.abspath(__file__)); fails = []; n = 0
for path in sorted(glob.glob(os.path.join(here, "golden", "*.json"))):
    g = json.load(open(path, encoding="utf8")); name = os.path.basename(path)[:-5]; n += 1; ds = g["dataset"]
    t = S.parse(ds, open(os.path.join(here, "datasets", ds), "rb").read())[0]; d = S.derive_table(t, g["ops"], g.get("numfmt", "auto")); e = g["expect"]
    if d["errors"]: fails.append((name, "bước bị từ chối", d["errors"][0]["message"])); continue
    rows = d["view"]["rows"]; hdr = rows[0]
    if "columns" in e and hdr != e["columns"]: fails.append((name, "cột", hdr, e["columns"]))
    for c in e.get("cells", []):
        v = rows[c["row"] - 1][hdr.index(c["col"])]; v = v.date().isoformat() if isinstance(v, dt.datetime) else v
        if v != c["value"]: fails.append((name, "ô %d/%s" % (c["row"], c["col"]), v, c["value"]))
    for f in e.get("fills", []):
        v = (d["view"].get("cfills") or {}).get((f["row"] - 1, f["col"]))
        if v != f["color"]: fails.append((name, "màu %d/%d" % (f["row"], f["col"]), v, f["color"]))
    if "warnings" in e and len(d["warnings"]) != e["warnings"]: fails.append((name, "số cảnh báo", d["warnings"], e["warnings"]))
    for w in e.get("warnings_contain", []):
        if not any(w in x for x in d["warnings"]): fails.append((name, "thiếu cảnh báo", w, d["warnings"]))
    for oid, ec in e.get("errors", {}).items():
        if d["stats"][oid]["errors"] != ec: fails.append((name, "số lỗi " + oid, d["stats"][oid]["errors"], ec))
    v = d["view"]; rr = v["rows"]; gfill = {(i + 1, j + 1): col for (i, j), col in (v.get("cfills") or {}).items()}
    nf, bf, nr, br = PL.independent_pipeline_check(v["derived"], list(range(len(rr))), list(range(len(rr[0]))), rr, gfill, {i: i + 1 for i in range(len(rr))}, set(), [S.disp(x) for x in rr[0]], True, S.to_num, S.to_date, S.blank)
    if bf or br: fails.append((name, "bộ kiểm tra độc lập báo lệch", (bf + br)[:2]))
    print("  %s %s" % ("✓" if not [f for f in fails if f[0] == name] else "✗", name))
print("ĐÁP ÁN CHUẨN: %d bộ, %d sai lệch" % (n, len(fails))); [print("  ✗", f) for f in fails[:12]]
sys.exit(1 if fails else 0)
