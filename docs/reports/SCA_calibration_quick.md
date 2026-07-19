# SCA calibration — hiệu chỉnh ℓ (block length) trên mô phỏng

> 🔬 Diagnostic (docs/12 §3.2, docs/13 §5). Hiệu chỉnh ℓ trên dữ liệu MÔ PHỎNG — hợp lệ vì không đụng dữ liệu thật. Sinh bởi `scripts/run_sca_calibration.py`.

## Metadata

- **git commit**: `d6b118d` · **generated_at**: 2026-07-19T16:09:58
- **n_trials**: 20 · **B**: 150 · quick=True

## Câu hỏi

ℓ chốt trong docs/12 (12 tháng / 60 ngày) là PHÁN ĐOÁN. Với hiệu ứng thật=0 trên chuỗi dai dẳng, tỉ lệ bác bỏ (SIZE) có ≈ 5% không? ℓ quá nhỏ phá autocorr → size phình; quá lớn → ít block. Chọn ℓ giữ size gần danh nghĩa.

## Track monthly (n=378, ρ=0.85, ℓ chốt docs/12 = 12)

| ℓ (block) | SIZE (effect=0, mong ~0.05) | POWER (effect=0.3) |
|---|---|---|
| 3 | 0.2 | 0.9 |
| 6 | 0.15 | 0.9 |
| 12 ← docs/12 **← chọn** | 0.1 | 0.8 |
| 18 | 0.15 | 0.75 |
| 24 | 0.1 | 0.65 |

- ℓ=12 (docs/12) cho size = **0.1**. ℓ giữ size gần 0.05 nhất = **12**. Khớp docs/12.

## Track daily (n=2000, ρ=0.95, ℓ chốt docs/12 = 60)

| ℓ (block) | SIZE (effect=0, mong ~0.05) | POWER (effect=0.3) |
|---|---|---|
| 20 | 0.1 | 0.8 |
| 40 **← chọn** | 0.05 | 0.2 |
| 60 ← docs/12 | 0.0 | 0.05 |
| 90 | 0.0 | 0.2 |
| 120 | 0.0 | 0.1 |

- ℓ=60 (docs/12) cho size = **0.0**. ℓ giữ size gần 0.05 nhất = **40**. ⚠️ KHÁC docs/12 (60) — cân nhắc cập nhật ℓ.

## Kết luận

- ℓ hiệu chỉnh (giữ size gần danh nghĩa): tháng **12**, ngày **40**.
- Đây là hiệu chỉnh HỢP LỆ (mô phỏng, không đụng dữ liệu thật, docs/13 §5). Nếu khác giá trị chốt docs/12 → cập nhật registry `block_length_*` + ghi lý do.
- ⚠️ Mô phỏng dùng AR(1) đơn giản; chuỗi thật có thể có đuôi/regime phức tạp hơn. Coi đây là cận dưới độ tin cậy, không phải bảo chứng tuyệt đối.
