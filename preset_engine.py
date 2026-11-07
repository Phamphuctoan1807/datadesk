"""
DataDesk - Saved Workflow / Preset Engine (Stage C - Future 1, Mục 74)
Quản lý, lưu trữ, tái sử dụng, xuất/nhập quy trình biến đổi mẫu (Preset).

Nguyên tắc:
1. Không sửa dataset gốc; preset chỉ lưu định nghĩa các bước biến đổi (ops).
2. Kiểm tra tính tương thích cột trước khi áp dụng (validate_preset_for_dataset).
3. Độc lập với phiên làm việc (persisted trên đĩa dạng JSON an toàn).
4. Kháng injection, kiểm tra tính hợp lệ của schema bước khi nạp.
"""

import os
import re
import json
import time
import uuid
import datetime as dt
from typing import Dict, List, Optional, Tuple, Any

import formula as F
import rules as RL
import normalize as NZ
import schema as SC

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRESET_FILE = os.path.join(DATA_DIR, "presets.json")

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PRESET_FILE):
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def _read_all() -> Dict[str, dict]:
    _ensure_dir()
    try:
        with open(PRESET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_all(presets: Dict[str, dict]):
    _ensure_dir()
    with open(PRESET_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)

# ----------------- 1. Phân tích yêu cầu cột của Preset -----------------

def extract_preset_requirements(steps: List[dict]) -> List[str]:
    """Phân tích danh sách các bước biến đổi để trích xuất các cột đầu vào bắt buộc."""
    req_cols = set()
    for o in steps:
        otype = o.get("type", "FORMULA")
        if otype == "FORMULA":
            expr = o.get("expression", "")
            # Trích xuất các cột trong ngoặc vuông [Tên cột]
            for col in re.findall(r"\[([^\]]+)\]", expr):
                req_cols.add(col.strip())
        elif otype == "NORMALIZE":
            for col in o.get("columns", []):
                req_cols.add(str(col).strip())
        elif otype == "CONDITIONAL":
            for c in o.get("conditions", []):
                if c.get("col"):
                    req_cols.add(str(c["col"]).strip())
            for a in (o.get("then", []) + o.get("else", [])):
                if a.get("col"):
                    req_cols.add(str(a["col"]).strip())
    return sorted(list(req_cols))

def validate_preset_for_dataset(preset: dict, headers: List[str]) -> dict:
    """Kiểm tra tính tương thích giữa Preset và bảng dữ liệu hiện tại.
    Trả về danh sách cột còn thiếu và gợi ý ánh xạ cột thông minh nếu có sai khác tên.
    """
    clean_headers = [str(h).strip() for h in headers if h is not None]
    norm_h_map = {SC.normalize_col_name(h): h for h in clean_headers}

    req_cols = preset.get("column_requirements") or extract_preset_requirements(preset.get("steps", []))
    missing = []
    suggested_map = {}

    for req in req_cols:
        if req in clean_headers:
            continue
        # Thử tìm theo tên chuẩn hóa
        norm_req = SC.normalize_col_name(req)
        if norm_req in norm_h_map:
            suggested_map[req] = norm_h_map[norm_req]
        else:
            missing.append(req)

    is_compatible = len(missing) == 0
    return {
        "compatible": is_compatible,
        "required_columns": req_cols,
        "missing_columns": missing,
        "suggested_mapping": suggested_map,
        "warnings": [f"Thiếu cột bắt buộc: '{c}'" for c in missing]
    }

# ----------------- 2. CRUD Quy trình mẫu (Presets) -----------------

def list_presets() -> List[dict]:
    """Danh sách tóm tắt toàn bộ Preset đã lưu."""
    data = _read_all()
    res = []
    for pid, p in data.items():
        res.append({
            "id": pid,
            "name": p.get("name", "Quy trình không tên"),
            "description": p.get("description", ""),
            "steps_count": len(p.get("steps", [])),
            "required_columns": p.get("column_requirements", []),
            "created_at": p.get("created_at", ""),
            "updated_at": p.get("updated_at", ""),
            "version": p.get("version", 1)
        })
    res.sort(key=lambda x: x["updated_at"], reverse=True)
    return res

def get_preset(preset_id: str) -> Optional[dict]:
    """Lấy thông tin chi tiết một Preset."""
    data = _read_all()
    return data.get(preset_id)

def save_preset(name: str, steps: List[dict], description: str = "", preset_id: str = None) -> dict:
    """Tạo mới hoặc cập nhật một Preset."""
    name = str(name).strip()[:100]
    if not name:
        raise ValueError("Tên quy trình mẫu không được để trống.")
    if not isinstance(steps, list) or len(steps) == 0:
        raise ValueError("Quy trình mẫu phải có ít nhất 1 bước biến đổi.")

    data = _read_all()
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Vệ sinh các bước (loại bỏ id tạm thời nếu cần hoặc tạo id mới)
    clean_steps = []
    for idx, s in enumerate(steps):
        s_copy = dict(s)
        s_copy["id"] = s_copy.get("id") or f"op_{idx+1}_{uuid.uuid4().hex[:6]}"
        s_copy["enabled"] = bool(s_copy.get("enabled", True))
        clean_steps.append(s_copy)

    req_cols = extract_preset_requirements(clean_steps)

    if preset_id and preset_id in data:
        pid = preset_id
        entry = data[pid]
        entry["name"] = name
        entry["description"] = str(description).strip()[:300]
        entry["steps"] = clean_steps
        entry["column_requirements"] = req_cols
        entry["updated_at"] = now_str
        entry["version"] = entry.get("version", 1) + 1
    else:
        pid = preset_id or f"preset_{uuid.uuid4().hex[:10]}"
        entry = {
            "id": pid,
            "name": name,
            "description": str(description).strip()[:300],
            "steps": clean_steps,
            "column_requirements": req_cols,
            "created_at": now_str,
            "updated_at": now_str,
            "version": 1
        }
        data[pid] = entry

    _write_all(data)
    return entry

def delete_preset(preset_id: str) -> bool:
    """Xóa một Preset."""
    data = _read_all()
    if preset_id in data:
        del data[preset_id]
        _write_all(data)
        return True
    return False

# ----------------- 3. Xuất / Nhập Preset (Export / Import) -----------------

def export_preset_json(preset_id: str) -> str:
    """Xuất một Preset ra chuỗi JSON để tải về hoặc chia sẻ."""
    p = get_preset(preset_id)
    if not p:
        raise ValueError("Không tìm thấy quy trình mẫu với ID đã cho.")
    export_payload = {
        "datadesk_preset_version": "1.0",
        "preset": p
    }
    return json.dumps(export_payload, ensure_ascii=False, indent=2)

def import_preset_json(json_content: str) -> dict:
    """Nhập một Preset từ chuỗi JSON hoặc file tải lên."""
    try:
        raw = json.loads(json_content)
    except Exception as e:
        raise ValueError(f"Dữ liệu JSON không hợp lệ: {e}")

    p = raw.get("preset") if isinstance(raw, dict) and "preset" in raw else raw
    if not isinstance(p, dict) or not p.get("name") or not p.get("steps"):
        raise ValueError("File mẫu không đúng cấu trúc DataDesk Preset.")

    new_name = p.get("name") + " (Đã nhập)"
    return save_preset(new_name, p["steps"], p.get("description", ""))

# ----------------- 4. Áp dụng Preset vào Pipeline -----------------

def adapt_steps_with_mapping(steps: List[dict], col_mapping: Dict[str, str]) -> List[dict]:
    """Điều chỉnh tên cột trong các bước của Preset theo ánh xạ cột mới nếu bảng hiện tại khác tên."""
    if not col_mapping:
        return steps

    adapted = []
    for s in steps:
        s_new = dict(s)
        otype = s_new.get("type", "FORMULA")

        if otype == "FORMULA":
            expr = s_new.get("expression", "")
            for src_col, tgt_col in col_mapping.items():
                # Thay thế an toàn [src_col] -> [tgt_col]
                pattern = r"\[" + re.escape(src_col) + r"\]"
                expr = re.sub(pattern, f"[{tgt_col}]", expr)
            s_new["expression"] = expr

        elif otype == "NORMALIZE":
            cols = s_new.get("columns", [])
            s_new["columns"] = [col_mapping.get(c, c) for c in cols]

        elif otype == "CONDITIONAL":
            conds = []
            for c in s_new.get("conditions", []):
                c_copy = dict(c)
                if c_copy.get("col") in col_mapping:
                    c_copy["col"] = col_mapping[c_copy["col"]]
                conds.append(c_copy)
            s_new["conditions"] = conds

            # Cập nhật then/else actions
            for branch in ("then", "else"):
                actions = []
                for a in s_new.get(branch, []):
                    a_copy = dict(a)
                    if a_copy.get("col") in col_mapping:
                        a_copy["col"] = col_mapping[a_copy["col"]]
                    actions.append(a_copy)
                s_new[branch] = actions

        adapted.append(s_new)
    return adapted
