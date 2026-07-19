# E1c — Rank thước đo shock bằng AUC (sự kiện ngoại sinh)

> 🔬 Research diagnostic (docs/13 §2, registry KĐ-E1c). THAY E1b: sửa lỗi episode nội sinh (§1.1) + ngưỡng 2σ không so được (§1.2). AUC bất biến biến đổi đơn điệu. KHÔNG chạm holdout, KHÔNG hồi quy outcome. Sinh bởi `scripts/run_e1c_shock_detection.py`.

## Metadata

- **data_version**: `8cc9bfb5c3b6` · **git**: `adc2ac4` · **generated_at**: 2026-07-19T14:33:39
- **AR order (pre-registered)**: p=5 · **B bootstrap**: 2000 · seed=42
- **sự kiện endo** (GPRD>q97.5, đối chứng): 166 · **exo (gold set)**: 0

> 🛑 **CHƯA CÓ `data/gold_events.csv`** — chỉ chạy được bản ENDO (đối chứng). Bản EXO (bản DÙNG để chốt ô chính) chặn bởi gold set: cần 2 người dựng tay, KHÔNG tra GPRD (docs/13 §2.2, cổng G-Gold). primary_cell.shock KHÔNG được chốt từ bản endo.

## Kết quả

### AUC — ENDO (GPRD>q97.5 — ĐỐI CHỨNG, không dùng chốt)

| Thước đo | full | pre-2008 | 2008-2015 | post-2015 | CI 95% (full) |
|---|---|---|---|---|---|
| LEVEL+JUMP | 0.774 | 0.769 | 0.812 | 0.758 | [0.74, 0.805] |
| LEVEL | 0.74 | 0.721 | 0.805 | 0.735 | [0.694, 0.783] |
| JUMP | 0.719 | 0.719 | 0.74 | 0.702 | [0.7, 0.737] |
| INNOVATION | 0.712 | 0.71 | 0.72 | 0.705 | [0.694, 0.729] |

## Phép thử tự bác bỏ (docs/13 §2.5)

- endo rank (đối chứng): **LEVEL+JUMP > LEVEL > JUMP > INNOVATION**.
- CHƯA chạy được bản exo → chưa kết luận. Dựng gold set trước.

## Ghi chú AUC vs hit-rate E1b

AUC bất biến biến đổi đơn điệu nên chấm INNOVATION công bằng hơn hit-rate 2σ của E1b (E1b méo vì JUMP zero-inflated, LEVEL skew — docs/13 §1.2). So AUC endo với hit-rate E1b để thấy mức độ méo của E1b.

## Hệ quả ô chính SCA-01

Chỉ chốt `primary_cell.shock` từ bản EXO khi: một thước đo thắng rõ, ổn định qua sub-sample, CI không chồng lấn (docs/13 §3). Nếu không → SHOCK MỞ (§3.1): báo cáo cả 4 mức, Holm trên 4×H.
