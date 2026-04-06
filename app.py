"""
Pothole Detection Server
- Nhận data ổ gà từ Jetson (POST /api/pothole)
- Lưu trữ vào SQLite database
- Serve web dashboard
- API để web frontend fetch data

Deploy miễn phí trên Render.com
"""

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import uuid
import base64
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)  # cho phép cross-origin requests

# ---------- Config ----------
DB_PATH = os.environ.get('DB_PATH', 'potholes.db')
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Database ----------
def get_db():
    """Tạo connection mới cho mỗi request."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Tạo bảng nếu chưa có."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS potholes (
            id TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            confidence REAL NOT NULL,
            vibration REAL DEFAULT 0,
            imu_ax REAL DEFAULT 0,
            imu_ay REAL DEFAULT 0,
            imu_az REAL DEFAULT 0,
            image_path TEXT,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------- API: Nhận data từ Jetson ----------
@app.route('/api/pothole', methods=['POST'])
def add_pothole():
    """
    Nhận data ổ gà từ Jetson.
    
    Body (multipart/form-data):
        - latitude: float
        - longitude: float
        - confidence: float
        - vibration: float
        - imu_ax, imu_ay, imu_az: float
        - timestamp: string
        - image: file (jpg)
    
    Hoặc JSON body với image_base64.
    """
    try:
        # Hỗ trợ cả form-data và JSON
        if request.content_type and 'json' in request.content_type:
            data = request.get_json()
            lat = float(data.get('latitude', 0))
            lon = float(data.get('longitude', 0))
            conf = float(data.get('confidence', 0))
            vibration = float(data.get('vibration', 0))
            imu_ax = float(data.get('imu_ax', 0))
            imu_ay = float(data.get('imu_ay', 0))
            imu_az = float(data.get('imu_az', 0))
            timestamp = data.get('timestamp', datetime.now().strftime("%H:%M:%S %d-%m-%Y"))
            image_b64 = data.get('image_base64', None)
        else:
            lat = float(request.form.get('latitude', 0))
            lon = float(request.form.get('longitude', 0))
            conf = float(request.form.get('confidence', 0))
            vibration = float(request.form.get('vibration', 0))
            imu_ax = float(request.form.get('imu_ax', 0))
            imu_ay = float(request.form.get('imu_ay', 0))
            imu_az = float(request.form.get('imu_az', 0))
            timestamp = request.form.get('timestamp', datetime.now().strftime("%H:%M:%S %d-%m-%Y"))
            image_b64 = None

        pid = str(uuid.uuid4())[:8]
        image_path = None

        # Lưu ảnh từ file upload
        if 'image' in request.files:
            img_file = request.files['image']
            if img_file.filename:
                image_path = f"{pid}.jpg"
                img_file.save(os.path.join(UPLOAD_DIR, image_path))

        # Lưu ảnh từ base64
        elif image_b64:
            image_path = f"{pid}.jpg"
            img_bytes = base64.b64decode(image_b64)
            with open(os.path.join(UPLOAD_DIR, image_path), 'wb') as f:
                f.write(img_bytes)

        # Lưu vào DB
        conn = get_db()
        conn.execute('''
            INSERT INTO potholes (id, latitude, longitude, confidence, vibration,
                                  imu_ax, imu_ay, imu_az, image_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pid, lat, lon, conf, vibration, imu_ax, imu_ay, imu_az, image_path, timestamp))
        conn.commit()
        conn.close()

        print(f"[SAVED] Pothole {pid} at ({lat:.5f}, {lon:.5f}) conf={conf:.2f}")

        return jsonify({
            'status': 'ok',
            'id': pid,
            'message': 'Pothole saved successfully'
        }), 201

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400


# ---------- API: Lấy tất cả data (GeoJSON) ----------
@app.route('/api/potholes', methods=['GET'])
def get_potholes():
    """Trả về tất cả ổ gà dưới dạng GeoJSON."""
    conn = get_db()
    rows = conn.execute('SELECT * FROM potholes ORDER BY created_at DESC').fetchall()
    conn.close()

    features = []
    for row in rows:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            },
            "properties": {
                "id": row['id'],
                "confidence": row['confidence'],
                "vibration": row['vibration'],
                "imu_ax": row['imu_ax'],
                "imu_ay": row['imu_ay'],
                "imu_az": row['imu_az'],
                "time": row['timestamp'],
                "image": f"/api/image/{row['image_path']}" if row['image_path'] else None
            }
        }
        features.append(feature)

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


# ---------- API: Lấy ảnh ----------
@app.route('/api/image/<filename>')
def get_image(filename):
    """Serve ảnh ổ gà."""
    return send_from_directory(UPLOAD_DIR, filename)


# ---------- API: Thống kê ----------
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Thống kê tổng quan."""
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) as cnt FROM potholes').fetchone()['cnt']
    avg_conf = conn.execute('SELECT AVG(confidence) as avg FROM potholes').fetchone()['avg'] or 0
    high_vib = conn.execute('SELECT COUNT(*) as cnt FROM potholes WHERE vibration > 20').fetchone()['cnt']
    conn.close()

    return jsonify({
        'total_potholes': total,
        'avg_confidence': round(avg_conf, 2),
        'high_vibration_count': high_vib
    })


# ---------- API: Xóa 1 pothole ----------
@app.route('/api/pothole/<pid>', methods=['DELETE'])
def delete_pothole(pid):
    """Xóa 1 ổ gà theo ID."""
    conn = get_db()
    row = conn.execute('SELECT image_path FROM potholes WHERE id = ?', (pid,)).fetchone()
    
    if row is None:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

    # Xóa ảnh
    if row['image_path']:
        img_path = os.path.join(UPLOAD_DIR, row['image_path'])
        if os.path.exists(img_path):
            os.remove(img_path)

    conn.execute('DELETE FROM potholes WHERE id = ?', (pid,))
    conn.commit()
    conn.close()

    return jsonify({'status': 'ok', 'message': f'Deleted {pid}'})


# ---------- Serve Web Dashboard ----------
@app.route('/')
def index():
    return send_file('static/index.html')


# ---------- Run ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
