"""Quy tắc điều kiện (Giai đoạn 3 của lộ trình): WHEN <điều kiện> THEN <hành động> ELSE <hành động>.
Điều kiện được dịch sang cây công thức rồi chạy bằng bộ tính có kiểu dữ liệu của Formula Engine (không so sánh chuỗi thô).
Quy tắc chạy tuần tự trên bản dẫn xuất; bảng gốc không bao giờ bị sửa. Có bộ kiểm tra độc lập (ieval, Decimal) chạy lại toàn bộ chuỗi quy tắc."""
import re, datetime as dt
from collections import Counter
from decimal import Decimal as D, localcontext, Context
import formula as F

COND_OPS = ("=", "!=", ">", "<", ">=", "<=", "contains", "starts_with", "ends_with", "is_empty", "is_not_empty",
            "is_duplicate", "is_unique", "in", "not_in")
ACTIONS = ("set_value", "clear", "replace", "color", "mark", "add_to_list", "append_last")
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
    try: return ("bin", op, col, lit(v, ctype, cname, to_num, to_date))
    except RuleError:
        if ctype in ("number", "date") and op in ("=", "!="):  # so với chữ như "N/A" trong cột số/ngày: ô số/ngày không bao giờ bằng chữ đó
            return ("call", "IF", [("call", "ISNUMBER" if ctype == "number" else "ISDATE", [col]), ("bool", op == "!="), ("bin", op, col, ("str", v))])
        raise

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
                tg = str(a.get("target", "")).strip() or {"mark": "Đánh dấu", "add_to_list": "Danh sách"}.get(t, "")
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
            if t in ("mark", "add_to_list", "append_last"):
                lab = str(a.get("value", "")).strip()
                if not lab or ";" in lab: fail("ERROR_VALUE", "nhãn không được trống và không chứa dấu ;")
                if t == "append_last":  # thêm vào cột cuối hiện có, không tạo cột mới (schema không đổi âm thầm)
                    tg = names[-1]
                    if F.norm(tg) in protected: fail("PROTECTED_COLUMN", 'cột cuối ("%s") là cột công thức, không thể thêm giá trị vào đó.' % tg)
                    return {"type": "mark", "target": tg, "value": lab}
                return {"type": "mark", "target": target(True), "value": lab}
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

def apply_rules(rows, names, ctypes, protected, rules, typed, T, to_num, to_date):
    """rows là bảng dẫn xuất (hàng 0 là tiêu đề), được sửa tại chỗ. typed(c) trả về danh sách có kiểu của cột c (dùng chung với công thức);
    T là bộ nhớ đệm đó. Điều kiện của mỗi quy tắc được tính trước khi quy tắc chạy; quy tắc sau thấy kết quả của quy tắc trước."""
    try: comp = compile_rules(rules, names, ctypes, protected, to_num, to_date)
    except RuleError as e: return {"errors": [{"code": e.code, "message": e.msg, "op_id": e.op_id}]}
    body = rows[1:]; n = len(body); names, ctypes = list(names), list(ctypes)
    idx = {}
    for j in range(len(names) - 1, -1, -1): idx[F.norm(names[j])] = j
    stats, events, errlog, created_all = {}, [], [], []
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
        flags = []; logged = 0
        for i in range(n):
            v = F.ev(cr["ast"], lambda nm, i=i: L[nm][i])
            code = v.code if isinstance(v, F.Err) else (None if isinstance(v, bool) else "ERROR_TYPE")
            if code:  # không đánh giá được: không chạy THEN cũng không chạy ELSE, ghi vào báo cáo lỗi
                st["errors"][code] += 1; flags.append(None)
                if logged < 100: logged += 1; errlog.append({"op_id": cr["id"], "target": cr["label"], "row": i, "code": code, "inputs": "; ".join("%s = %s" % (nm, F._show(L[nm][i])) for nm in sorted(L) if not nm.startswith(DUP))})
            else: flags.append(v)
        st["matched"] = sum(1 for f_ in flags if f_ is True)
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
    warnings = []
    for cid, s_ in stats.items():
        if s_["errors"]: warnings.append("Một số dòng không đánh giá được điều kiện (%s) nên không được coi là khớp: cần kiểm tra." % ", ".join("%d %s" % (v, k) for k, v in s_["errors"].items()))
    return {"errors": [], "warnings": warnings[:3], "stats": stats, "events": events, "created": created_all, "names": names, "ctypes": ctypes, "errlog": errlog}

