"""Tạo bộ dữ liệu mẫu cho kiểm thử (mục 64 của lộ trình). Chạy: python tests/make_datasets.py"""
import os, csv, datetime as dt
import openpyxl
from openpyxl.styles import PatternFill
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")
def wcsv(name, rows):
    with open(os.path.join(here, name), "w", encoding="utf-8-sig", newline="") as f: csv.writer(f).writerows(rows)
wcsv("simple.csv", [["Mã", "Tên", "Điểm"], ["A1", "An", 4], ["A2", "Bình", 6], ["A3", "Cường", 9], ["A4", "Dũng", 8.5], ["A5", "Em", 3]])
wcsv("orders.csv", [["Mã", "Số lượng", "Đơn giá"], ["D1", 5, 20000], ["D2", 10, 25000], ["D3", 0, 1000], ["D4", 3, 1500], ["D5", 2, 300], ["D6", 7, 100], ["D7", 1, 50], ["D8", 4, 10], ["D9", 6, 30], ["D10", 8, 40], ["D11", 9, 60]])
wcsv("vietnamese.csv", [["Mã KH", "Tên"], ["KH10", "Đức"], ["KH2", "An"], ["KH100", "Ăn"], ["KH7", "Em"], ["KH25", "Dũng"], ["KH3", "Âu"], ["KH1", "Ba"], ["KH4", "bình"]])
wcsv("numbers.csv", [["Rõ", "Mơ hồ", "Hỗn hợp"], ["1.234", "1.234", "1234"], ["2.500", "2.500", "1,234.5"], ["12,5", "3.100", "1.234,5"], ["1.234,5", "1.000", "1000₫"], ["7", "5.500", "1.000.000 VND"], ["8", "6.600", "10%"], ["9", "7.700", "abc"], ["10", "8.800", ""], ["11", "9.900", "5"], ["12", "1.100", "6"], ["13", "2.200", "7"]])
wcsv("dates.csv", [["Việc", "Ngày"], ["a", "31/01/2026"], ["b", "2026-02-28"], ["c", "29/02/2024"], ["d", "31/02/2024"], ["e", ""], ["f", "abc"], ["g", "01/03/2026"], ["h", "15/04/2026"], ["i", "20/05/2026"], ["j", "25/06/2026"], ["k", "30/07/2026"]])
wcsv("dirty_data.csv", [["Mã", "Tên", "Điểm"], ["a1", "  an  ", 5], ["A2", "BÌNH", "N/A"], ["a3", "Cường", 7], ["A4", "", 6], ["", "", ""], ["A6", "Em", 8], ["A7", "Ân", 9], ["A8", "Ba", 4], ["A9", "Dũng", 3], ["A10", "Đức", 10], ["A11", "Hà", 2], ["A12", "Lê", 1]])
wcsv("duplicate.csv", [["Mã", "Tên"], ["A1", "An"], ["A2", "Bình"], ["A1", "An"], ["A3", "Cường"], ["A2", "Dũng"], ["A4", "Em"]])
wcsv("phones.csv", [["Tên", "SĐT"], ["Nguyễn Văn A", "0912 345 678"], ["TRẦN THỊ B", "+84 913 456 789"], ["lê c", "913456780"], ["Phạm D", "84914567890"], ["Hoàng E", "abc"], ["Võ F", "(024) 3123 4567"], ["Đặng G", "0912.345.679"], ["Bùi H", "091 234 5680"], ["Ngô I", "0912345681"], ["Dương K", "+84 912 345 682"], ["Lý L", ""]])
wcsv("emails.csv", [["Tên", "Email"], ["A", " An@Mail.COM "], ["B", "x@y.vn"], ["C", "bad"], ["D", "a b@c.com"], ["E", "Le.Van@Cong-Ty.com.vn"], ["F", ""], ["G", "g@h.io"], ["H", "h@i.net"], ["I", "i@j.org"], ["J", "j@k.edu"], ["K", "k@l.gov"]])
wcsv("dates_mixed.csv", [["Việc", "Ngày"], ["a", "13/03/2026"], ["b", "05/03/2026"], ["c", "2026-03-01"], ["d", "ngày 5 tháng 3 năm 2026"], ["e", "31/02/2026"], ["f", "abc"], ["g", ""], ["h", "7.4.2026"], ["i", "2026/5/9 10:30"], ["j", "29/02/2024"], ["k", "01/06/2026"]])
wcsv("missing_rows.csv", [["Mã", "Tên"], ["001", "A"], ["002", "B"]])      # dùng cho giai đoạn Smart Merge sau này
wcsv("conflict.csv", [["Mã KH", "Tên"], ["001", "Nguyễn Văn B"], ["002", "Trần Thị C"]])
wb = openpyxl.Workbook(); a = wb.active; a.title = "Tháng 1"; a.append(["Mã", "Số"]); [a.append(["M%d" % i, i]) for i in range(1, 4)]
b = wb.create_sheet("Tháng 2"); b.append(["Mã", "Số"]); [b.append(["N%d" % i, i * 10]) for i in range(1, 4)]; wb.save(os.path.join(here, "multi_sheet.xlsx"))
wb = openpyxl.Workbook(); m = wb.active; m.title = "Hỗn hợp"; m.append(["Mã", "Giá", "Ngày", "Ghi chú"])
for r in [["X1", 100, dt.datetime(2026, 1, 5), "ok"], ["X2", "abc", dt.datetime(2026, 2, 5), ""], ["X3", 250.5, None, None], ["X4", 80, dt.datetime(2026, 4, 5), "gấp"]]: m.append(r)
m["B2"].fill = PatternFill("solid", fgColor="FFFFFF00"); wb.save(os.path.join(here, "mixed_types.xlsx"))
print("Đã tạo", len(os.listdir(here)), "file trong", here)
