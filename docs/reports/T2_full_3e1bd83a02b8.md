# T2-full — Bảng γ tầng 2, track THÁNG (Phase 1a)

> 🔬 Research deliverable. Local Projection lag-augmented (MO-PM 2021) + HC1 + dải sup-t (MO-PM 2019). Sinh tự động bởi `scripts/run_t2_full.py`.

**Claim tối đa: `transmission decomposition` / `predictive`. KHÔNG phải `causal`** — reduced-form LP, chưa có structural ID (claims matrix `docs/07v2` §6.4). Track tháng **chưa có holdout** (`g0` §2: rỗng theo cấu tạo) → trần claim `predictive, chưa xác nhận holdout`.

## Metadata

- **data_version**: `3e1bd83a02b8`
- **git commit**: `ac99a5d`
- **generated_at**: 2026-08-09T04:32:50
- **panel**: 2000-02-01 → 2026-06-01 (315 tháng, complete-case một mẫu duy nhất)
- **suy diễn**: `lag_augmented` + HC1, lags=6, dải sup-t (seed=0), CI=0.9
- **lưới**: 3 thước đo × 3 kênh × 8 outcome × 2 bản battery × h=0..24 → 3600 hàng γ
- **vintage**: real_macro=`506e9dcd8bfb` · freight=`f6cdcf8e013e` · benchmark=`7d9195a80571`
- **thời gian chạy**: 535.4 giây

## Chi phí mẫu (complete-case toàn cục)

- `--start` yêu cầu: **1990-01-01**
- mẫu thực tế: **2000-02-01**
- **mất 121 tháng** vì cột `GPR_THREAT_LEVEL_PLUS_JUMP` (hợp lệ từ 2000-02-01)
- `battery_mode` = `level_lags`, số lag control = 6

Các cột bắt đầu muộn nhất (trước complete-case):

| Cột | Hợp lệ từ | n |
|---|---|---|
| `GPR_THREAT_LEVEL_PLUS_JUMP` | 2000-02-01 | 317 |
| `GPR_ACT_LEVEL_PLUS_JUMP` | 2000-02-01 | 317 |
| `GPR_LEVEL_PLUS_JUMP` | 2000-02-01 | 317 |
| `epu_global_LEVEL_L6` | 1997-08-01 | 347 |
| `epu_global_LEVEL_L5` | 1997-07-01 | 348 |

> `level_lags`: control EPU vào dạng LEVEL + lag thay vì cùng thước đo với shock. Span của {LEVEL, lag} chứa trọn INNOVATION (INNOVATION là tổ hợp tuyến tính của chính LEVEL và lag của nó) nên hấp thụ không kém hơn ở hai thước đo LEVEL/INNOVATION. **Đánh đổi**: JUMP là phi tuyến, KHÔNG nằm trong span đó — ở thước đo LEVEL+JUMP, control hấp thụ ÍT HƠN chế độ `same_measure`. Đọc kết quả LEVEL+JUMP bản b với lưu ý này.

## Quyết định đã ký chi phối run này

| Quyết định | Nội dung | Hệ quả trong run |
|---|---|---|
| `DEC-2026-08-02-shock-axis` (`g0` §7.1=A) | SHOCK là **trục báo cáo**, báo cáo cả ba, không chọn | 3 bảng γ song song; `primary_cell.shock` vẫn UNRESOLVED |
| — điều kiện kèm | LEVEL/LEVEL+JUMP chỉ eligible với `lag_augmented` | run này dùng `lag_augmented` → cả ba thước đo eligible |
| `DEC-2026-08-02-holm-family` (docs/14 §6.6=B) | Họ = nhóm outcome pre-register | Holm trong họ, cỡ 4 / 3 / 1 |
| `DEC-2026-08-09-battery-control-form` | Dạng control battery = `level_lags` (LEVEL + lag), sửa cách thực hiện của docs/14 §2 1a mục 2; `same_measure` giữ làm robustness | run này dùng `level_lags`; lý do + đánh đổi ở mục *Chi phí mẫu* |

## Cổng eligibility (máy)

| Thước đo | Eligible | Lý do |
|---|---|---|
| LEVEL | ✅ | LEVEL + lag augmentation: lag của chính shock nằm trong ma trận thiết kế, phần dự báo được bị partial-out ngay trong hồi quy (MO-PM 2021) → hệ số đọc được là phản ứng với phần BẤT NGỜ. Điều kiện của DEC-2026-08-02-shock-axis. |
| INNOVATION | ✅ | INNOVATION đã khử phần dự báo được ở bước dựng biến (shocks.innovation, AR(p) rolling) — eligible với mọi chế độ suy diễn. |
| LEVEL+JUMP | ✅ | LEVEL_PLUS_JUMP + lag augmentation: lag của chính shock nằm trong ma trận thiết kế, phần dự báo được bị partial-out ngay trong hồi quy (MO-PM 2021) → hệ số đọc được là phản ứng với phần BẤT NGỜ. Điều kiện của DEC-2026-08-02-shock-axis. |

## Đối chiếu mức lưới (đọc TRƯỚC bảng Holm)

Toàn lưới có **432** kiểm định focal ở ngưỡng p<0.1. Kỳ vọng số bác bỏ **dưới null toàn cục**: **43.2**. Quan sát: **51** (1.18x kỳ vọng, z≳+1.25).

> TREN ky vong null nhung trong khoang nhieu — chua tach duoc khoi null toan cuc.

Holm trả lời *ô NÀO sống sót trong họ này*; con số trên trả lời *toàn lưới có nhiều hơn nhiễu thuần không*. Họ Holm chỉ 4/3/1 outcome nên ngưỡng nghiêm nhất là α/4 — gần như không phạt gì so với quy mô lưới. z là **cận dưới** của |z| thật (kỳ vọng cộng tính bất kể tương quan, chỉ phương sai mới phình) — đọc dấu và độ lớn xấp xỉ, không phải p-value.

| Bản battery | n | Kỳ vọng null | Quan sát | Tỉ lệ |
|---|---|---|---|---|
| a | 216 | 21.6 | 31 | 1.44x |
| b | 216 | 21.6 | 20 | 0.93x |

Chênh lệch giữa hai bản đọc được ngay ở đây: bản a bác bỏ nhiều hơn hẳn bản b ⇒ phần 'riêng của GPR' chính là thứ battery hấp thụ.

## Kết quả — số ô sống sót Holm (bản b: có battery EPU)

Một ô = một (outcome, horizon focal) tại h∈[1, 2, 6], kênh pooled+act+threat gộp lại; α=0.1. Tổng 432 kiểm định focal, 51 có p thô < 0.1, **22** sống sót Holm trong họ (bản b: 9).

| Thước đo | Giá tài sản | Vĩ mô thực | Kênh vật lý | Tổng |
|---|---|---|---|---|
| LEVEL | 0 | 0 | 0 | 0 |
| INNOVATION | 0 | 0 | 0 | 0 |
| LEVEL+JUMP | 5 | 4 | 0 | 9 |

**Đồng thuận qua trục SHOCK:** 0 ô (kênh, outcome, horizon) sống sót Holm ở **cả ba** thước đo. Đó là con số đáng đọc nhất của trục báo cáo: kết luận bền qua cách đo shock mạnh hơn hẳn kết luận chỉ đúng ở một thước đo.

**Ô mạnh nhất (bản b):** Kỳ vọng lạm phát (Δ) × LEVEL+JUMP × kênh act tại h=2: γ=+0.0318, p=0.0000, p_Holm=0.0000 (họ `real_macro`).

**Dải sup-t:** hằng số c ∈ [2.33, 2.861] trên 25 horizon — so với z pointwise. 18/72 ô có IRF ra khỏi dải **đồng thời** ở ít nhất một horizon. Đọc IRF bằng dải pointwise trên ngần ấy horizon là đọc sai.

## Bảng γ — LEVEL, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0008 | 0.0041 | 0.850 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0007 | 0.0040 | 0.862 | 1.000 | — |
| Giá tài sản | Δln DXY | 6 | -0.0048 | 0.0044 | 0.276 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0520 | 0.0515 | 0.313 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | -0.0018 | 0.0345 | 0.959 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0181 | 0.0332 | 0.586 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0480 | 0.0931 | 0.606 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0341 | 0.0588 | 0.562 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | +0.0174 | 0.0910 | 0.848 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -0.8816 | 1.8681 | 0.637 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -2.3803 | 1.5949 | 0.136 | 0.542 | — |
| Giá tài sản | VIX (level) | 6 | -0.3746 | 1.4219 | 0.792 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | +0.0677 | 0.0971 | 0.485 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.1055 | 0.0899 | 0.241 | 0.722 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0423 | 0.0672 | 0.529 | 0.824 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0687 | 0.1230 | 0.577 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0957 | 0.1941 | 0.622 | 0.722 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0784 | 0.0718 | 0.275 | 0.824 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | +0.1021 | 0.5654 | 0.857 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.5494 | 0.5566 | 0.324 | 0.722 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.2630 | 0.2473 | 0.288 | 0.824 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0075 | 0.0112 | 0.505 | 0.505 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0094 | 0.0082 | 0.254 | 0.254 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | +0.0031 | 0.0059 | 0.592 | 0.592 | — |

## Bảng γ — INNOVATION, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0002 | 0.0042 | 0.960 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0000 | 0.0040 | 0.999 | 1.000 | — |
| Giá tài sản | Δln DXY | 6 | -0.0047 | 0.0042 | 0.257 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0497 | 0.0498 | 0.319 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | +0.0009 | 0.0337 | 0.979 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0176 | 0.0333 | 0.596 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0424 | 0.0931 | 0.649 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0259 | 0.0599 | 0.666 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | +0.0159 | 0.0889 | 0.858 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -0.8435 | 1.8125 | 0.642 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -2.2667 | 1.5629 | 0.147 | 0.588 | — |
| Giá tài sản | VIX (level) | 6 | -0.3583 | 1.4310 | 0.802 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | +0.0715 | 0.0960 | 0.456 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.0992 | 0.0877 | 0.258 | 0.773 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0397 | 0.0666 | 0.551 | 0.889 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0610 | 0.1222 | 0.618 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0942 | 0.1911 | 0.622 | 0.773 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0745 | 0.0720 | 0.300 | 0.889 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | +0.1167 | 0.5657 | 0.837 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.5464 | 0.5367 | 0.309 | 0.773 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.2600 | 0.2490 | 0.296 | 0.889 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0074 | 0.0111 | 0.502 | 0.502 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0096 | 0.0079 | 0.226 | 0.226 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | +0.0031 | 0.0058 | 0.589 | 0.589 | — |

## Bảng γ — LEVEL+JUMP, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0002 | 0.0005 | 0.741 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0003 | 0.0004 | 0.372 | 0.744 | — |
| Giá tài sản | Δln DXY | 6 | -0.0006 | 0.0005 | 0.171 | 0.514 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0026 | 0.0035 | 0.454 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | +0.0000 | 0.0031 | 0.999 | 0.999 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0067 | 0.0038 | 0.078 | 0.310 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0192 | 0.0095 | 0.044 | 0.175 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0107 | 0.0055 | 0.051 | 0.202 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | -0.0069 | 0.0127 | 0.587 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -0.1291 | 0.1905 | 0.498 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -0.2504 | 0.1538 | 0.103 | 0.310 | — |
| Giá tài sản | VIX (level) | 6 | -0.0169 | 0.1593 | 0.916 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | -0.0011 | 0.0108 | 0.920 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.0030 | 0.0133 | 0.824 | 0.824 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0081 | 0.0062 | 0.190 | 0.570 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0266 | 0.0077 | 0.001 | 0.002 | **✓** |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0519 | 0.0177 | 0.003 | 0.010 | **✓** |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0093 | 0.0075 | 0.214 | 0.570 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | -0.0024 | 0.0345 | 0.945 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.0337 | 0.0349 | 0.334 | 0.669 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.0126 | 0.0223 | 0.573 | 0.573 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0006 | 0.0027 | 0.812 | 0.812 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0005 | 0.0012 | 0.666 | 0.666 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | -0.0000 | 0.0006 | 0.985 | 0.985 | — |

## Hồi quy phân vị — phân phối dịch chuyển hay dày đuôi?

γ theo τ tại focal horizons, bản b, kênh pooled. `*` = p<0.1. **Không có dải sup-t** cho nhánh này (hàm ảnh hưởng của QuantReg cần ước lượng sparsity — đường đúng là bootstrap, chưa làm): đọc kèm cảnh báo bội trên 25 horizon.

`‡` = IRLS **không hội tụ** → ô để trống, không in số. 502/6000 hàng phân vị rơi vào trường hợp này: statsmodels chỉ WARN rồi trả hệ số của vòng lặp cuối, nên nếu không đếm thì số không đáng tin vẫn chạy thẳng vào bảng. Hồi quy phân vị ở τ đuôi trên mẫu 315 tháng là vùng dễ không hội tụ — đây là giới hạn của mẫu, không phải lỗi cấu hình.

### LEVEL

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.021 | -0.023 | -0.051* | -0.045* | -0.001 |
| Δln Oil (Brent) | 2 | +0.001 | +0.024 | +0.006 | +0.012 | +0.067* |
| Δln Oil (Brent) | 6 | -0.015 | +0.010 | -0.001 | +0.007 | -0.046 |
| Δln DXY | 1 | -0.004 | -0.004 | +0.000 | +0.002 | +0.016* |
| Δln DXY | 2 | +0.010* | +0.006 | +0.003 | +0.001 | ‡ |
| Δln DXY | 6 | -0.002 | -0.003 | -0.002 | ‡ | -0.009 |
| VIX (level) | 1 | ‡ | -1.576* | ‡ | ‡ | +6.329* |
| VIX (level) | 2 | +0.146 | -0.868 | -1.799 | ‡ | ‡ |
| VIX (level) | 6 | +1.324 | +1.579 | +0.539 | ‡ | -1.331 |
| ΔUS10Y (%) | 1 | -0.111 | ‡ | -0.008 | +0.068 | +0.096 |
| ΔUS10Y (%) | 2 | +0.115 | ‡ | -0.044 | +0.015 | +0.011 |
| ΔUS10Y (%) | 6 | -0.134 | -0.091 | ‡ | +0.058 | +0.183* |
| IP (100·Δln) | 1 | -0.102 | +0.009 | -0.182 | -0.480* | -0.680* |
| IP (100·Δln) | 2 | +0.104 | -0.048 | +0.029 | +0.002 | -0.339* |
| IP (100·Δln) | 6 | +0.787* | +0.492* | +0.347* | +0.100 | -0.019 |
| CPI (Δln) | 1 | +0.034 | -0.039 | -0.029 | -0.079 | +0.251* |
| CPI (Δln) | 2 | -0.335* | -0.092 | -0.096 | -0.235* | -0.286* |
| CPI (Δln) | 6 | -0.062 | -0.072 | +0.046 | -0.034 | -0.082 |
| Kỳ vọng lạm phát (Δ) | 1 | ‡ | -0.179* | -0.091 | -0.063 | +0.012 |
| Kỳ vọng lạm phát (Δ) | 2 | -0.123 | -0.073 | +0.012 | ‡ | +0.263 |
| Kỳ vọng lạm phát (Δ) | 6 | +0.248* | +0.057 | ‡ | -0.054 | +0.031 |
| Cước biển (Δln PPI) | 1 | -0.009 | +0.006 | +0.002 | -0.007 | +0.015* |
| Cước biển (Δln PPI) | 2 | +0.012 | +0.002 | +0.002 | -0.003 | -0.006 |
| Cước biển (Δln PPI) | 6 | +0.007 | +0.001 | +0.001 | +0.004 | -0.007 |

### INNOVATION

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.003 | -0.018 | -0.051* | -0.054* | -0.010 |
| Δln Oil (Brent) | 2 | -0.007 | +0.008 | +0.004 | ‡ | +0.074* |
| Δln Oil (Brent) | 6 | -0.025 | +0.003 | -0.003 | ‡ | -0.024 |
| Δln DXY | 1 | -0.005 | -0.003 | -0.001 | +0.002 | +0.011* |
| Δln DXY | 2 | +0.008 | -0.000 | +0.006 | +0.003 | ‡ |
| Δln DXY | 6 | -0.004 | -0.002 | ‡ | -0.012* | -0.009 |
| VIX (level) | 1 | -0.452 | -1.474* | -1.388 | -2.493* | +4.504* |
| VIX (level) | 2 | +0.227 | -0.434 | -1.725 | -2.354 | -1.788 |
| VIX (level) | 6 | +1.256 | +0.219 | +0.723 | ‡ | -4.871 |
| ΔUS10Y (%) | 1 | -0.135 | -0.124 | -0.018 | +0.083 | ‡ |
| ΔUS10Y (%) | 2 | +0.068 | +0.058 | -0.044 | +0.006 | +0.010 |
| ΔUS10Y (%) | 6 | -0.139 | -0.111 | +0.115 | +0.073 | +0.140* |
| IP (100·Δln) | 1 | -0.110 | +0.022 | -0.173 | -0.430* | -0.663* |
| IP (100·Δln) | 2 | +0.089 | -0.041 | ‡ | -0.041 | ‡ |
| IP (100·Δln) | 6 | +0.762* | +0.465* | +0.323* | +0.116 | +0.025 |
| CPI (Δln) | 1 | +0.035 | -0.025 | -0.028 | -0.105 | +0.249* |
| CPI (Δln) | 2 | -0.260* | ‡ | ‡ | -0.198* | -0.232* |
| CPI (Δln) | 6 | ‡ | -0.062 | +0.023 | -0.027 | -0.045 |
| Kỳ vọng lạm phát (Δ) | 1 | +0.173* | -0.184* | -0.111 | -0.074 | -0.036 |
| Kỳ vọng lạm phát (Δ) | 2 | -0.084 | -0.060 | +0.016 | +0.078 | +0.238 |
| Kỳ vọng lạm phát (Δ) | 6 | +0.192* | +0.077 | +0.006 | -0.037 | ‡ |
| Cước biển (Δln PPI) | 1 | ‡ | +0.007 | +0.001 | -0.001 | +0.033* |
| Cước biển (Δln PPI) | 2 | ‡ | +0.001 | +0.001 | -0.003 | +0.014* |
| Cước biển (Δln PPI) | 6 | +0.008 | +0.001 | +0.002 | +0.002 | -0.006 |

### LEVEL+JUMP

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.001 | -0.000 | -0.003 | -0.005 | -0.004 |
| Δln Oil (Brent) | 2 | -0.005 | +0.001 | -0.001 | +0.004 | +0.021* |
| Δln Oil (Brent) | 6 | +0.006 | +0.005* | ‡ | +0.002 | -0.002 |
| Δln DXY | 1 | +0.001 | +0.000 | +0.000 | -0.000 | +0.000 |
| Δln DXY | 2 | +0.001* | +0.001 | +0.000 | +0.000 | +0.000 |
| Δln DXY | 6 | +0.001 | ‡ | -0.001 | -0.001* | -0.002* |
| VIX (level) | 1 | -0.263* | +0.118 | -0.032 | -0.387* | +0.761* |
| VIX (level) | 2 | +0.132* | +0.136 | -0.127 | -0.480* | -0.368 |
| VIX (level) | 6 | +0.258 | +0.178 | +0.114 | +0.195 | -0.489 |
| ΔUS10Y (%) | 1 | -0.033* | +0.041* | +0.020* | +0.015 | ‡ |
| ΔUS10Y (%) | 2 | +0.037* | +0.017 | +0.011 | -0.000 | +0.001 |
| ΔUS10Y (%) | 6 | ‡ | -0.013 | -0.016 | +0.012 | +0.031* |
| IP (100·Δln) | 1 | +0.028 | +0.005 | -0.018 | -0.058 | -0.056 |
| IP (100·Δln) | 2 | ‡ | -0.013 | +0.005 | -0.043 | -0.053 |
| IP (100·Δln) | 6 | +0.042 | +0.049* | +0.037 | +0.015 | -0.002 |
| CPI (Δln) | 1 | +0.007 | +0.000 | -0.008 | -0.022* | -0.023 |
| CPI (Δln) | 2 | -0.037* | -0.004 | -0.009 | -0.019* | +0.079* |
| CPI (Δln) | 6 | +0.022* | +0.016* | +0.011 | -0.001 | -0.002 |
| Kỳ vọng lạm phát (Δ) | 1 | +0.009 | -0.019 | ‡ | -0.037* | -0.053 |
| Kỳ vọng lạm phát (Δ) | 2 | +0.037* | +0.008 | +0.031* | +0.061* | ‡ |
| Kỳ vọng lạm phát (Δ) | 6 | +0.029 | +0.012 | +0.002 | -0.003 | -0.003 |
| Cước biển (Δln PPI) | 1 | -0.001 | -0.002* | -0.002* | +0.001* | +0.015* |
| Cước biển (Δln PPI) | 2 | +0.001 | +0.000 | -0.000 | -0.001 | -0.002* |
| Cước biển (Δln PPI) | 6 | +0.001 | +0.000 | -0.000 | +0.000 | -0.001 |

## Giới hạn — đọc trước khi trích số

- **Mẫu 315 tháng** là chi phí thật của thiết kế: LEVEL+JUMP cần 120 tháng cửa sổ (min_periods=60) cho ngưỡng phân vị, và EPU global chỉ có từ 1997. Một mẫu duy nhất cho mọi ô là điều kiện để bản a/b và ba thước đo so được với nhau (docs/14 §2 1a) — trộn mẫu thì 'hệ số yếu đi khi thêm control' có thể chỉ là đổi mẫu.
- **WUI KHÔNG có trong battery**: publish theo quý, join vào grid tháng sẽ xóa 2/3 panel trong im lặng, forward-fill thì vi phạm #10. `data/wui_global.csv` chưa tồn tại. Battery ở đây = EPU US + EPU Global, **thiếu WUI** — ghi ra chứ không lặng lẽ bỏ (docs/14 §2 1a #3).
- **Freight là PPI khảo sát dính** → đo truyền dẫn chi phí, KHÔNG đo tắc nghẽn Hormuz/Malacca. Đừng đọc hệ số freight như thước đo điểm nghẽn.
- **IP/CPI revise hồi tố**: bản FRED là vintage mới nhất, không phải point-in-time. Backtest thật phải qua ALFRED vintage.
- **Phân vị chỉ chạy kênh pooled** (5 mức τ): lưới đầy đủ 3 kênh × 5 τ không thêm thông tin cho câu hỏi Phase 1a mà nhân 3 lần chi phí. Phạm vi ghi ra, không âm thầm thu hẹp.
- **Holm chỉ áp tại focal horizons đã pre-register**, không quét 25 horizon: chiều horizon đã do dải sup-t xử lý (docs/14 §1.3); phạt lại là mất hết power.
- Holm **conservative** khi outcome tương quan mạnh — oil/dxy/vix/us10y chắc chắn có. Đánh đổi đã biết khi ký §6.6, không đổi sang thủ tục lỏng hơn sau khi thấy p-value.

## Human review (điền tay sau khi đọc)

- Dấu & độ lớn có giải thích kinh tế cho từng ô sống sót: _chưa điền_
- Ba thước đo có kể cùng một câu chuyện không: _chưa điền_
- **Kết luận (GO/NO-GO + lý do + ngày + người):** _chưa điền_
