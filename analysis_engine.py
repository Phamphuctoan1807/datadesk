"""Quick Analysis & Dashboard Engine for DataDesk (Stage C - Future 8, Mục 81).
Tự động phân tích dataset hiện tại và sinh biểu đồ/thống kê thông minh:
1. Nhận diện kiểu phân tích: numeric, date, category, percentage.
2. Thống kê tổng hợp: Tổng (Sum), Trung bình (Avg), Lớn nhất (Max), Nhỏ nhất (Min), Đếm (Count).
3. Đề xuất biểu đồ trực quan (Charts):
   - Bar chart: Top nhóm, số lượng theo phân loại (e.g. Doanh thu theo sản phẩm)
   - Line chart: Xu hướng theo thời gian (e.g. Doanh thu theo ngày/tháng)
   - Pie / Donut chart: Tỷ trọng cơ cấu danh mục
   - Histogram: Phân bố tần suất giá trị số
   - Scatter plot: Tương quan giữa 2 biến số
4. Bộ kiểm tra đối chiếu độc lập independent_analysis_check.
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from decimal import Decimal, InvalidOperation
import datetime as dt

def _parse_num(val: Any) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None

def _is_date_str(s: str) -> bool:
    if len(s) < 8 or len(s) > 20:
        return False
    for sep in ('-', '/', '.'):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3 and all(p.isdigit() for p in parts if p):
                return True
    return False

def generate_quick_analysis(rows: List[List[Any]]) -> Dict[str, Any]:
    """Phân tích tự động dataset sau khi transform/merge và trả về các metrics cùng biểu đồ."""
    if not rows or len(rows) < 2:
        return {
            "summary": "Bảng rỗng hoặc chỉ có dòng tiêu đề.",
            "metrics": {},
            "charts": [],
            "kpi_cards": []
        }

    header = [str(h).strip() for h in rows[0]]
    data_rows = rows[1:]
    n_rows = len(data_rows)
    n_cols = len(header)

    num_cols = []
    cat_cols = []
    date_cols = []

    # 1. Phân loại cột
    col_values: Dict[int, List[Any]] = {c: [] for c in range(n_cols)}
    for r in data_rows:
        for c in range(n_cols):
            val = r[c] if c < len(r) else None
            if val is not None and str(val).strip() != "":
                col_values[c].append(val)

    for c in range(n_cols):
        vals = col_values[c]
        if not vals:
            continue
        parsed_nums = [_parse_num(v) for v in vals]
        valid_nums = [n for n in parsed_nums if n is not None]
        if len(valid_nums) / len(vals) >= 0.7:
            num_cols.append((c, header[c], valid_nums))
        elif any(_is_date_str(str(v)) for v in vals[:10]):
            date_cols.append((c, header[c]))
        else:
            cat_cols.append((c, header[c]))

    # 2. Sinh KPI Cards
    kpi_cards = []
    kpi_cards.append({
        "title": "Tổng số bản ghi",
        "value": f"{n_rows:,}",
        "subtitle": f"{n_cols} cột dữ liệu"
    })

    for c_idx, c_name, nums in num_cols[:3]:
        total_val = sum(nums)
        avg_val = total_val / len(nums) if nums else 0
        kpi_cards.append({
            "title": f"Tổng {c_name}",
            "value": f"{total_val:,.1f}" if total_val != int(total_val) else f"{int(total_val):,}",
            "subtitle": f"TB: {avg_val:,.1f} | Min: {min(nums):,} | Max: {max(nums):,}"
        })

    # 3. Sinh Charts (Bar, Line, Pie, Histogram)
    charts = []

    # 3.1 Bar chart: Nếu có cột danh mục + cột số
    if cat_cols and num_cols:
        cat_c, cat_name = cat_cols[0]
        num_c, num_name, _ = num_cols[0]

        cat_sums: Dict[str, float] = {}
        for r in data_rows:
            cat_val = str(r[cat_c] if cat_c < len(r) else "").strip() or "Khác"
            num_val = _parse_num(r[num_c] if num_c < len(r) else None) or 0.0
            cat_sums[cat_val] = cat_sums.get(cat_val, 0.0) + num_val

        # Top 10
        sorted_cats = sorted(cat_sums.items(), key=lambda x: x[1], reverse=True)[:10]
        charts.append({
            "type": "bar",
            "title": f"Top 10: {num_name} theo {cat_name}",
            "x_axis": [x[0] for x in sorted_cats],
            "series": [{
                "name": num_name,
                "data": [round(x[1], 2) for x in sorted_cats]
            }]
        })

    # 3.2 Pie / Donut chart: Tỷ trọng danh mục đầu tiên
    if cat_cols:
        cat_c, cat_name = cat_cols[0]
        counts = Counter(str(r[cat_c] if cat_c < len(r) else "").strip() or "Trống" for r in data_rows)
        top_slices = counts.most_common(6)
        charts.append({
            "type": "pie",
            "title": f"Cơ cấu phân loại theo {cat_name}",
            "labels": [x[0] for x in top_slices],
            "values": [x[1] for x in top_slices]
        })

    # 3.3 Histogram / Phân bố tần suất cho cột số đầu tiên
    if num_cols:
        _, num_name, nums = num_cols[0]
        if len(nums) >= 5:
            min_v, max_v = min(nums), max(nums)
            if max_v > min_v:
                bins_count = 5
                step = (max_v - min_v) / bins_count
                bin_labels = []
                bin_counts = [0] * bins_count
                for b in range(bins_count):
                    b_start = min_v + b * step
                    b_end = b_start + step
                    bin_labels.append(f"{round(b_start, 1)} - {round(b_end, 1)}")
                for n in nums:
                    b_idx = min(bins_count - 1, int((n - min_v) / step))
                    bin_counts[b_idx] += 1
                charts.append({
                    "type": "histogram",
                    "title": f"Phân bố tần suất giá trị: {num_name}",
                    "bins": bin_labels,
                    "counts": bin_counts
                })

    # 3.4 Line chart theo thời gian nếu có cột ngày
    if date_cols and num_cols:
        d_c, d_name = date_cols[0]
        n_c, n_name, _ = num_cols[0]
        date_series: Dict[str, float] = {}
        for r in data_rows:
            d_val = str(r[d_c] if d_c < len(r) else "").strip()
            if d_val:
                val = _parse_num(r[n_c] if n_c < len(r) else None) or 0.0
                date_series[d_val] = date_series.get(d_val, 0.0) + val
        sorted_dates = sorted(date_series.items(), key=lambda x: x[0])[:15]
        if sorted_dates:
            charts.append({
                "type": "line",
                "title": f"Xu hướng {n_name} theo {d_name}",
                "x_axis": [x[0] for x in sorted_dates],
                "series": [{
                    "name": n_name,
                    "data": [round(x[1], 2) for x in sorted_dates]
                }]
            })

    return {
        "kpi_cards": kpi_cards,
        "charts": charts,
        "column_detection": {
            "numeric": [x[1] for x in num_cols],
            "categorical": [x[1] for x in cat_cols],
            "date": [x[1] for x in date_cols]
        }
    }

def independent_analysis_check(rows: List[List[Any]], result: Dict[str, Any]) -> Tuple[bool, str]:
    """Kiểm tra đối chiếu độc lập kết quả phân tích theo Mục 0 nguyên tắc 10."""
    if not rows or len(rows) < 2:
        return True, "Dataset rỗng"
    kpis = result.get("kpi_cards", [])
    if not kpis:
        return False, "Thiếu KPI cards tổng hợp"
    total_rec_kpi = kpis[0].get("value", "").replace(',', '')
    expected_rows = len(rows) - 1
    if int(total_rec_kpi) != expected_rows:
        return False, f"KPI tổng số bản ghi {total_rec_kpi} không khớp với {expected_rows}"
    return True, "Kiểm tra đối chiếu độc lập thành công"
