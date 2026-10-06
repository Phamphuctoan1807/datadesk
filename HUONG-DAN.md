# DataDesk: hướng dẫn

## Các file
- `engine.cpp`: bộ xử lý C++ (đọc số/ngày, sắp xếp nhiều cấp, phát hiện trùng, so sánh số)
- `engine.py`: cầu nối Python gọi C++ (ctypes). Chưa biên dịch C++ thì tự dùng bản Python dự phòng
- `server.py`: máy chủ Flask (đăng nhập, API, đọc/ghi Excel, kiểm tra độc lập, gọi AI)
- `static/`: giao diện (`index.html`, `login.html`)
- `Dockerfile`, `render.yaml`: để đưa lên internet

## 1. Chạy thử trên máy
```
pip install -r requirements.txt
```
Đặt mật khẩu rồi chạy (mật khẩu là chữ bạn chọn, không nằm trong code):
- Windows (cmd): `set APP_PASSWORD=mat-khau-cua-ban` rồi `python server.py`
- Mac/Linux: `export APP_PASSWORD=mat-khau-cua-ban` rồi `python3 server.py`

Mở http://127.0.0.1:5000 và nhập mật khẩu. Nếu quên đặt `APP_PASSWORD`, máy chủ tự khóa và báo lỗi.

Biên dịch C++ (tùy chọn khi chạy trên máy, trên Render tự làm):
- Linux: `g++ -O2 -std=c++17 -shared -fPIC -o libddengine.so engine.cpp`
- Mac: như trên nhưng đặt tên `libddengine.dylib`
- Windows (cần MinGW-w64 hoặc MSYS2): `g++ -O2 -std=c++17 -shared -o ddengine.dll engine.cpp`

Góc phải trên của trang hiện "Bộ xử lý: C++" nếu thành công, "Python" nếu chưa.

## 2. AI miễn phí (tùy chọn)
1. Lấy khóa tại aistudio.google.com và đặt biến `AI_API_KEY`.
2. Mặc định dùng Gemini (`AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`, `AI_MODEL=gemini-flash-latest`).
3. Muốn dùng nhà cung cấp khác tương thích OpenAI (Groq, OpenRouter...), đổi 3 biến `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`.
4. Hạn mức miễn phí do nhà cung cấp quy định và có thể thay đổi. Hết hạn mức thì web vẫn chạy bình thường, chỉ phần gợi ý AI báo lỗi.
5. AI chỉ nhận tên cột, kiểu dữ liệu và tối đa 6 dòng mẫu. Đặt `AI_SAMPLE_ROWS=0` để không gửi dòng mẫu nào.

## 3. Đưa lên internet (Render)
1. Tạo repository **Private** trên GitHub và tải toàn bộ thư mục này lên. Không tải file `.env` hay ghi mật khẩu vào code.
2. Vào render.com, chọn **New, Blueprint**, chọn repository. Render đọc `render.yaml` và dựng bằng Dockerfile (tự biên dịch C++).
3. Khi được hỏi, nhập `APP_PASSWORD` (mật khẩu bạn chọn) và `AI_API_KEY` (có thể bỏ trống nếu chưa dùng AI).
4. Đợi vài phút, Render cấp địa chỉ dạng `https://tên.onrender.com`. Gửi link này cho người cần dùng.
5. Đổi mật khẩu sau này: vào Render, mục Environment, sửa `APP_PASSWORD`, lưu để dịch vụ khởi động lại.

Gói miễn phí thường tự "ngủ" khi không có người dùng nên lần mở đầu chậm. Dữ liệu tải lên chỉ nằm trong bộ nhớ 2 giờ rồi bị xóa. Luôn chạy 1 worker (đã đặt sẵn trong Dockerfile).

## 4. Về Google
Mọi trang gửi kèm `noindex` và `robots.txt` chặn công cụ tìm kiếm, nên trang không hiện trên Google. Chỉ người có link và mật khẩu mới vào được.

## 5. Bảo mật
- Mật khẩu đặt trong biến môi trường, so sánh an toàn, phiên đăng nhập 8 giờ, cookie HttpOnly.
- Sai 5 lần trong 10 phút thì khóa tạm theo địa chỉ IP.
- Nên dùng mật khẩu dài và không dựa trên tên bạn.
