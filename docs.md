# 📚 Tài Liệu Hướng Dẫn & Chi Tiết Dự Án: ShopBot v2.0

> **Cập nhật lần cuối:** 11/03/2026 (GMT+7)
> **Mục tiêu:** Telegram Bot bán Key API (NewAPI) & Tài Khoản Số tự động 100%, tích hợp Web Admin Panel.

---

## 🌟 1. Tổng Quan Chức Năng Hiện Tại

Hệ thống ShopBot chia làm 2 hệ sinh thái tương tác với nhau qua chung Database (SQLite WAL) và Python (FastAPI + aiogram).

### 1.1 Tính năng Khách Hàng (Telegram Bot)
- **🛍️ Mua Key API Đa Máy Chủ:** Hỗ trợ nhiều cụm Server API. Cho phép mua Key mới hoặc Nạp thêm Quota vào Key cũ.
- **🎛️ Nạp Tiền Tuỳ Chọn (Custom Dollar):** Khách hàng tự nhập số đô (`$`) muốn nạp, Bot tự động quy đổi ra VNĐ và tính toán Quota chuẩn xác dựa theo cấu hình từng Server.
- **📦 Kho Tài Khoản (Account Stocks):** Tự động giao tài khoản (ChatGPT, Netflix...) ngay khi thanh toán xong.
- **🛒 Đặt Hàng Tránh Trùng (Reservation):** Khi khách bấm mua tài khoản, Bot sẽ "xí chỗ" acc đó trong 30 phút. Tránh tình trạng quá tải hoặc giao trùng acc cho 2 người.
- **💳 Thanh Toán Siêu Tốc:** 
  - **VietQR:** Quét mã QR, tự động đối soát giao dịch MBBank (khoảng 10-15s).
  - **Ví Nội Bộ (Wallet):** Tính năng nạp ví và trừ tiền thẳng vào ví cực tiện lợi.
- **🧭 Menu Lệnh Hiện Đại:** Menu cố định bên góc góc trái màn hình (`/products`, `/wallet`, `/orders`, `/search`, `/profile`, `/support`).
- **🕰️ Múi Giờ Chuẩn:** Mọi thông tin thời gian hiển thị hoàn toàn theo giờ Việt Nam (GMT+7).

### 1.2 Tính năng Admin (Web Panel)
- **🔐 Bảo Mật Cấp Độ Cao:** 
  - Đường dẫn đăng nhập bị làm mờ (Obfuscated Login URL).
  - Khóa IP (Rate Limiter) nếu nhập sai quá 5 lần.
  - Session băm bí mật (`secrets.token_hex(32)`), mật khẩu quản trị mã hóa chuẩn SHA-256.
  - Toàn bộ Router khóa bằng Middleware Auth, miễn nhiễm các truy cập rác.
- **⚙️ Quản Định Dạng Linh Hoạt:** Nhập Hàng, Sinh Sản Phẩm tự động theo Mức giá Đô (`$`), tính năng Smart Fields ẩn/hiện trường nhập liệu tùy loại sản phẩm.
- **💼 Quản Lý Giao Dịch & Đơn Dịch Vụ:** Nút xác nhận nhanh. Đặc biệt: **Nút Hoàn Tiền (Refund)** chuyển lập tức tiền về Ví nội bộ cho khách. Có nút nhắn tin thẳng vào Telegram khách.
- **📉 Thống Kê & Giám Sát:** Nắm bắt toàn bộ doanh thu theo ngày, Quotas, Tồn kho (ngừng nhập khi Stock hết). Check sức khoẻ Server qua API `/health`.

---

## 🛠 2. Hướng Dẫn Cài Đặt (VPS Ubuntu)

Mã nguồn được viết bằng Python 3.12+, framework `aiogram` và `FastAPI`, database `aiosqlite`.

### Bước 1: Chuẩn bị môi trường
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
```

### Bước 2: Tải Source Code & Tạo Virtual Environment
Đẩy mã nguồn lên VPS tại thư mục `/home/ubuntu/shopbot/`.
```bash
cd /home/ubuntu/shopbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Bước 3: Cấu hình Môi Trường (`.env`)
Copy từ file `.env.example` sang `.env` và điền thông số:
```ini
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
DB_PATH=shopbot.db

# Bảo mật Admin
ADMIN_SECRET_KEY=khoa-bao-mat-session-32-byte-bat-ky
ADMIN_PORT=8080
ADMIN_LOGIN_PATH=/login-shopbot-admin
ADMIN_TELEGRAM_IDS=123456789,987654321

# MBBank API
MB_API_URL=https://apicanhan.com/api/mbbankv3
MB_API_KEY=YOUR_API_KEY
MB_USERNAME=03x
MB_PASSWORD=pass_mbbank
MB_ACCOUNT_NO=STK
MB_ACCOUNT_NAME=NGUYEN VAN A
MB_BANK_ID=MB
```

### Bước 4: Chạy Dịch Vụ (Systemd)
Tạo file service để Bot luôn chạy ngầm và tự bật lại khi khởi động lại VPS.
```bash
sudo nano /etc/systemd/system/shopbot.service
```
Nội dung file:
```ini
[Unit]
Description=ShopBot Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/shopbot
ExecStart=/home/ubuntu/shopbot/.venv/bin/python -m bot.main
Restart=always

[Install]
WantedBy=multi-user.target
```
Lưu lại (Ctrl+O, Enter, Ctrl+X) và khởi chạy:
```bash
sudo systemctl daemon-reload
sudo systemctl enable shopbot
sudo systemctl start shopbot
sudo systemctl status shopbot
```

---

## 💻 3. Hướng Dẫn Sử Dụng (Dành Cho Admin)

1. **Truy cập Panel:** Vào `http://<IP-VPS>:8080/login-shopbot-admin` (Dùng mật khẩu mặc định là `admin123` ở lần chạy đầu tiên, nhớ vào Settings để đổi).
2. **Khai báo Máy Chủ API:** Sang tab **API Servers**, thêm Server API (aabao/newapi) cùng Access Token.
3. **Danh mục & Sản phẩm:**
   - Qua tab **Categories**, tạo danh mục.
   - Qua tab **Products**, tạo sản phẩm. Bạn có thể chọn loại `Key Mới`, `Nạp Tiền (Topup)`, `Tài khoản Stock`, hoặc `Dịch vụ Thủ công`.
4. **Nhập Tồn Kho (Accounts):** Với sản phẩm dạng Stock, vào tab **Tài Khoản Số**, chọn dán hàng chục account theo định dạng tùy chọn (Mỗi dòng 1 Account).
5. **Đơn Hàng & Xử lý:** Khi có khách nạp qua Ví hoặc quét VietQR, đơn hàng nhảy sang `Tiến hành`. Với đơn Tài khoản/Key, hệ thống giao 100% tự động. Với đơn Dịch vụ, bạn tự thao tác và bấm *Hoàn Thành* hoặc *Hoàn Tiền (Refund)*.

---

## 📖 4. Lịch Sử & Quá Trình Phát Triển Tới Hiện Tại

Project đã trải qua **13 Giai Đoạn (Phases)** tiến hóa lớn để từ 1 mã nguồn cơ sở trở thành bản Production chuẩn doanh nghiệp.

* **Phases 1-4 (Nền Móng & Đa Máy Chủ):** 
  Xây dựng lõi API MBBank Poller và hệ thống Menu. Đập bỏ thiết kế cũ để kiến trúc lại hệ thống Máy Chủ (Multi-servers), cho phép Bot mua Key/Nạp Key ở vô vàn Server cùng lúc bằng hệ thống Custom Dollar thông minh. Nâng cấp UI Admin.

* **Phases 5-6 (Trải Nghiệm Dịch Vụ):**
  Hoàn thiện các luồng "Dịch vụ thủ công". Xây dựng nút Hủy & Hoàn Tiền nhanh chóng gạch nợ cho khách nếu Admin không có hàng trỏ trả. Ghim Menu Commands `/products`, `/wallet` trực tiếp vào khung chat Telegram.

* **Phases 7-8 (Đồng bộ Tồn Kho & Xí Chỗ):**
  Cách ly bảng `chatgpt_accounts` rác cũ, thay bằng `account_stocks` đa năng. Đập đi tính Tồn kho tĩnh (`stock`), sửa lại đếm trực tiếp (`COUNT`) số lượng thẻ chưa bán hiện thẳng vào UI Telegram. Xây dựng cơ chế *Lock (Reserve)* tài khoản trong 30 phút để chống vỡ kho khi có người mở nhiều hóa đơn cùng lúc.

* **Phases 9-10 (Kiểm Định & Vá Lỗ Hổng Bảo Mật):**
  Phát hiện các lỗ hổng Critical. Sửa gấp lỗi mã hóa Password từ Plaintext sang SHA-256 Auth. Thay API Endpoint mặc định (`/login`) thành Endpoint tàng hình có Rate Limiting IP (Chặn brute-force). Kẹp khóa Guard Auth vào toàn bộ Router để chặn các lệnh gọi tắt tàng hình của Hacker.

* **Phases 11-12 (Tối Ưu Hiển Thị & GMT+7):**
  Sửa UX bàn phím Telegram cho Danh mục bị dài chữ (Co gọn thành 1 dòng lớn). Đánh chiếm và đè lại định dạng Múi Giờ Quốc Tế (UTC+0) thành chuỗi GMT+7 trên các giao diện Admin Panel & Box Chat Telegram để tiện đối chiếu với giờ địa phương Việt Nam.

* **Phase 13 (Refactoring Phiên Bản Chuyên Nghiệp):**
  Đưa kiến trúc Database và Poller quay về chuẩn UTC Thuần Tùy. Tránh lỗi nổ chậm khi chênh giờ với các hệ thống Server Linux. Sát nhập hàng trăm dòng Code bị phân mảnh (`products.py` và `flow_api_key.py`). Ghim cứng tất cả các bản version của thư viện Python (Pin requirements) và bổ sung lệnh gọi tự kiểm tra sức khỏe VPS (`/health`). 
  -> **Phiên bản hoàn hảo để chạy Production lớn.**