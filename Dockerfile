# Dockerfile — GPR Global Engine, ảnh production cho pipeline serving
# ("1 tin vào -> GPR + khuyến nghị vĩ mô/VN, đẩy Kafka") + các script ingest.
#
# Build:  docker build -t gpr-engine .
# Chạy pipeline serving (mặc định):
#   docker run --env-file .env gpr-engine
# Chạy một script khác (vd ingest) — override CMD:
#   docker run --env-file .env -v "$(pwd)/data:/app/data" gpr-engine \
#       python -m gpr_engine.ingest.gpr_daily --path data/data_gpr_daily_recent.xls --dsn "$GPR_DB_DSN"
#
# Xem docker-compose.yml cho bộ chạy đầy đủ (Postgres + Kafka KRaft + app)
# dùng khi phát triển/thử nghiệm cục bộ.

# --- Stage 1: builder — cài dependency vào venv riêng, có build tool nếu cần
# compile (statsmodels/arch/confluent-kafka thường có wheel sẵn, nhưng giữ
# build-essential làm lưới an toàn — không lọt vào ảnh cuối). ---
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
# Cai THUONG (khong -e): dong goi vao site-packages cua venv, KHONG phu
# thuoc thu muc build con o day hay khong sau khi copy venv sang stage sau
# (editable install se hong o day — .pth cua no tro ve /build/src, thu muc
# nay khong ton tai trong stage runtime).
RUN pip install --no-cache-dir .

# --- Stage 2: runtime — ảnh gọn, không có build-essential ---
FROM python:3.11-slim AS runtime

# psycopg2-binary tự mang libpq tĩnh, không cần libpq-dev ở runtime.
RUN useradd --create-home --shell /bin/bash gpr

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Code + cấu hình + bảng γ đã công bố (docs/reports/data — gamma_lookup.py cần
# đọc file này ngay khi container khởi động, KHÔNG tự ước lượng lại).
# KHÔNG copy data/ (file GPR .xls/.csv gitignored, chủ) — mount qua volume
# lúc `docker run -v` hoặc docker-compose (xem README/CLAUDE.md).
COPY src/ src/
COPY scripts/ scripts/
COPY sql/ sql/
COPY config/ config/
COPY pyproject.toml .
COPY docs/reports/data/ docs/reports/data/

RUN mkdir -p data/cache && chown -R gpr:gpr /app
USER gpr

# Không có ENTRYPOINT cố định — CMD mặc định chạy pipeline serving, nhưng
# `docker run <image> <lệnh khác>` (vd ingest script) ghi đè trực tiếp, không
# cần sửa Dockerfile hay thêm cờ đặc biệt.
CMD ["python", "scripts/run_news_service.py"]
