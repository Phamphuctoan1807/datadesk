"""Quy tắc điều kiện (Giai đoạn 3 của lộ trình): WHEN <điều kiện> THEN <hành động> ELSE <hành động>.
Điều kiện được dịch sang cây công thức rồi chạy bằng bộ tính có kiểu dữ liệu của Formula Engine (không so sánh chuỗi thô).
Quy tắc chạy tuần tự trên bản dẫn xuất; bảng gốc không bao giờ bị sửa. Có bộ kiểm tra độc lập (ieval, Decimal) chạy lại toàn bộ chuỗi quy tắc."""
import re, datetime as dt
from collections import Counter
from decimal import Decimal as D, localcontext, Context
import formula as F

COND_OPS = ("=", "!=", ">", "<", ">=", "<=", "contains", "starts_with", "ends_with", "is_empty", "is_not_empty",
            "is_duplicate", "is_unique", "in", "not_in")
ACTIONS = ("set_value", "clear", "replace", "color", "mark")
MAXRULES, MAXCOND, MAXACT = 30, 10, 6
HEX = re.compile(r"#[0-9a-fA-F]{6}$")
DUP = "__dup__"

class RuleError(Exception):
    def __init__(self, code, msg, op_id=None): super().__init__(msg); self.code, self.msg, self.op_id = code, msg, op_id

def _blank(v): return v is None or (isinstance(v, str) and not v.strip())

def _colnames(ast):
    out, st = set(), [ast]
    while st:
        n = st.pop()
        if n[0] == "col": out.add(n[1])
        elif n[0] == "neg": st.append(n[1])
        elif n[0] == "bin": st += [n[2], n[3]]
        elif n[0] == "call": st += n[2]
    return out

def lit(v, ctype, col, to_num, to_date):
    v = str(v)
    if ctype == "number":
        x = to_num(v)
        if x is None: raise RuleError("ERROR_VALUE", 'giá trị "%s" không phải số hợp lệ (cột "%s" là cột số).' % (v, col))
        return ("num", float(x))
    if ctype == "date":
        o = to_date(v)
        if o is None: raise RuleError("ERROR_VALUE", 'giá trị "%s" không phải ngày hợp lệ, hãy nhập dd/mm/yyyy (cột "%s" là cột ngày).' % (v, col))
        return ("date", dt.date.fromordinal(int(o)))
    return ("str", v)

def cmp_node(op, col, v, ctype, cname, to_num, to_date):
    """Cột nhận diện là chữ nhưng giá trị so sánh là số (cột lẫn số và chữ): ô số so như số, ô chữ báo ERROR_TYPE để người dùng kiểm tra."""
    if ctype == "text":
        x = to_num(v)
        if x is not None:
            num = ("bin", op, col, ("num", float(x)))
            if op in ("=", "!="): return ("call", "IF", [("call", "ISNUMBER", [col]), num, ("bin", op, col, ("str", v))])
            return num
    return ("bin", op, col, lit(v, ctype, cname, to_num, to_date))

def cond_ast(c, ctype, to_num, to_date):
    """Một điều kiện -> cây công thức. Ô trống: 'khác' và 'không thuộc' là đúng, các phép còn lại là sai (không báo lỗi)."""
    col = ("col", c["column"]); op = c["operator"]; v = str(c.get("value", ""))
    if op == "is_empty": return ("call", "ISEMPTY", [col])
    if op == "is_not_empty": return ("call", "NOT", [("call", "ISEMPTY", [col])])
    if op in ("is_duplicate", "is_unique"):
        a = ("col", DUP + F.norm(c["column"])); return a if op == "is_duplicate" else ("call", "NOT", [a])
    if op in ("contains", "starts_with", "ends_with"):
        if v == "": raise RuleError("ERROR_VALUE", "điều kiện chứa/bắt đầu/kết thúc cần một giá trị.")
        core = ("call", {"contains": "CONTAINS", "starts_with": "STARTSWITH", "ends_with": "ENDSWITH"}[op], [col, ("str", v)])
    elif op in ("in", "not_in"):
        vals = [x.strip() for x in v.split(";") if x.strip()]
        if not vals: raise RuleError("ERROR_VALUE", "điều kiện danh sách cần ít nhất một giá trị, cách nhau bằng dấu ;")
        core = ("call", "OR", [cmp_node("=", col, x, ctype, c["column"], to_num, to_date) for x in vals])
        if op == "not_in": core = ("call", "NOT", [core])
    else:
        core = cmp_node(op, col, v, ctype, c["column"], to_num, to_date)
    return ("call", "IF", [("call", "ISEMPTY", [col]), ("bool", op in ("!=", "not_in")), core])

def compile_rules(rules, names, ctypes, protected, to_num, to_date):
    """Kiểm tra và dịch quy tắc. Cột do quy tắc trước tạo ra dùng được ở quy tắc sau; ghi đè cột công thức bị chặn."""
    names, ctypes = list(names), list(ctypes); known = {}
    for j in range(len(names) - 1, -1, -1): known[F.norm(names[j])] = j
    if len(rules) > MAXRULES: raise RuleError("TOO_MANY_OPS", "Tối đa %d quy tắc đang bật." % MAXRULES)
    out = []
    for r in rules:
        rid = r.get("id"); label = (r.get("name") or "").strip() or rid
        def fail(code, msg): raise RuleError(code, 'Quy tắc "%s": %s' % (label, msg), rid)
        when = r.get("when") or {}; items = when.get("items") or []
        if not items: fail("ERROR_SYNTAX", "chưa có điều kiện nào.")
        if len(items) > MAXCOND: fail("ERROR_SYNTAX", "tối đa %d điều kiện." % MAXCOND)
        asts, dupcols = [], []
        for c in items:
            col = str(c.get("column", "")).strip()
            if F.norm(col) not in known: fail("ERROR_COLUMN", 'cột "%s" không tồn tại.' % col)
            if c.get("operator") not in COND_OPS: fail("ERROR_OPERATOR", "toán tử điều kiện không hợp lệ.")
            try: a = cond_ast(dict(c, column=col), ctypes[known[F.norm(col)]], to_num, to_date)
            except RuleError as e: fail(e.code, e.msg)
            if c["operator"] in ("is_duplicate", "is_unique") and col not in dupcols: dupcols.append(col)
            asts.append(("call", "NOT", [a]) if c.get("not") else a)
        ast = asts[0] if len(asts) == 1 else ("call", "OR" if when.get("logic") == "OR" else "AND", asts)
        created = []
        def act(a):
            t = a.get("type")
            if t not in ACTIONS: fail("UNSUPPORTED_ACTION", "hành động không được hỗ trợ.")
            def target(create):
                tg = str(a.get("target", "")).strip() or ("Đánh dấu" if t == "mark" else "")
                if not tg: fail("ERROR_COLUMN", "thiếu cột đích.")
                k = F.norm(tg)
                if k in protected: fail("PROTECTED_COLUMN", 'cột "%s" là cột công thức, hãy sửa công thức thay vì ghi đè.' % tg)
                if k not in known:
                    if not create: fail("ERROR_COLUMN", 'cột "%s" không tồn tại.' % tg)
                    if len(tg) > 60 or re.search(r'[\[\]"]', tg): fail("INVALID_NAME", "tên cột mới không hợp lệ (1 đến 60 ký tự, không chứa [ ] hoặc dấu nháy kép).")
                    names.append(tg); ctypes.append("text"); known[k] = len(names) - 1; created.append(tg)
                return tg
            if t == "set_value":
                vt = "number" if a.get("value_type") == "number" else "text"; v = str(a.get("value", "")); num = None
                if vt == "number":
                    num = to_num(v)
                    if num is None: fail("ERROR_VALUE", 'giá trị "%s" không phải số hợp lệ.' % v)
                return {"type": t, "target": target(True), "value": v, "value_type": vt, "num": num}
            if t == "clear": return {"type": t, "target": target(False)}
            if t == "replace":
                f = str(a.get("find", ""))
                if not f: fail("ERROR_VALUE", "thiếu chữ cần thay thế.")
                return {"type": t, "target": target(False), "find": f, "with": str(a.get("with", ""))}
            if t == "mark":
                lab = str(a.get("value", "")).strip()
                if not lab or ";" in lab: fail("ERROR_VALUE", "nhãn đánh dấu không được trống và không chứa dấu ;")
                return {"type": t, "target": target(True), "value": lab}
            col = str(a.get("color", "")); sc = "cell" if a.get("scope") == "cell" else "row"
            if not HEX.match(col): fail("ERROR_VALUE", "màu không hợp lệ.")
            return {"type": t, "color": col.upper(), "scope": sc, "target": target(False) if sc == "cell" else ""}
        acts = {}
        for key in ("then", "else"):
            L = r.get(key) or []
            if key == "then" and not L: fail("ERROR_SYNTAX", "cần ít nhất một hành động THEN.")
            if len(L) > MAXACT: fail("ERROR_SYNTAX", "tối đa %d hành động mỗi nhánh." % MAXACT)
            acts[key] = [act(a) for a in L]
        out.append({"id": rid, "label": label, "ast": ast, "dupcols": dupcols, "then": acts["then"], "else": acts["else"], "created": created})
    return out

def apply_rules(rows, names, ctypes, protected, rules, pn, pd, to_num, to_date):
    """rows là bảng dẫn xuất (hàng 0 là tiêu đề), được sửa tại chỗ. Điều kiện của mỗi quy tắc được tính trên trạng thái
    trước khi quy tắc đó chạy; quy tắc sau thấy kết quả của quy tắc trước."""
    try: comp = compile_rules(rules, names, ctypes, protected, to_num, to_date)
    except RuleError as e: return {"errors": [{"code": e.code, "message": e.msg, "op_id": e.op_id}]}
    body = rows[1:]; n = len(body); names, ctypes = list(names), list(ctypes)
    idx = {}
    for j in range(len(names) - 1, -1, -1): idx[F.norm(names[j])] = j
    T, stats, events, created_all = {}, {}, [], []
    def typed(c):
        if c not in T: T[c] = F.typed_source([r[c] for r in body], ctypes[c], pn, pd)[0]
        return T[c]
    for cr in comp:
        st = {"matched": 0, "errors": Counter(), "overwritten": 0, "created": list(cr["created"])}
        for nm in cr["created"]:  # cột mới được tạo ngay khi quy tắc bắt đầu, kể cả khi không dòng nào khớp
            names.append(nm); ctypes.append("text"); idx[F.norm(nm)] = len(names) - 1; rows[0].append(nm)
            for r in body: r.append("")
            T[len(names) - 1] = [None] * n; created_all.append(nm)
        pseudo = {}
        for cname in cr["dupcols"]:
            col = typed(idx[F.norm(cname)])
            keys = [None if _blank(v) else F.txt(v).casefold() for v in col]; cnt = Counter(k for k in keys if k is not None)
            pseudo[DUP + F.norm(cname)] = [k is not None and cnt[k] > 1 for k in keys]
        L = {nm: (pseudo[nm] if nm in pseudo else typed(idx[F.norm(nm)])) for nm in _colnames(cr["ast"])}
        flags = []
        for i in range(n):
            v = F.ev(cr["ast"], lambda nm, i=i: L[nm][i])
            if isinstance(v, F.Err): st["errors"][v.code] += 1; flags.append(None)  # không đánh giá được: không chạy THEN cũng không chạy ELSE
            elif isinstance(v, bool): flags.append(v)
            else: st["errors"]["ERROR_TYPE"] += 1; flags.append(None)
        st["matched"] = sum(1 for f in flags if f is True)
        def do(a, i, st=st):
            t = a["type"]; row = rows[i + 1]
            if t == "color": events.append((i + 1, "row" if a["scope"] == "row" else idx[F.norm(a["target"])], a["color"])); return
            c = idx[F.norm(a["target"])]; old = row[c]
            if t == "set_value":
                num = a["value_type"] == "number"; new = F.cellval(float(a["num"])) if num else a["value"]
                if not _blank(old) and old != new: st["overwritten"] += 1
                row[c] = new; typed(c)[i] = None if _blank(new) else (float(a["num"]) if num else new)
            elif t == "clear":
                if not _blank(old): st["overwritten"] += 1
                row[c] = ""; typed(c)[i] = None
            elif t == "replace":
                if isinstance(old, str) and a["find"] in old:
                    new = old.replace(a["find"], a["with"])
                    if new != old: st["overwritten"] += 1; row[c] = new; typed(c)[i] = None if _blank(new) else new
            elif t == "mark":
                lab = a["value"]
                if _blank(old): row[c] = lab; typed(c)[i] = lab
                elif isinstance(old, str):
                    if lab not in [s.strip() for s in old.split(";")]: row[c] = old + "; " + lab; typed(c)[i] = row[c]
                else: st["errors"]["ERROR_TYPE"] += 1
        for i, m in enumerate(flags):
            if m is not None:
                for a in (cr["then"] if m else cr["else"]): do(a, i)
        stats[cr["id"]] = {"matched": st["matched"], "errors": dict(st["errors"]), "overwritten": st["overwritten"], "created": st["created"], "rows": n}
    fills = {}; W = len(rows[0])
    for i, c, col in events:  # quy tắc sau ghi đè màu của quy tắc trước
        if c == "row":
            for j in range(W): fills[(i, j)] = col
        else: fills[(i, c)] = col
    warnings = []
    for cid, s_ in stats.items():
        if s_["errors"]: warnings.append("Một số dòng không đánh giá được điều kiện (%s) nên không được coi là khớp: cần kiểm tra." % ", ".join("%d %s" % (v, k) for k, v in s_["errors"].items()))
    return {"errors": [], "warnings": warnings[:3], "stats": stats, "fills": fills, "created": created_all}

# ---------------- kiểm tra độc lập ----------------
def independent_rules_check(dv, outidx, cols, got, gfill, pos, high, final_names, check_colors, to_num, to_date, blank):
    """Chạy lại toàn bộ chuỗi quy tắc từ dữ liệu gốc bằng bộ tính Decimal riêng, rồi so với giá trị và màu đọc lại từ file đã xuất.
    Lưu ý: bước dịch quy tắc sang cây điều kiện (compile_rules) dùng chung với bộ xử lý chính."""
    src, types0, fcols, cfg = dv["src"], dv["types0"], dv["cols"], dv["rcfg"]
    try: comp = compile_rules(cfg["rules"], cfg["names"], cfg["ctypes"], set(cfg["protected"]), to_num, to_date)
    except RuleError as e: return 0, ["không dịch lại được quy tắc: " + e.msg]
    n = len(src) - 1; byname = {}
    for j in range(len(dv["names0"]) - 1, -1, -1): byname[F.norm(dv["names0"][j])] = j
    astof = {F.norm(c["target"]): c["ast"] for c in fcols}
    state, rawv, created_set, events = {}, {}, set(), []
    with localcontext(Context(prec=40)):
        def fget(i, memo):
            def g(name):
                k = F.norm(name)
                if k in memo: return memo[k]
                v = F.ieval(astof[k], g) if k in astof else F.ityped(src[i + 1][byname[k]], types0[byname[k]], to_num, to_date, blank)
                memo[k] = v; return v
            return g
        def colget(k):
            if k not in state:
                if k in astof:
                    vals = []
                    for i in range(n):
                        try: vals.append(F.ieval(astof[k], fget(i, {})))
                        except F.Raise as e: vals.append(e.code)  # ô công thức lỗi hiện mã lỗi dạng chữ, giống bộ xử lý chính
                        except ArithmeticError: vals.append("ERROR_OVERFLOW")
                    state[k] = vals
                else: state[k] = [F.ityped(src[i + 1][byname[k]], types0[byname[k]], to_num, to_date, blank) for i in range(n)]
            return state[k]
        def rawcell(k, i):
            if k in created_set: return rawv[k].get(i, "")
            return rawv.get(k, {}).get(i, src[i + 1][byname[k]])
        for cr in comp:
            for nm in cr["created"]:
                k = F.norm(nm); state[k] = [None] * n; rawv[k] = {}; created_set.add(k)
            pseudo = {}
            for cname in cr["dupcols"]:
                col = colget(F.norm(cname)); keys = [None if blank(v) else F.itxt(v).casefold() for v in col]; cnt = Counter(k for k in keys if k is not None)
                pseudo[DUP + F.norm(cname)] = [k is not None and cnt[k] > 1 for k in keys]
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
                        if a["value_type"] == "number": new = D(repr(float(a["num"]))); col[i] = new
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
    checked, bad = 0, []
    for k, dmap in rawv.items():
        j = fidx.get(k)
        if j is None: bad.append('cột "%s" không có trong kết quả' % k); continue
        if j not in outpos: continue
        for i in (range(n) if k in created_set else dmap):
            if i + 1 not in rowpos: continue
            exp = dmap.get(i, "") if k in created_set else dmap[i]; g = got[rowpos[i + 1]][outpos[j]]; checked += 1
            if not F.same(exp, g): bad.append('dòng %d, cột "%s": cần %s, file có %s' % (i + 2, final_names[j], exp, g))
    if check_colors:
        expc = {}
        for i, c, col in events:
            if c == "row":
                for j in range(len(final_names)): expc[(i, j)] = col
            elif c in fidx: expc[(i, fidx[c])] = col
        for (i, j), col in expc.items():
            if i not in pos or j not in outpos or (i, j) in high: continue
            checked += 1
            if gfill.get((pos[i], outpos[j] + 1)) != col: bad.append('dòng %d, cột "%s": cần màu %s, file có %s' % (i + 1, final_names[j], col, gfill.get((pos[i], outpos[j] + 1))))
    return checked, bad
