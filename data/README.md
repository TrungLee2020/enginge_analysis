# data/

Không commit file dữ liệu lớn ngoài danh sách dưới (xem `.gitignore`).

Layout hiện tại (đổi 2026-08-08, commit `e3bde3b` — code đã trỏ theo, xem
`econometrics/data_files.py` phần hằng số `DEFAULT_*`):

```
data/
├── GPR index/          # GPR gốc Caldara-Iacoviello
├── AI-GPRs/            # AI-GPR (Iacoviello & Tong 2026)
└── cache/              # cache FRED, sinh tự động
```

## `GPR index/`

| File | Nội dung | Phủ | Vintage (sha256[:12]) |
|---|---|---|---|
| `data_gpr_daily_recent (1).xls` | GPRD/GPRD_ACT/GPRD_THREAT daily, 15.190 hàng × 11 cột | 1985-01-01 → **2026-08-03** | `a429b2431795` |
| `data_gpr_export_202608.xls` | 44 nước monthly, 1.519 × 115 (44 `GPRC_*` recent 1985+, 44 `GPRHC_*` historical 1900+, có `GPRC_VNM`/`GPRHC_VNM`, global GPR/GPRT/GPRA/GPRH/GPRHT/GPRHA) | 1900-01 → **2026-07** | `f57e78baf651` |
| `data_gpr_export (1).xls` | ⚠️ **Bản trùng** của file trên — kiểm 2026-08-08: giống **từng ô** trên cả 112 cột số (0 ô lệch) | 1900-01 → 2026-07 | `49eaf46fb70a` |

- `data_gpr_daily_recent (1).xls` — GPRD/GPRD_ACT/GPRD_THREAT daily,
  **1985-01-01 → 2026-08-03** (15190 dòng). `DEFAULT_GPR_DAILY`.
  Hậu tố `(1)` là do trình duyệt thêm khi tải; đổi tên file thì phải sửa hằng số
  cùng lúc, không có fallback ngầm.
- `data_gpr_export_202608.xls` — bản 44 nước monthly **1900-01 → 2026-07**
  (1519×115). `DEFAULT_GPR_MONTHLY`. Gồm 44 cột `GPRC_*` (recent 1985+) + 44
  `GPRHC_*` (historical 1900+), có `GPRC_VNM`/`GPRHC_VNM`, và global
  GPR/GPRT/GPRA/GPRH/GPRHT/GPRHA. Cột dictionary: `var_name`/`var_label`.
  Nguồn: matteoiacoviello.com/gpr_country.htm
- `data_gpr_export (1).xls` — **trùng nội dung** với file trên (đã đối chiếu
  `assert_frame_equal`, chỉ khác byte). Không dùng; giữ lại thì vô hại.

`DEFAULT_GPR_MONTHLY` trỏ `data_gpr_export_202608.xls` (tên có vintage, không nhập
nhằng). Xóa được `data_gpr_export (1).xls` — giữ hai bản trùng chỉ làm resolver
phải đoán.

## `AI-GPRs/` — AI-GPR (Iacoviello & Tong 2026)

Chỉ số tổng hợp (`DEFAULT_AI_GPR_DAILY` / `_MONTHLY`):

| File | Kích thước | Nhịp | Phủ | Vintage |
|---|---|---|---|---|
| `ai_gpr_data_daily.csv` | 24.319 × 15 | daily | 1960-01-01 → 2026-07-31 | `13b8e8b48d41` |
| `ai_gpr_data_monthly.csv` | 799 × 15 | monthly | 1960-01 → 2026-07 | `92b9ba3bd38f` |

Country Decompositions (4 file, đã có loader trong `data_files.py`):

| File | Kích thước | Nhịp | Phủ | Vintage |
|---|---|---|---|---|
| `ai_gpr_eventtype_monthly.csv` | 799 × 10 | monthly | 1960-01 → 2026-07 | `4e6ad63e48c7` |
| `ai_gpr_country_monthly.csv` | 799 × 802 | monthly | 1960-01 → 2026-07 | `22750ad1e1bf` |
| `ai_gpr_country_eventtype_monthly.csv` | 799 × 1.602 | monthly | 1960-01 → 2026-07 | `dd4bace497a0` |
| `ai_gpr_bilateral_monthly.csv` | 799 × 1.202 | monthly | 1960-01 → 2026-07 | `e3c6185d0e40` |

⚠️ **Bốn file "Country Decompositions" (country/bilateral/eventtype) là MONTHLY** —
nguyên tắc #10 cấm forward-fill xuống daily, nên chúng chỉ vào track tháng.
Chi tiết: `docs/17_master_plan.md` §A2.

Ghim vintage bằng `data_files.ai_gpr_vintage(path)` (hash file) — trang nguồn cập
nhật định kỳ mà URL không đổi, không ghim thì report cũ mất tái lập (#7).

⚠️ `matteoiacoviello.com` bị chặn ở egress policy của sandbox Claude Code —
file AI-GPR phải tải tay.

## Đổi vintage

**Phía research (file → report):** `DEFAULT_GPR_*` được `_data_version()` băm byte
để đặt tên report (nguyên tắc #4). Đổi file → `data_version` đổi → report mới có
tên khác, report cũ chỉ tái lập được nếu file cũ còn. **Giữ file cũ lại khi thay.**

**Phía DB (file → Postgres):** `ingest/versioning.py` lo, không phải đặt tay.
Chạy lại đúng lệnh ingest cũ là đủ:

```bash
python -m gpr_engine.ingest.gpr_daily --dsn "$DSN"      # --snapshot delta (mặc định)
```

- bản chạy `v1` = mới nhất (ngày mới append, giá trị revise được cập nhật);
- giá trị cũ bị ghi đè → chép sang `gpr_daily_pre_<YYYYMMDD>` trước khi đè;
- mỗi lần nạp in ra **có bao nhiêu giá trị bị revise** và ví dụ cụ thể — revise
  không chạy ngầm nữa;
- `--snapshot full` nếu muốn thêm bản sao toàn bộ dưới một nhãn riêng.

GPR **có** hiệu chỉnh hồi tố: đo 2026-08-09, 42 ngày trong 15 tháng gần nhất bị
tính lại, median |Δ| 42.9 điểm trên thang ~300. Lịch sử trước 2025-03 thì đóng
băng (0/44.007 hàng đổi).

## Còn thiếu (blocker đang mở)

| File | Chặn |
|---|---|
| `data/wui_global.csv` | battery control WUI — tải tay, thiếu thì report phải ghi rõ |
| VNINDEX daily | tier3 VN (`vn_market_series_missing`) |
| WIG / IPSA | nước pilot Phase 1b (`pilot_market_series_missing`) — không có trên FRED |
| `data/gold_events.csv` | E1c-exo → chốt ô chính. **2 người dựng tay, KHÔNG tra GPRD** |

## Citation bắt buộc khi dùng GPR

"Data downloaded from https://www.matteoiacoviello.com/gpr.htm on <ngày>"
