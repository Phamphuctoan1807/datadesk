"""
DataDesk - Phase 8: Export Engine mở rộng (export.py)
Tuân thủ nghiêm ngặt DataDesk Development Roadmap (đặc biệt các mục 35, 36, 71):
- Hỗ trợ xuất các định dạng chuẩn: XLSX, CSV, TSV, JSON.
- Hàm write_xlsx(t, outidx, cols, fills, hdr, title, formula_mode="value"):
  * Khi formula_mode == "value": ghi giá trị đã tính toán.
  * Khi formula_mode == "formula": nếu có biểu thức công thức (hoặc Excel formula dạng =...), ghi công thức Excel.
  * Giữ nguyên màu sắc (fills), tiêu đề in đậm, cố định dòng tiêu đề (freeze_panes), autofilter,
    tự căn chỉnh độ rộng cột (column_dimensions), giữ nguyên number format/date format gốc.
- Hàm write_csv(t, outidx, cols): Xuất CSV UTF-8 kèm BOM (\ufeff) để Excel mở không lỗi font tiếng Việt.
- Hàm write_tsv(t, outidx, cols): Xuất TSV tab-delimited UTF-8 (\ufeff).
- Hàm write_json(t, outidx, cols, hdr): Xuất mảng JSON các object [{"col_name": val}] (nếu có header)
  hoặc mảng 2 chiều nếu không có header, đảm bảo parse/serialize an toàn.
- Hàm read_back(data, fmt, nrows, ncols): Đọc lại file vừa tạo (hỗ trợ cả XLSX, CSV, TSV, JSON)
  và trích xuất (rows, fills) độc lập để phục vụ kiểm tra đối chiếu kép.
- Hàm format_warnings(fmt): Trả về cảnh báo nếu định dạng không hỗ trợ màu sắc/định dạng (như CSV, TSV, JSON).
- Hàm export_data(t, outidx, cols, fills, hdr, title, fmt, formula_mode): Bộ điều phối xuất file đa định dạng.
- Hàm export_preview(t, outidx, cols, fills, hdr, fmt, limit): Xem trước bảng xuất (Roadmap mục 36).
"""

import io
import csv
import json
import math
import re
import datetime as dt
import unicodedata

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    openpyxl = None

try:
    import formula as F
except ImportError:
    F = None


# ==============================================================================
# 1. TIỆN ÍCH CHUYỂN ĐỔI VÀ ĐỊNH DẠNG DỮ LIỆU
# ==============================================================================

def norm_str(s):
    """Chuẩn hóa chuỗi Unicode NFC không dấu/chữ thường để so khớp tên cột."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s))).strip().casefold()


def disp(v):
    """Chuyển đổi giá trị ô sang chuỗi hiển thị tương thích CSV/TSV và Excel text."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, dt.datetime):
        return v.strftime("%d/%m/%Y" if not (v.hour or v.minute or v.second) else "%d/%m/%Y %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return ""
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def norm(v):
    """Chuẩn hóa giá trị ô để phục vụ so sánh đối chiếu kép (read_back so với gốc)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def json_safe(v):
    """Đảm bảo mọi giá trị đều có thể serialize thành JSON an toàn, bảo toàn kiểu."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int,)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return int(v) if v.is_integer() else v
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def clean_hex(color):
    """Làm sạch mã màu HEX để đưa vào openpyxl PatternFill."""
    if not color:
        return "FFFFFF"
    c = str(color).strip().lstrip("#").upper()
    if len(c) == 8:
        return c
    if len(c) == 6:
        return c
    if len(c) == 3:
        return "".join([x * 2 for x in c])
    return "FFFFFF"


# ==============================================================================
# 2. XỬ LÝ CÔNG THỨC VÀ DỊCH SANG EXCEL FORMULA
# ==============================================================================

def ast_to_excel(ast, col_map, row_num):
    """
    Dịch cây cú pháp (AST) của Formula Engine sang cú pháp công thức Excel.
    col_map: dict ánh xạ {tên cột chuẩn hóa: chữ cái cột Excel}
    row_num: chỉ số dòng 1-based trong Excel
    """
    if not isinstance(ast, tuple):
        return str(ast)
    kind = ast[0]
    if kind == "num":
        v = ast[1]
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    elif kind == "str":
        s = str(ast[1]).replace('"', '""')
        return f'"{s}"'
    elif kind == "bool":
        return "TRUE" if ast[1] else "FALSE"
    elif kind == "col":
        col_name = str(ast[1])
        c_letter = col_map.get(norm_str(col_name)) or col_map.get(col_name) or col_name
        return f"{c_letter}{row_num}"
    elif kind == "neg":
        return f"-({ast_to_excel(ast[1], col_map, row_num)})"
    elif kind == "bin":
        op, left, right = ast[1], ast[2], ast[3]
        l_str = ast_to_excel(left, col_map, row_num)
        r_str = ast_to_excel(right, col_map, row_num)
        if op == "%":
            return f"MOD({l_str}, {r_str})"
        elif op in ("!=", "<>"):
            return f"({l_str} <> {r_str})"
        else:
            return f"({l_str} {op} {r_str})"
    elif kind == "call":
        fn, args = ast[1].upper(), ast[2]
        arg_strs = [ast_to_excel(a, col_map, row_num) for a in args]
        if fn == "CEIL":
            return f"ROUNDUP({arg_strs[0]}, 0)"
        elif fn == "FLOOR":
            return f"ROUNDDOWN({arg_strs[0]}, 0)"
        elif fn == "ISEMPTY":
            return f"ISBLANK({arg_strs[0]})"
        elif fn == "CONTAINS":
            return f"ISNUMBER(SEARCH({arg_strs[1]}, {arg_strs[0]}))"
        elif fn == "STARTSWITH":
            return f"(LEFT({arg_strs[0]}, LEN({arg_strs[1]})) = {arg_strs[1]})"
        elif fn == "ENDSWITH":
            return f"(RIGHT({arg_strs[0]}, LEN({arg_strs[1]})) = {arg_strs[1]})"
        else:
            return f"{fn}({', '.join(arg_strs)})"
    return str(ast)


def translate_to_excel_formula(formula, col_map, row_num, col_names=None):
    """
    Chuyển đổi biểu thức công thức (AST, string DSL, hoặc template Excel) thành công thức Excel hợp lệ.
    """
    if isinstance(formula, tuple):
        return "=" + ast_to_excel(formula, col_map, row_num)
    if not isinstance(formula, str):
        return str(formula)

    f_str = formula.strip()
    if "{row}" in f_str:
        res = f_str.format(row=row_num)
        return res if res.startswith("=") else "=" + res

    # Nếu đã là công thức Excel trực tiếp dạng =A2+B2 hoặc =SUM(A2:B2)
    if f_str.startswith("=") and not re.search(r"\[.+?\]", f_str):
        return f_str

    clean_expr = f_str.lstrip("=")

    # Nếu có module formula, thử parse sang AST để chuyển đổi chuẩn mực
    if F is not None and col_names:
        try:
            ast = F.parse(clean_expr, F._pats(col_names))
            return "=" + ast_to_excel(ast, col_map, row_num)
        except Exception:
            pass

    # Quy tắc thay thế Regex thay thế [Tên cột] thành [Cột_Excel][Dòng]
    def repl_col(m):
        cname = m.group(1).strip()
        c_letter = col_map.get(norm_str(cname)) or col_map.get(cname) or cname
        return f"{c_letter}{row_num}"

    translated = re.sub(r"\[([^\]]+)\]", repl_col, clean_expr)
    return translated if translated.startswith("=") else "=" + translated


# ==============================================================================
# 3. CÁC HÀM XUẤT FILE CHÍNH
# ==============================================================================

def write_xlsx(t, outidx, cols, fills=None, hdr=True, title="Dữ liệu", formula_mode="value"):
    """
    Xuất bảng t sang file Excel .xlsx với định dạng cao cấp.
    
    Tham số:
      - t: dict chứa dữ liệu bảng ('rows', 'name', 'fm', 'sf', 'formulas', 'derived', ...)
      - outidx: danh sách chỉ số dòng cần xuất (từ t['rows'])
      - cols: danh sách chỉ số cột cần xuất
      - fills: dict màu sắc {(row_idx, col_idx): "#RRGGBB"}
      - hdr: boolean, có dòng tiêu đề hay không
      - title: tên sheet hiển thị trong workbook
      - formula_mode: "value" (giá trị đã tính toán) hoặc "formula" (công thức Excel)
    """
    if openpyxl is None:
        raise ImportError("openpyxl chưa được cài đặt. Không thể tạo tệp XLSX.")

    wb = openpyxl.Workbook()
    ws = wb.active

    # Cắt gọn và lọc ký tự cấm trong tên sheet theo chuẩn Excel (tối đa 31 ký tự)
    safe_title = re.sub(r"[\\/?*\[\]:]", "_", str(title or t.get("name") or "Dữ liệu"))[:31]
    ws.title = safe_title or "Dữ liệu"

    fills = fills or {}
    rows = t.get("rows") or []
    hdr_bool = bool(hdr)

    # 1. Thu thập ánh xạ tên cột sang chữ cái cột Excel cho công thức
    col_map = {}
    col_names = []
    if rows:
        hdr_row = rows[0] if hdr_bool else []
        for k, c in enumerate(cols, 1):
            letter = get_column_letter(k)
            name = str(hdr_row[c]).strip() if hdr_bool and c < len(hdr_row) else f"Cột {k}"
            col_names.append(name)
            col_map[norm_str(name)] = letter
            col_map[name] = letter
            col_map[str(c)] = letter
            col_map[c] = letter
            col_map[letter.upper()] = letter
            col_map[norm_str(letter)] = letter

    # 2. Thu thập bản đồ công thức (nếu có)
    cell_formulas = dict(t.get("formulas") or {})
    cell_formulas.update(t.get("cell_formulas") or {})
    col_formulas = dict(t.get("col_formulas") or {})

    # Trích xuất công thức từ metadata derived pipeline nếu có
    dv = t.get("derived") or {}
    for step in dv.get("steps") or []:
        if step.get("kind") == "formula":
            for col_def in step.get("cols") or []:
                target = col_def.get("target")
                if hdr_bool and rows:
                    for c_idx, h_val in enumerate(rows[0]):
                        if norm_str(h_val) == norm_str(target):
                            col_formulas[c_idx] = col_def.get("ast") or col_def.get("expression")

    calc_values = dict(t.get("values") or {})
    calc_values.update(t.get("calc_values") or {})

    # 3. Ghi dữ liệu từng ô
    for r, i in enumerate(outidx, 1):
        is_header_cell = bool(hdr_bool and r == 1)
        for k, c in enumerate(cols, 1):
            cell = ws.cell(r, k)
            raw_v = rows[i][c] if i < len(rows) and c < len(rows[i]) else ""

            if is_header_cell:
                # Dòng tiêu đề
                cell.value = raw_v
                cell.font = Font(bold=True)
                hdr_color = "#E8EDF3"
                if t.get("sf") and len(t["sf"]) > 0 and c < len(t["sf"][0]) and t["sf"][0][c]:
                    hdr_color = t["sf"][0][c]
                cell.fill = PatternFill("solid", fgColor=clean_hex(hdr_color))
                continue

            # Dòng dữ liệu
            if formula_mode == "formula":
                # Tìm công thức cho ô hoặc cột này
                formula_target = cell_formulas.get((i, c)) or col_formulas.get(c)
                if not formula_target and isinstance(raw_v, str) and raw_v.startswith("="):
                    formula_target = raw_v

                if formula_target is not None:
                    excel_formula = translate_to_excel_formula(formula_target, col_map, r, col_names)
                    cell.value = excel_formula
                    # Không đặt data_type='s' để openpyxl giữ dạng công thức
                else:
                    v = calc_values.get((i, c), raw_v)
                    _write_single_cell(cell, v, t, i, c)
            else:
                # formula_mode == "value"
                v = calc_values.get((i, c), raw_v)
                _write_single_cell(cell, v, t, i, c)

            # Màu sắc ô (Fills)
            if fills and (i, c) in fills:
                cell.fill = PatternFill("solid", fgColor=clean_hex(fills[(i, c)]))

    # 4. Tự căn chỉnh độ rộng cột (Column Widths)
    for k, c in enumerate(cols, 1):
        col_letter = get_column_letter(k)
        max_len = 8
        for i in outidx:
            if i < len(rows) and c < len(rows[i]):
                val = rows[i][c]
                d_len = len(disp(val))
                if d_len > max_len:
                    max_len = d_len
        ws.column_dimensions[col_letter].width = min(60, max(8, max_len + 2))

    # 5. Cố định dòng tiêu đề & Bật bộ lọc tự động
    if hdr_bool and len(outidx) > 0:
        ws.freeze_panes = "A2"
        if ws.dimensions and ws.dimensions != "A1:A1":
            ws.auto_filter.ref = ws.dimensions

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _write_single_cell(cell, v, t, i, c):
    """Ghi giá trị đơn lẻ vào ô Excel kèm theo kiểu và định dạng number_format."""
    if v is None or v == "":
        return
    cell.value = v
    if isinstance(v, str):
        cell.data_type = "s"
    fm = t["fm"][i][c] if t.get("fm") and i < len(t["fm"]) and c < len(t["fm"][i]) else None
    if fm and fm != "General":
        cell.number_format = fm


def write_csv(t, outidx, cols):
    """
    Xuất bảng t sang định dạng CSV UTF-8 kèm BOM (\\ufeff) để Excel hiển thị tiếng Việt không bị lỗi font.
    """
    rows = t.get("rows") or []
    s = io.StringIO()
    w = csv.writer(s, lineterminator="\r\n")
    for i in outidx:
        row_vals = [disp(rows[i][c] if i < len(rows) and c < len(rows[i]) else "") for c in cols]
        w.writerow(row_vals)
    return ("\ufeff" + s.getvalue()).encode("utf-8")


def write_tsv(t, outidx, cols):
    """
    Xuất bảng t sang định dạng TSV tab-delimited UTF-8 kèm BOM (\\ufeff).
    """
    rows = t.get("rows") or []
    s = io.StringIO()
    w = csv.writer(s, delimiter="\t", lineterminator="\r\n")
    for i in outidx:
        row_vals = [disp(rows[i][c] if i < len(rows) and c < len(rows[i]) else "") for c in cols]
        w.writerow(row_vals)
    return ("\ufeff" + s.getvalue()).encode("utf-8")


def write_json(t, outidx, cols, hdr=True):
    """
    Xuất bảng t sang JSON UTF-8.
    Nếu hdr == True: Xuất mảng các object [{"col_name": val}].
    Nếu hdr == False: Xuất mảng 2 chiều [[val1, val2, ...]].
    """
    rows = t.get("rows") or []
    hdr_bool = bool(hdr)

    if hdr_bool:
        # Nếu outidx bắt đầu bằng 0 (dòng header), tách dòng 0 ra làm tên thuộc tính
        if outidx and outidx[0] == 0:
            header_idx = 0
            data_indices = outidx[1:]
        else:
            header_idx = 0
            data_indices = [idx for idx in outidx if idx != 0] if 0 in outidx else outidx

        headers = []
        for k, c in enumerate(cols, 1):
            h_name = ""
            if rows and header_idx < len(rows) and c < len(rows[header_idx]):
                h_name = disp(rows[header_idx][c]).strip()
            headers.append(h_name or f"Cột {k}")

        records = []
        for i in data_indices:
            obj = {}
            for k, c in enumerate(cols):
                val = rows[i][c] if i < len(rows) and c < len(rows[i]) else None
                obj[headers[k]] = json_safe(val)
            records.append(obj)
        output_data = records
    else:
        # Không có header: mảng 2 chiều thuần túy
        output_data = []
        for i in outidx:
            row_data = [json_safe(rows[i][c] if i < len(rows) and c < len(rows[i]) else None) for c in cols]
            output_data.append(row_data)

    return json.dumps(output_data, ensure_ascii=False, indent=2, default=str).encode("utf-8")


# ==============================================================================
# 4. HÀM ĐỌC LẠI FILE (READ-BACK) ĐỂ KIỂM ĐỊNH ĐỐI CHIẾU ĐỘC LẬP
# ==============================================================================

def _try_parse_iso(s):
    """Cố gắng khôi phục ngày tháng từ chuỗi ISO trong JSON."""
    if not isinstance(s, str):
        return s
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return dt.date.fromisoformat(s)
        except ValueError:
            pass
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?", s):
        try:
            return dt.datetime.fromisoformat(s)
        except ValueError:
            pass
    return s


def read_back(data, fmt, nrows, ncols):
    """
    Đọc lại file vừa tạo (hỗ trợ cả XLSX, CSV, TSV, JSON) và trích xuất (rows, fills) độc lập.
    Phục vụ kiểm tra đối chiếu kép theo nguyên tắc số 9 & 10 của Roadmap.
    
    Trả về:
      got: danh sách 2D gồm nrows dòng, mỗi dòng ncols giá trị.
      fills: dict màu sắc {(r, k): "#RRGGBB"} với r, k là chỉ số 1-based (chỉ có ở XLSX).
    """
    fmt = str(fmt).lower().strip()

    if fmt in ("xlsx", "excel"):
        if openpyxl is None:
            raise ImportError("openpyxl chưa được cài đặt. Không thể đọc lại XLSX.")
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
        ws = wb.active
        got, fl = [], {}
        for r, row in enumerate(ws.iter_rows(min_row=1, max_row=nrows, max_col=ncols), 1):
            got.append([norm(c.value) for c in row])
            for k, c in enumerate(row, 1):
                if c.fill and c.fill.fill_type == "solid" and r > (1 if ws.freeze_panes else 0):
                    color_rgb = str(c.fill.fgColor.rgb) if c.fill.fgColor else ""
                    if color_rgb and color_rgb.lower() != "none":
                        fl[(r, k)] = "#" + color_rgb[-6:].upper()
        # Đảm bảo đủ số dòng và số cột
        while len(got) < nrows:
            got.append([""] * ncols)
        got = got[:nrows]
        for idx in range(len(got)):
            row = got[idx]
            if len(row) < ncols:
                row.extend([""] * (ncols - len(row)))
            got[idx] = row[:ncols]
        return got, fl

    elif fmt == "csv":
        text = data.decode("utf-8-sig") if isinstance(data, (bytes, bytearray)) else data
        reader = csv.reader(io.StringIO(text, newline=""))
        got = [list(r) for r in reader]
        while len(got) < nrows:
            got.append([""] * ncols)
        got = got[:nrows]
        for idx in range(len(got)):
            row = got[idx]
            if len(row) < ncols:
                row.extend([""] * (ncols - len(row)))
            got[idx] = row[:ncols]
        return got, {}

    elif fmt == "tsv":
        text = data.decode("utf-8-sig") if isinstance(data, (bytes, bytearray)) else data
        reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t")
        got = [list(r) for r in reader]
        while len(got) < nrows:
            got.append([""] * ncols)
        got = got[:nrows]
        for idx in range(len(got)):
            row = got[idx]
            if len(row) < ncols:
                row.extend([""] * (ncols - len(row)))
            got[idx] = row[:ncols]
        return got, {}

    elif fmt == "json":
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        parsed = json.loads(text)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            headers = list(parsed[0].keys())
            data_rows = [[item.get(h, "") for h in headers] for item in parsed]
            if nrows == len(data_rows):
                got = [[norm(_try_parse_iso(v)) for v in row] for row in data_rows]
            else:
                got = [headers] + [[norm(_try_parse_iso(v)) for v in row] for row in data_rows]
        elif isinstance(parsed, list):
            got = [[norm(_try_parse_iso(v)) for v in row] for row in parsed]
        else:
            got = []
        while len(got) < nrows:
            got.append([""] * ncols)
        got = got[:nrows]
        for idx in range(len(got)):
            row = got[idx]
            if len(row) < ncols:
                row.extend([""] * (ncols - len(row)))
            got[idx] = row[:ncols]
        return got, {}

    else:
        raise ValueError(f"Định dạng không được hỗ trợ để đọc lại: {fmt}")


# ==============================================================================
# 5. CẢNH BÁO ĐỊNH DẠNG (FORMAT WARNINGS)
# ==============================================================================

def format_warnings(fmt):
    """
    Trả về danh sách cảnh báo (list of str) về tính năng định dạng bị mất khi xuất file.
    Tuân thủ mục 35.2 & 35.3 trong Roadmap.
    """
    f = str(fmt).lower().strip()
    if f == "csv":
        return [
            "CSV là định dạng văn bản thuần túy, không hỗ trợ lưu màu sắc ô (cell fills/highlights).",
            "CSV không hỗ trợ viền ô (borders), phông chữ in đậm hoặc căn lề.",
            "CSV không hỗ trợ cố định dòng tiêu đề (freeze panes) hoặc bộ lọc dữ liệu (autofilter).",
            "CSV không lưu công thức Excel mà chỉ lưu giá trị hiển thị dạng chuỗi văn bản.",
            "CSV không giữ nguyên định dạng số/ngày tháng gốc của Excel."
        ]
    elif f == "tsv":
        return [
            "TSV là định dạng ngăn cách bởi dấu tab, không hỗ trợ lưu màu sắc ô (cell fills/highlights).",
            "TSV không hỗ trợ viền ô (borders), phông chữ in đậm hoặc căn lề.",
            "TSV không hỗ trợ cố định dòng tiêu đề (freeze panes) hoặc bộ lọc dữ liệu (autofilter).",
            "TSV không lưu công thức Excel mà chỉ lưu giá trị hiển thị dạng chuỗi văn bản.",
            "TSV không giữ nguyên định dạng số/ngày tháng gốc của Excel."
        ]
    elif f == "json":
        return [
            "JSON chỉ lưu trữ cấu trúc dữ liệu, không hỗ trợ lưu màu sắc ô (cell fills/highlights).",
            "JSON không hỗ trợ thuộc tính bảng tính (freeze panes, autofilter, column widths, font format).",
            "JSON không lưu công thức Excel mà chỉ lưu giá trị dữ liệu đã qua tính toán."
        ]
    elif f in ("xlsx", "xls"):
        return []
    else:
        return [f"Định dạng '{fmt}' có thể không lưu đầy đủ các thuộc tính trực quan của bảng tính."]


# ==============================================================================
# 6. ĐIỀU PHỐI XUẤT FILE VÀ XEM TRƯỚC (EXPORT PREVIEW)
# ==============================================================================

def export_data(t, outidx, cols, fills=None, hdr=True, title="Dữ liệu", fmt="xlsx", formula_mode="value"):
    """
    Hàm điều phối thống nhất cho toàn bộ hệ thống xuất file của DataDesk.
    """
    fmt = str(fmt).lower().strip()
    if fmt == "xlsx":
        return write_xlsx(t, outidx, cols, fills=fills, hdr=hdr, title=title, formula_mode=formula_mode)
    elif fmt == "csv":
        return write_csv(t, outidx, cols)
    elif fmt == "tsv":
        return write_tsv(t, outidx, cols)
    elif fmt == "json":
        return write_json(t, outidx, cols, hdr=hdr)
    else:
        raise ValueError(f"Định dạng xuất không được hỗ trợ: {fmt}")


def export_preview(t, outidx, cols, fills=None, hdr=True, fmt="xlsx", formula_mode="value", limit=20):
    """
    Tạo dữ liệu xem trước kết quả xuất (Roadmap mục 36: Export Preview).
    Trả về dict chứa thông tin kích thước, cảnh báo, và mẫu dữ liệu giới hạn.
    """
    fmt = str(fmt).lower().strip()
    fills = fills or {}
    rows = t.get("rows") or []
    total_rows = len(outidx)
    total_cols = len(cols)

    sample_outidx = outidx[:limit]
    col_headers = []
    if rows and hdr:
        col_headers = [disp(rows[0][c]) for c in cols]
    else:
        col_headers = [f"Cột {k}" for k in range(1, total_cols + 1)]

    sample_rows = []
    sample_fills = {}
    for r, i in enumerate(sample_outidx, 1):
        row_vals = [disp(rows[i][c] if i < len(rows) and c < len(rows[i]) else "") for c in cols]
        sample_rows.append(row_vals)
        for k, c in enumerate(cols, 1):
            if (i, c) in fills:
                sample_fills[(r, k)] = fills[(i, c)]

    return {
        "format": fmt.upper(),
        "total_rows": total_rows,
        "total_cols": total_cols,
        "columns": col_headers,
        "sample_rows": sample_rows,
        "sample_fills": sample_fills if fmt == "xlsx" else {},
        "warnings": format_warnings(fmt),
        "formula_mode": formula_mode
    }
