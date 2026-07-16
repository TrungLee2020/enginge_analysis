# GPR Global Engine

Lượng tử hóa rủi ro địa chính trị từ tin tức/phát ngôn/sự kiện quốc tế → chỉ số định lượng → tín hiệu cho BeaverX. Xây phần **global trước**, tham số Việt Nam sau. Kiến trúc: **1 engine lõi + n bộ tham số quốc gia**.

## Đọc theo thứ tự

1. **`CLAUDE.md`** — nguyên tắc bất biến, đọc trước tiên (Claude Code tự đọc file này).
2. `docs/00_engine_design.md` — thiết kế 3 chân (Media/Statements/Events) + Fusion. **Nguồn chân lý.**
3. `docs/05_build_order.md` — thứ tự làm G1→G7, định nghĩa "done", cổng GO/NO-GO.
4. `docs/01_research_methodology.md` — nền tảng học thuật, danh sách kiểm định.
5. `docs/02_engineering_plan.md` — chi tiết service, schema, rủi ro.

## Bắt đầu (G1)

```bash
# 1. Postgres
psql "$DSN" -f sql/001_schema_core.sql

# 2. Ingest GPR daily (file đã có sẵn, 1985 -> 2026-06-29)
python -m gpr_engine.ingest.gpr_daily --path data/data_gpr_daily_recent.xls --dsn "$DSN"

# 3. Khám phá
jupyter lab notebooks/01_explore.ipynb
```

## Trạng thái

**G1 — ingest chân A.** File daily dùng được ngay. File monthly 44 nước (có `GPRC_VNM`) đang chờ user cung cấp — file hiện có là bản 39 nước, thiếu Vietnam.

## Nguyên tắc sống còn (chi tiết trong CLAUDE.md)

- Research tách Production. Công thức tự phát minh test trước, service hóa sau khi pass cổng.
- Không xây lại GPR — chỉ ingest. Giá trị nằm ở chân B/C + fusion.
- OOS window (2023+) khóa cứng. Mọi kết quả là out-of-sample.
- Phân biệt mục tiêu A (chỉ số — dễ, chắc đạt) vs B (alpha — khó, phải kiểm định).
- Mỗi lớp dữ liệu mới phải chứng minh incremental IC.
