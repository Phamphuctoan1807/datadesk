"""Quy trình biến đổi (Giai đoạn 1 đến 3): các bước (công thức, quy tắc điều kiện) chạy lần lượt theo thứ tự người dùng sắp xếp.
Mô hình: bảng gốc bất biến + nhật ký thao tác -> bảng dẫn xuất. Bộ kiểm tra độc lập (independent_pipeline_check) chạy lại cả quy trình
bằng bộ tính Decimal riêng từ dữ liệu gốc và so với giá trị, màu đọc lại từ file đã xuất."""
import re, datetime as dt
from collections import Counter
from decimal import localcontext, Context
import formula as F, rules as RL

def ctype_of(vals):
    v = [x for x in vals if x != "" and not (isinstance(x, str) and x.startswith("ERROR_"))]
    if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v): return "number"
    if v and all(isinstance(x, dt.datetime) for x in v): return "date"
    return "text"

def _later_targets(ops):
    """Tên cột sẽ được tạo ở từng bước, để báo lỗi dễ hiểu khi công thức dùng cột được tạo ở bước sau."""
    out = {}
    for k, o in enumerate(ops):
        if o.get("type", "FORMULA") == "FORMULA": out.setdefault(F.norm(o.get("target", "")), k + 1)
        else:
            for a in (o.get("then") or []) + (o.get("else") or []):
                if a.get("type") in ("set_value", "mark", "add_to_list") and a.get("target"): out.setdefault(F.norm(a["target"]), k + 1)
    return out

def run_pipeline(t, ops, numfmt, env):
    ops = [o for o in ops if o.get("enabled", True)]
    other = [o for o in ops if o.get("type", "FORMULA") not in ("FORMULA", "CONDITIONAL")]
    if other: return {"errors": [{"code": "UNSUPPORTED_OP", "message": "Loại biến đổi %s chưa được hỗ trợ." % other[0].get("type"), "op_id": other[0].get("id")}]}
    detect, pn, pd, to_num, to_date, disp = (env[k] for k in ("detect", "pn", "pd", "to_num", "to_date", "disp"))
    rows0 = t["rows"]; W0 = len(rows0[0]); body0 = rows0[1:]; n = len(body0)
    names0 = [disp(x).strip() or "Cột %d" % (c + 1) for c, x in enumerate(rows0[0])]
    types0 = [detect([r[c] for r in body0]) for c in range(W0)]
    rows = [list(r) for r in rows0]; names = list(names0); ctypes = list(types0); protected = set()
    T, INFO, warned, stats, warnings, errlog, events, steps, fmt_cols, refs, fcols = {}, {}, set(), {}, [], [], [], [], {}, {}, []
    def typed(c):  # giá trị có kiểu của cột c, tính từ dữ liệu GỐC rồi được các bước vá dần
        if c not in T: T[c], INFO[c] = F.typed_column([r[c] for r in body0], ctypes[c], pn, pd, numfmt)
        return T[c]
    def typed_for_formula(c):  # như typed, kèm cảnh báo theo trạng thái ngay tại bước công thức (sau khi các bước làm sạch phía trên đã chạy)
        lst = typed(c)
        if c < W0 and c not in warned:
            nm = names0[c]; strs = [v for v in lst if isinstance(v, str)]
            if ctypes[c] in ("number", "date") and strs:
                warned.add(c); amb = sum(1 for v in strs if F.AMB.fullmatch(F._CUR.sub("", v))) if ctypes[c] == "number" else 0
                if amb: warnings.append('Cột "%s" có %d giá trị dạng 1.234 hoặc 1,234 chưa rõ là 1234 hay 1,234 nên CHƯA được đọc thành số (báo ERROR_TYPE khi tính). Hãy chọn "Cách đọc số" ở phần Quy trình biến đổi.' % (nm, amb))
                if len(strs) - amb > 0: warnings.append('Cột "%s" chứa %d giá trị không thể đọc thành %s; các ô đó báo ERROR_TYPE khi dùng trong phép tính.' % (nm, len(strs) - amb, "số" if ctypes[c] == "number" else "ngày"))
            elif ctypes[c] == "text" and strs and any(isinstance(v, float) for v in lst):
                warned.add(c); warnings.append('Cột "%s" vừa có số vừa có chữ: các ô chữ báo ERROR_TYPE khi dùng trong phép tính.' % nm)
        return lst
    later = _later_targets(ops); groups = []
    for k, o in enumerate(ops):
        kind = "formula" if o.get("type", "FORMULA") == "FORMULA" else "rules"
        if groups and groups[-1][0] == kind: groups[-1][1].append(o)
        else: groups.append((kind, [o]))
    for kind, gops in groups:
        if kind == "formula":
            d = F.derive(n, names, gops, typed_for_formula)
            if d["errors"]:
                for e in d["errors"]:
                    m = re.search(r'"([^"]+)"', e["message"])
                    if e["code"] == "ERROR_COLUMN" and m and F.norm(m.group(1)) in later:
                        e["message"] += " Cột này được tạo ở bước %d, sau bước dùng nó: hãy đổi thứ tự các bước." % later[F.norm(m.group(1))]
                return {"errors": d["errors"]}
            for c in d["cols"]:
                j = len(names); rows[0].append(c["target"])
                for i in range(n): rows[i + 1].append(c["values"][i])
                names.append(c["target"]); ctypes.append(ctype_of(c["values"])); T[j] = c["typed"]; protected.add(F.norm(c["target"]))
                fmt_cols[j] = "dd/mm/yyyy" if c["date"] else None; fcols.append({"id": c["id"], "target": c["target"]})
            stats.update(d["stats"]); errlog.extend(d["errlog"]); warnings.extend(d["warnings"]); refs.update(d["refs"])
            steps.append({"kind": "formula", "cols": [{"id": c["id"], "target": c["target"], "ast": c["ast"]} for c in d["cols"]]})
        else:
            meta = {"kind": "rules", "rules": gops, "names": list(names), "ctypes": list(ctypes), "protected": sorted(protected)}
            res = RL.apply_rules(rows, names, ctypes, protected, gops, typed, T, to_num, to_date)
            if res["errors"]:
                for e in res["errors"]:
                    m = re.search(r'cột "([^"]+)" không tồn tại', e["message"])
                    if e["code"] == "ERROR_COLUMN" and m and F.norm(m.group(1)) in later:
                        e["message"] += " Cột này được tạo ở bước %d, sau bước dùng nó: hãy đổi thứ tự các bước." % later[F.norm(m.group(1))]
                return {"errors": res["errors"]}
            names, ctypes = res["names"], res["ctypes"]; events.extend(res["events"]); stats.update(res["stats"]); errlog.extend(res["errlog"]); warnings.extend(res["warnings"]); steps.append(meta)
    W = len(names); fills = {}
    for i, c, col in events:  # quy tắc sau ghi đè màu của quy tắc trước; màu cả dòng phủ mọi cột cuối cùng
        if c == "row":
            for j in range(W): fills[(i, j)] = col
        else: fills[(i, c)] = col
    fm0 = t["fm"] or [[None] * W0 for _ in rows0]; add = W - W0
    FM = [fm0[0] + [None] * add] + [fm0[i + 1] + [fmt_cols.get(j) for j in range(W0, W)] for i in range(n)]
    SF = [t["sf"][i] + [None] * add for i in range(n + 1)] if t.get("sf") else None
    ctf = {j: ctype_of([r[j] for r in rows[1:]]) for j in range(W0, W)}
    view = {"name": t["name"], "dropped": t["dropped"], "rows": rows, "fm": FM, "sf": SF, "cfills": fills,
            "derived": {"W0": W0, "names0": names0, "types0": types0, "ctypes": ctf, "src": rows0, "steps": steps, "numfmt": numfmt}}
    return {"errors": [], "warnings": warnings, "stats": stats, "errlog": errlog, "view": view, "cols": fcols, "refs": refs}

# ---------------- kiểm tra độc lập ----------------
def independent_pipeline_check(dv, outidx, cols, got, gfill, pos, high, final_names, check_colors, to_num, to_date, blank):
    """Chạy lại toàn bộ quy trình từ dữ liệu gốc bằng bộ tính Decimal riêng, rồi so với giá trị và màu đọc lại từ file đã xuất.
    Trả về (số ô công thức đã kiểm, sai lệch công thức, số giá trị/màu quy tắc đã kiểm, sai lệch quy tắc).
    Lưu ý: bước phân tích cú pháp công thức và dịch quy tắc sang cây điều kiện dùng chung với bộ xử lý chính."""
    src, types0, names0, numfmt, steps = dv["src"], dv["types0"], dv["names0"], dv.get("numfmt", "auto"), dv["steps"]
    n = len(src) - 1; byname = {}
    for j in range(len(names0) - 1, -1, -1): byname[F.norm(names0[j])] = j
    state, rawv, fraw, created_set, events = {}, {}, {}, set(), []
    with localcontext(Context(prec=40)):
        def colget(k):
            if k not in state:
                c = byname[k]; state[k] = F.ityped_col([src[i + 1][c] for i in range(n)], types0[c], numfmt, to_num, to_date, blank)
            return state[k]
        def rawcell(k, i):
            if k in created_set: return rawv[k].get(i, "")
            return rawv.get(k, {}).get(i, src[i + 1][byname[k]])
        for st in steps:
            if st["kind"] == "formula":
                asts = {F.norm(c["target"]): c["ast"] for c in st["cols"]}; memos = [dict() for _ in range(n)]
                def fget(i):
                    memo = memos[i]
                    def g(name):
                        k = F.norm(name)
                        if k not in asts: return colget(k)[i]
                        if k not in memo:
                            try: memo[k] = ("v", F.ieval(asts[k], g))
                            except F.Raise as e: memo[k] = ("e", e.code)
                            except ArithmeticError: memo[k] = ("e", "ERROR_OVERFLOW")
                        tag, val = memo[k]
                        if tag == "e": raise F.Raise(val)
                        return val
                    return g
                newcols = {}
                for c in st["cols"]:
                    vals = []
                    for i in range(n):
                        try: vals.append(fget(i)(c["target"]))
                        except F.Raise as e: vals.append(e.code)  # ô công thức lỗi hiện mã lỗi dạng chữ, giống bộ xử lý chính
                    newcols[F.norm(c["target"])] = vals
                for k, vals in newcols.items(): state[k] = vals; fraw[k] = vals
            else:
                try: comp = RL.compile_rules(st["rules"], st["names"], st["ctypes"], set(st["protected"]), to_num, to_date)
                except RL.RuleError as e: return 0, [], 0, ["không dịch lại được quy tắc: " + e.msg]
                for cr in comp:
                    for nm in cr["created"]:
                        k = F.norm(nm); state[k] = [None] * n; rawv[k] = {}; created_set.add(k)
                    pseudo = {}
                    for cname in cr["dupcols"]:
                        col = colget(F.norm(cname)); keys = [None if blank(v) else F.itxt(v).casefold() for v in col]; cnt = Counter(k for k in keys if k is not None)
                        pseudo[RL.DUP + F.norm(cname)] = [k is not None and cnt[k] > 1 for k in keys]
                    flags = []
                    for i in range(n):
                        get = lambda name, i=i: pseudo[name][i] if name in pseudo else colget(F.norm(name))[i]
                        try: v = F.ieval(cr["ast"], get)
                        except (F.Raise, ArithmeticError): v = None
                        flags.append(v if isinstance(v, bool) else None)
                    for i, m in enumerate(flags):
                        for a in ([] if m is None else (cr["then"] if m else cr["else"])):
                            t = a["type"]
                            if t == "color": events.append((i + 1, "row" if a["scope"] == "row" else F.norm(a["target"]), a["color"])); continue
                            k = F.norm(a["target"]); col = colget(k); old = rawcell(k, i); rawv.setdefault(k, {})
                            if t == "set_value":
                                if a["value_type"] == "number": new = F.D(repr(float(a["num"]))); col[i] = new
                                else: new = a["value"]; col[i] = None if blank(new) else new
                                rawv[k][i] = new
                            elif t == "clear": col[i] = None; rawv[k][i] = ""
                            elif t == "replace":
                                if isinstance(old, str) and a["find"] in old:
                                    nv = old.replace(a["find"], a["with"])
                                    if nv != old: col[i] = None if blank(nv) else nv; rawv[k][i] = nv
                            elif t == "mark":
                                lab = a["value"]
                                if blank(old): col[i] = lab; rawv[k][i] = lab
                                elif isinstance(old, str) and lab not in [s.strip() for s in old.split(";")]:
                                    col[i] = old + "; " + lab; rawv[k][i] = old + "; " + lab
    fidx = {}
    for j in range(len(final_names) - 1, -1, -1): fidx[F.norm(final_names[j])] = j
    outpos = {c: k for k, c in enumerate(cols)}; rowpos = {i: r for r, i in enumerate(outidx)}
    nf, bf, nr, br = 0, [], 0, []
    for k, vals in fraw.items():  # cột công thức: mọi dòng đã xuất
        j = fidx.get(k)
        if j is None or j not in outpos: continue
        for i in range(n):
            if i + 1 in rowpos:
                nf += 1; g = got[rowpos[i + 1]][outpos[j]]
                if not F.same(vals[i], g): bf.append('dòng %d, cột "%s": cần %s, file có %s' % (i + 2, final_names[j], vals[i], g))
    for k, dmap in rawv.items():  # ô bị quy tắc chạm tới, và mọi ô của cột do quy tắc tạo
        j = fidx.get(k)
        if j is None: br.append('cột "%s" không có trong kết quả' % k); continue
        if j not in outpos: continue
        for i in (range(n) if k in created_set else dmap):
            if i + 1 not in rowpos: continue
            exp = dmap.get(i, "") if k in created_set else dmap[i]; g = got[rowpos[i + 1]][outpos[j]]; nr += 1
            if not F.same(exp, g): br.append('dòng %d, cột "%s": cần %s, file có %s' % (i + 2, final_names[j], exp, g))
    if check_colors:
        expc = {}
        for i, c, col in events:
            if c == "row":
                for j in range(len(final_names)): expc[(i, j)] = col
            elif c in fidx: expc[(i, fidx[c])] = col
        for (i, j), col in expc.items():
            if i not in pos or j not in outpos or (i, j) in high: continue
            nr += 1
            if gfill.get((pos[i], outpos[j] + 1)) != col: br.append('dòng %d, cột "%s": cần màu %s, file có %s' % (i + 1, final_names[j], col, gfill.get((pos[i], outpos[j] + 1))))
    return nf, bf, nr, br
