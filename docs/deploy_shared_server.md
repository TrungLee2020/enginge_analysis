# Triển khai engine cùng server với repport_v2 + search_core

Ngày 2026-10-30. Engine chạy thành **project docker compose riêng** (`docker-compose.prod.yml`),
nối vào mạng `shared-infra` có sẵn của repport_v2. Không gộp code vào repport_v2: hai bên chỉ nói
chuyện qua Kafka và một database Postgres; registry khóa, vintage dữ liệu và pin
`statsmodels<0.15` của engine không lẫn vào dependency của repport_v2.

```
repport_v2 collect_gpr ──► Kafka gpr.news.raw ──► gpr-engine-app ──► Kafka gpr.news.assessment
        │                     (kafka:29092, shared-infra)    │
        │                                                     └──► Postgres DB gpr_engine
        └── data/gdelt_events ──(mount chỉ đọc)──► ingest.gdelt_events ──┘     (bảng news_assessment)
                                                                                  │
repport_v2 báo cáo ◄──────────── đọc news_assessment (role chỉ đọc) ◄──────────────┘
```

## Hạ tầng dùng lại

| Thành phần | Giá trị | Ghi chú |
|---|---|---|
| Kafka | `kafka:29092` | listener nội bộ trên `shared-infra`, cùng giá trị repport_v2 đặt trong `KAFKA_BOOTSTRAP_SERVERS` |
| Postgres | container `shared-postgres-report`, database **`gpr_engine`** | cùng instance với DB `report`, khác database |
| GDELT slots | `${REPPORT_V2_DIR:-/opt/repport_v2}/data/gdelt_events` | collector ghi, engine đọc |

## Lần đầu

Chạy trong thư mục engine trên server, ví dụ `/opt/enginge_analysis`.

1. Database và schema (`init-multi-db.sh` của repport_v2 chỉ chạy khi volume Postgres còn trống,
   nên trên server đang chạy phải tạo tay):

   ```bash
   docker exec shared-postgres-report psql -U postgres -c "CREATE DATABASE gpr_engine"
   ```

   ```bash
   docker exec -i shared-postgres-report psql -U postgres -d gpr_engine < sql/001_schema_core.sql
   ```

   ```bash
   docker exec -i shared-postgres-report psql -U postgres -d gpr_engine < sql/002_schema_serving.sql
   ```

2. Role chỉ đọc cho repport_v2 (báo cáo chỉ cần đọc kết quả, không được ghi vào engine):

   ```bash
   docker exec -i shared-postgres-report psql -U postgres -d gpr_engine <<'SQL'
   CREATE ROLE report_reader LOGIN PASSWORD 'doi-mat-khau-nay';
   GRANT CONNECT ON DATABASE gpr_engine TO report_reader;
   GRANT USAGE ON SCHEMA public TO report_reader;
   GRANT SELECT ON news_assessment, statements, statement_scores, ladder_state TO report_reader;
   SQL
   ```

3. `.env` (cùng thư mục, không commit):

   ```
   GPR_DB_DSN=postgresql://postgres:<mật khẩu>@shared-postgres-report:5432/gpr_engine
   OPENAI_API_KEY=...            # hoặc OPENAI_BASE_URL=http://<vllm>/v1 + key của vLLM
   GPR_LLM_MODEL=gpt-4o-mini     # hoặc tên model trên vLLM
   GPR_TRAINING_CUTOFF=2026-01-01
   ```

   Host trong DSN là `shared-postgres-report`, không phải `localhost`: bên trong container,
   `localhost` là chính container app. Kafka không đặt ở đây; `docker-compose.prod.yml` cố định
   `kafka:29092`.

4. Topic: nếu broker tắt auto-create, tạo trước. Đổi tên container Kafka cho đúng server; đường dẫn `kafka-topics.sh` là của image `apache/kafka`, image Confluent dùng lệnh `kafka-topics` trần:

   ```bash
   docker exec <kafka-container> /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic gpr.news.raw --partitions 1 --replication-factor 1
   ```

   ```bash
   docker exec <kafka-container> /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic gpr.news.assessment --partitions 1 --replication-factor 1
   ```

5. Build, nạp dữ liệu chân A, chạy:

   ```bash
   docker compose -f docker-compose.prod.yml build
   ```

   ```bash
   docker compose -f docker-compose.prod.yml run --rm app sh -c 'python -m gpr_engine.ingest.gpr_daily --dsn "$GPR_DB_DSN" && python -m gpr_engine.ingest.gpr_monthly --dsn "$GPR_DB_DSN" && python -m gpr_engine.ingest.ai_gpr --dsn "$GPR_DB_DSN" && python -m gpr_engine.ingest.market_data --dsn "$GPR_DB_DSN" --source fred'
   ```

   ```bash
   docker compose -f docker-compose.prod.yml up -d app
   ```

   `sh -c '... "$GPR_DB_DSN"'` để biến giãn **trong** container (compose bơm nó vào đó); gõ
   `"$GPR_DB_DSN"` trần trên host sẽ thành chuỗi rỗng.

## Định kỳ

- **GDELT Events → DB** (chân C, chưa nối Ladder — CLAUDE.md #6), mỗi ngày sau 01:00 UTC:

  ```bash
  docker compose -f docker-compose.prod.yml run --rm app sh -c 'python -m gpr_engine.ingest.gdelt_events --path data/gdelt_events --dsn "$GPR_DB_DSN"'
  ```

- **Vintage GPR mới** (file tải tay): commit file vào `data/GPR index/` theo `data/README.md`,
  rồi chạy lại hai lệnh ingest `gpr_daily` / `gpr_monthly` — `versioning.py` archive giá trị bị
  revise.

## Kiểm tra

```bash
docker logs --tail 20 gpr-engine-app
```

Dòng đầu phải là `[run_news_service] gpr.news.raw -> gpr.news.assessment @ kafka:29092`.
Sau khi collector repport_v2 publish (`collect_gpr.py publish`), bảng `news_assessment` có hàng mới:

```bash
docker exec shared-postgres-report psql -U postgres -d gpr_engine -c "SELECT generated_at, ladder_state, left(vn_note, 80) FROM news_assessment ORDER BY generated_at DESC LIMIT 5"
```

## Thứ tự deploy

engine (branch có `DEC-2026-10-29-role-init`) → search_core → repport_v2. Collector chạy trước
engine mới thì đặt `GPR_ENGINE_ROLES=head_of_state,minister,spokesperson,central_bank_governor`
bên repport_v2, để không gửi role engine cũ chưa biết.
