# data/

File dữ liệu tải tay. Layout hiện tại **chia hai thư mục con** (`data/AI-GPRs/` và
`data/GPR index/`) — loader tự tìm được qua `data_files.resolve_data_path()`, nên
không cần đặt phẳng ở `data/` như `DEFAULT_*` ghi. Vẫn nên giữ đúng tên file:
resolver khớp tên gần đúng thì **cảnh báo**, và raise nếu có nhiều file cùng khớp.

Kiểm kê lại bất cứ lúc nào: `python scripts/check_master_plan_claims.py`.

## `data/GPR index/` — GPR gốc (Caldara–Iacoviello)

| File | Nội dung | Phủ | Vintage (sha256[:12]) |
|---|---|---|---|
| `data_gpr_daily_recent (1).xls` | GPRD/GPRD_ACT/GPRD_THREAT daily, 15.190 hàng × 11 cột | 1985-01-01 → **2026-08-03** | `a429b2431795` |
| `data_gpr_export_202608.xls` | 44 nước monthly, 1.519 × 115 (44 `GPRC_*` recent 1985+, 44 `GPRHC_*` historical 1900+, có `GPRC_VNM`/`GPRHC_VNM`, global GPR/GPRT/GPRA/GPRH/GPRHT/GPRHA) | 1900-01 → **2026-07** | `f57e78baf651` |
| `data_gpr_export (1).xls` | ⚠️ **Bản trùng** của file trên — kiểm 2026-08-08: giống **từng ô** trên cả 112 cột số (0 ô lệch) | 1900-01 → 2026-07 | `49eaf46fb70a` |

`DEFAULT_GPR_MONTHLY` trỏ `data_gpr_export_202608.xls` (tên có vintage, không nhập
nhằng). Xóa được `data_gpr_export (1).xls` — giữ hai bản trùng chỉ làm resolver
phải đoán. Nguồn: matteoiacoviello.com/gpr_country.htm

## `data/AI-GPRs/` — AI-GPR (Iacoviello & Tong 2026)

| File | Kích thước | Nhịp | Phủ | Vintage |
|---|---|---|---|---|
| `ai_gpr_data_daily.csv` | 24.319 × 15 | daily | 1960-01-01 → 2026-07-31 | `13b8e8b48d41` |
| `ai_gpr_data_monthly.csv` | 799 × 15 | monthly | 1960-01 → 2026-07 | `92b9ba3bd38f` |
| `ai_gpr_eventtype_monthly.csv` | 799 × 10 | monthly | 1960-01 → 2026-07 | `4e6ad63e48c7` |
| `ai_gpr_country_monthly.csv` | 799 × 802 | monthly | 1960-01 → 2026-07 | `22750ad1e1bf` |
| `ai_gpr_country_eventtype_monthly.csv` | 799 × 1.602 | monthly | 1960-01 → 2026-07 | `dd4bace497a0` |
| `ai_gpr_bilateral_monthly.csv` | 799 × 1.202 | monthly | 1960-01 → 2026-07 | `e3c6185d0e40` |

⚠️ **Bốn file "Country Decompositions" (country/bilateral/eventtype) là MONTHLY** —
nguyên tắc #10 cấm forward-fill xuống daily, nên chúng chỉ vào track tháng.
Chi tiết: `docs/17_master_plan.md` §A2.

Ghim vintage bằng `data_files.ai_gpr_vintage(path)` (hash file) — trang nguồn cập
nhật định kỳ mà URL không đổi, không ghim thì report cũ mất tái lập (#7).

## Còn thiếu (blocker đang mở)

| File | Chặn |
|---|---|
| `data/wui_global.csv` | battery control WUI — tải tay, thiếu thì report phải ghi rõ |
| VNINDEX daily | tier3 VN (`vn_market_series_missing`) |
| WIG / IPSA | nước pilot Phase 1b (`pilot_market_series_missing`) — không có trên FRED |
| `data/gold_events.csv` | E1c-exo → chốt ô chính. **2 người dựng tay, KHÔNG tra GPRD** |

## Citation bắt buộc khi dùng GPR

"Data downloaded from https://www.matteoiacoviello.com/gpr.htm on <ngày>"
