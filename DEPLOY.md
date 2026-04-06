# 🕳️ Pothole Detection - Hướng dẫn Deploy Server

## Kiến trúc hệ thống

```
Jetson Nano (run.py)
    │
    │ POST /api/pothole (JSON + ảnh base64)
    ▼
Flask Server (Render.com - miễn phí)
    │
    ├── SQLite Database (lưu data ổ gà)
    ├── uploads/ (lưu ảnh)
    └── Web Dashboard (serve static HTML)
         │
         ▼
    Trình duyệt (xem bản đồ + danh sách)
```

## 1. Deploy lên Render.com (Miễn phí)

### Bước 1: Chuẩn bị GitHub repo

```bash
# Tạo repo mới trên GitHub, sau đó:
cd server
git init
git add .
git commit -m "Initial server"
git remote add origin https://github.com/<username>/pothole-server.git
git push -u origin main
```

### Bước 2: Tạo Web Service trên Render

1. Vào [https://render.com](https://render.com) → Đăng ký miễn phí
2. Click **"New" → "Web Service"**
3. Kết nối GitHub repo vừa tạo
4. Cấu hình:
   - **Name**: `pothole-server`
   - **Region**: Singapore (gần Việt Nam nhất)
   - **Branch**: `main`
   - **Root Directory**: (để trống nếu repo chỉ chứa server/)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: **Free**

5. Click **"Create Web Service"**

### Bước 3: Lấy URL

Sau khi deploy xong, Render sẽ cấp URL dạng:
```
https://pothole-server.onrender.com
```

> ⚠️ **Lưu ý Free tier**: Server sẽ "ngủ" sau 15 phút không có request.
> Request đầu tiên sau khi ngủ sẽ mất ~30s để khởi động lại.

## 2. Cấu hình Jetson Nano

### Cách 1: Biến môi trường

```bash
export POTHOLE_SERVER="https://pothole-server.onrender.com"
python3 run.py
```

### Cách 2: Chỉnh trực tiếp trong run.py

Mở `run.py`, tìm dòng:
```python
SERVER_URL = os.environ.get("POTHOLE_SERVER", "")
```

Đổi thành:
```python
SERVER_URL = os.environ.get("POTHOLE_SERVER", "https://pothole-server.onrender.com")
```

### Cài thêm thư viện trên Jetson

```bash
pip3 install requests
```

## 3. Truy cập Web Dashboard

Mở trình duyệt, vào:
```
https://pothole-server.onrender.com
```

Dashboard sẽ:
- 🗺️ Hiển thị bản đồ với các điểm ổ gà
- 📊 Bảng danh sách có sort/filter
- 🔄 Tự động refresh mỗi 30 giây
- 📸 Xem ảnh ổ gà trong popup

## 4. API Endpoints

| Method | URL | Mô tả |
|--------|-----|--------|
| `POST` | `/api/pothole` | Gửi data ổ gà mới (từ Jetson) |
| `GET` | `/api/potholes` | Lấy tất cả ổ gà (GeoJSON) |
| `GET` | `/api/stats` | Thống kê tổng quan |
| `GET` | `/api/image/<filename>` | Lấy ảnh ổ gà |
| `DELETE` | `/api/pothole/<id>` | Xóa 1 ổ gà |

### Ví dụ gửi data bằng curl:

```bash
curl -X POST https://pothole-server.onrender.com/api/pothole \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 13.77,
    "longitude": 109.21,
    "confidence": 0.85,
    "vibration": 15.3,
    "imu_ax": 100,
    "imu_ay": -200,
    "imu_az": 16000,
    "timestamp": "14:30:00 01-01-2025"
  }'
```

## 5. Các lựa chọn hosting miễn phí khác

| Dịch vụ | Ưu điểm | Nhược điểm |
|---------|---------|------------|
| **Render.com** ✅ | Dễ deploy, có disk storage | Server ngủ sau 15p |
| **Railway.app** | 500h/tháng miễn phí | Giới hạn giờ chạy |
| **Fly.io** | 3 VM miễn phí, nhanh | Cần cài CLI |
| **PythonAnywhere** | Python native, dễ dùng | Giới hạn outbound HTTP |
| **Vercel** | Rất nhanh, edge network | Chỉ hỗ trợ serverless |

## 6. Nâng cấp (tùy chọn)

### Dùng PostgreSQL thay SQLite (Supabase)

1. Tạo tài khoản [supabase.com](https://supabase.com) (miễn phí)
2. Tạo project mới → lấy connection string
3. Thay `sqlite3` bằng `psycopg2` trong `app.py`
4. Set env var trên Render: `DATABASE_URL=postgresql://...`

### Thêm bảo mật API

Thêm API key để chỉ Jetson mới gửi được data:

```python
# Trong app.py
API_KEY = os.environ.get("API_KEY", "my-secret-key")

@app.before_request
def check_api_key():
    if request.path.startswith('/api/pothole') and request.method == 'POST':
        key = request.headers.get('X-API-Key')
        if key != API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
```

```python
# Trong run.py - thêm header
headers = {"X-API-Key": "my-secret-key"}
resp = requests.post(url, json=payload, headers=headers, timeout=10)
```
