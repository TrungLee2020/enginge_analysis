# E1b — Rank thước đo shock theo sức phát hiện episode

> **ERRATA / pipeline_note (2026-07-19):** Nhãn `LEVEL+JUMP` trong artifact này thực tế được code cũ tính bằng `INNOVATION+JUMP`. Ranking lịch sử vì vậy là `INNOVATION+JUMP > JUMP > INNOVATION`, không phải bằng chứng cho LEVEL. Artifact được giữ nguyên số liệu để audit; HEAD đã sửa contract, alignment, weekend aggregation và không tái lập trực tiếp các số dưới đây.

> 🔬 Research diagnostic (docs/11 §10 E1b, registry KĐ-E1b). KHÔNG chạm holdout, KHÔNG hồi quy outcome (tránh circular với lưới SCA). Sinh bởi `scripts/run_e1b_shock_ranking.py`.

## Metadata

- **data_version** (sha256 GPRD): `8cc9bfb5c3b6`
- **git commit**: `541d60f`
- **generated_at**: 2026-07-19T01:39:13
- **AR order (pre-registered)**: p=5
- **mẫu**: 1990-01-01+ | episode lớn: GPRD > phân vị 0.975 rolling(250), dedup >10d → **166** episode

## Câu hỏi

Thước đo shock nào highlight đúng các cú sốc địa chính trị lớn đã biết? Đo thuộc tính nội tại (giá trị thước đo / σ tại episode; tỉ lệ episode vượt 2σ), KHÔNG qua outcome macro.

## Bảng: mean_z@event / hit_rate (>2σ) theo sub-sample

| Thước đo | full | pre-2008 | 2008-2015 | post-2015 |
|---|---|---|---|---|
| INNOVATION | 1.80 / 32% | 1.85 / 28% | 1.86 / 36% | 1.70 / 30% |
| JUMP | 2.67 / 55% | 2.33 / 44% | 4.17 / 82% | 3.22 / 67% |
| **LEVEL+JUMP** | 2.90 / 69% | 2.67 / 54% | 3.61 / 93% | 2.96 / 78% |

## Kết luận

- **Ranking (theo full sample, hit rồi mean_z): LEVEL+JUMP > JUMP > INNOVATION.**
- Thắng: **LEVEL+JUMP** — phát hiện 69% episode lớn (mean_z=2.9), so với INNOVATION chỉ 32% và JUMP 55%.
- Ổn định ranking: winner đứng đầu ở MỌI sub-sample = **CÓ**.
- INNOVATION phát hiện kém nhất — khớp E1: AR(p) nén cú sốc khi level tăng dần trước cú nhảy (chuỗi đã 'dự báo được' phần lớn spike).

## Hệ quả — ô chính lưới SCA (docs/12 §2.2)

Trường `SHOCK` của primary_cell = **`LEVEL+JUMP`**. Cả ba mức {INNOVATION, JUMP, LEVEL+JUMP} vẫn nằm trong chiều SHOCK của lưới (báo cáo toàn bộ) — E1b chỉ định ô CHÍNH, không loại mức nào khỏi lưới.

## Hạn chế

- 'Episode lớn' định nghĩa bằng chính GPRD level → thiên vị nhẹ cho thước đo có thành phần level (LEVEL+JUMP). Đây là lý do báo cáo CẢ hit_rate của JUMP thuần: nếu JUMP thuần đã đủ cao, không cần thành phần level.
- Không phải test outcome — 'phát hiện episode' ≠ 'dự báo macro'. Việc shock nào tác động macro là của lưới SCA, không phải E1b.
