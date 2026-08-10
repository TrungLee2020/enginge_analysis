# T2-full — Bảng γ tầng 2, track THÁNG (Phase 1a)

> 🔬 Research deliverable. Local Projection lag-augmented (MO-PM 2021) + HC1 + dải sup-t (MO-PM 2019). Sinh tự động bởi `scripts/run_t2_full.py`.

**Claim tối đa: `transmission decomposition` / `predictive`. KHÔNG phải `causal`** — reduced-form LP, chưa có structural ID (claims matrix `docs/07v2` §6.4). Track tháng **chưa có holdout** (`g0` §2: rỗng theo cấu tạo) → trần claim `predictive, chưa xác nhận holdout`.

## Metadata

- **data_version**: `3e1bd83a02b8_cb1a51`
- **git commit**: `ac99a5d`
- **generated_at**: 2026-08-10T03:55:18
- **panel**: 2000-08-01 → 2026-06-01 (309 tháng, complete-case một mẫu duy nhất)
- **suy diễn**: `lag_augmented` + HC1, lags=6, dải sup-t (seed=0), CI=0.9
- **lưới**: 3 thước đo × 3 kênh × 8 outcome × 2 bản battery × h=0..24 → 5400 hàng γ
- **vintage**: real_macro=`506e9dcd8bfb` · freight=`f6cdcf8e013e` · benchmark=`7d9195a80571`
- **thời gian chạy**: 671.3 giây

## Chi phí mẫu (complete-case toàn cục)

- `--start` yêu cầu: **1990-01-01**
- mẫu thực tế: **2000-08-01**
- **mất 127 tháng** vì cột `mp_surprise_L6` (hợp lệ từ 2000-08-01)
- `battery_mode` = `level_lags`, số lag control = 6

Các cột bắt đầu muộn nhất (trước complete-case):

| Cột | Hợp lệ từ | n |
|---|---|---|
| `mp_surprise_L6` | 2000-08-01 | 311 |
| `mp_surprise_L5` | 2000-07-01 | 312 |
| `mp_surprise_L4` | 2000-06-01 | 313 |
| `mp_surprise_L3` | 2000-05-01 | 314 |
| `mp_surprise_L2` | 2000-04-01 | 315 |

> `level_lags`: control EPU vào dạng LEVEL + lag thay vì cùng thước đo với shock. Span của {LEVEL, lag} chứa trọn INNOVATION (INNOVATION là tổ hợp tuyến tính của chính LEVEL và lag của nó) nên hấp thụ không kém hơn ở hai thước đo LEVEL/INNOVATION. **Đánh đổi**: JUMP là phi tuyến, KHÔNG nằm trong span đó — ở thước đo LEVEL+JUMP, control hấp thụ ÍT HƠN chế độ `same_measure`. Đọc kết quả LEVEL+JUMP bản b với lưu ý này.

## Quyết định đã ký chi phối run này

| Quyết định | Nội dung | Hệ quả trong run |
|---|---|---|
| `DEC-2026-08-02-shock-axis` (`g0` §7.1=A) | SHOCK là **trục báo cáo**, báo cáo cả ba, không chọn | 3 bảng γ song song; `primary_cell.shock` vẫn UNRESOLVED |
| — điều kiện kèm | LEVEL/LEVEL+JUMP chỉ eligible với `lag_augmented` | run này dùng `lag_augmented` → cả ba thước đo eligible |
| `DEC-2026-08-02-holm-family` (docs/14 §6.6=B) | Họ = nhóm outcome pre-register | Holm trong họ, cỡ 4 / 3 / 1 |
| `DEC-2026-08-09-battery-control-form` | Dạng control battery = `level_lags` (LEVEL + lag), sửa cách thực hiện của docs/14 §2 1a mục 2; `same_measure` giữ làm robustness | run này dùng `level_lags`; lý do + đánh đổi ở mục *Chi phí mẫu* |
| ⚠️ **chưa ký** — bản battery c | Thêm CÚ SỐC chính sách tiền tệ (`policy_shock.py`, proxy NGÀY: Δ lãi suất 2 năm ngày công bố FOMC) làm control thứ ba | bản a/b giữ nguyên định nghĩa cũ nên vẫn so được với report trước; đây là chiều MỚI, chưa vào registry |

## Cổng eligibility (máy)

| Thước đo | Eligible | Lý do |
|---|---|---|
| LEVEL | ✅ | LEVEL + lag augmentation: lag của chính shock nằm trong ma trận thiết kế, phần dự báo được bị partial-out ngay trong hồi quy (MO-PM 2021) → hệ số đọc được là phản ứng với phần BẤT NGỜ. Điều kiện của DEC-2026-08-02-shock-axis. |
| INNOVATION | ✅ | INNOVATION đã khử phần dự báo được ở bước dựng biến (shocks.innovation, AR(p) rolling) — eligible với mọi chế độ suy diễn. |
| LEVEL+JUMP | ✅ | LEVEL_PLUS_JUMP + lag augmentation: lag của chính shock nằm trong ma trận thiết kế, phần dự báo được bị partial-out ngay trong hồi quy (MO-PM 2021) → hệ số đọc được là phản ứng với phần BẤT NGỜ. Điều kiện của DEC-2026-08-02-shock-axis. |

## Đối chiếu mức lưới (đọc TRƯỚC bảng Holm)

Toàn lưới có **648** kiểm định focal ở ngưỡng p<0.1. Kỳ vọng số bác bỏ **dưới null toàn cục**: **64.8**. Quan sát: **61** (0.94x kỳ vọng, z≳-0.50).

> DUOI ky vong null — luoi nhat quan voi KHONG co tac dong o dau ca. Khong duoc doc cac o song sot Holm nhu phat hien.

Holm trả lời *ô NÀO sống sót trong họ này*; con số trên trả lời *toàn lưới có nhiều hơn nhiễu thuần không*. Họ Holm chỉ 4/3/1 outcome nên ngưỡng nghiêm nhất là α/4 — gần như không phạt gì so với quy mô lưới. z là **cận dưới** của |z| thật (kỳ vọng cộng tính bất kể tương quan, chỉ phương sai mới phình) — đọc dấu và độ lớn xấp xỉ, không phải p-value.

| Bản battery | n | Kỳ vọng null | Quan sát | Tỉ lệ |
|---|---|---|---|---|
| a | 216 | 21.6 | 24 | 1.11x |
| b | 216 | 21.6 | 19 | 0.88x |
| c | 216 | 21.6 | 18 | 0.83x |

Chênh lệch giữa hai bản đọc được ngay ở đây: bản a bác bỏ nhiều hơn hẳn bản b ⇒ phần 'riêng của GPR' chính là thứ battery hấp thụ.

## Kết quả — số ô sống sót Holm (bản b: có battery EPU)

Một ô = một (outcome, horizon focal) tại h∈[1, 2, 6], kênh pooled+act+threat gộp lại; α=0.1. Tổng 648 kiểm định focal, 61 có p thô < 0.1, **28** sống sót Holm trong họ (bản b: 8).

**Bản b — control EPU (bất định chính sách):**

| Thước đo | Giá tài sản | Vĩ mô thực | Kênh vật lý | Tổng |
|---|---|---|---|---|
| LEVEL | 0 | 0 | 0 | 0 |
| INNOVATION | 0 | 0 | 0 | 0 |
| LEVEL+JUMP | 4 | 4 | 0 | 8 |

**Bản c — EPU + CÚ SỐC chính sách tiền tệ:** 7 ô sống sót (bản b: 8). Đây là con số đáng đọc nhất của run: tin Fed đẩy đúng những biến mà γ đo (lãi suất, DXY, VIX, dầu), nên ô nào biến mất khi thêm control này là ô vốn đang tính công của Fed cho GPR. EPU kiểm soát *bất định* chính sách, KHÔNG kiểm soát *cú sốc* chính sách.

| Thước đo | Giá tài sản | Vĩ mô thực | Kênh vật lý | Tổng |
|---|---|---|---|---|
| LEVEL | 0 | 0 | 0 | 0 |
| INNOVATION | 0 | 0 | 0 | 0 |
| LEVEL+JUMP | 3 | 4 | 0 | 7 |

**Đồng thuận qua trục SHOCK:** 0 ô (kênh, outcome, horizon) sống sót Holm ở **cả ba** thước đo. Đó là con số đáng đọc nhất của trục báo cáo: kết luận bền qua cách đo shock mạnh hơn hẳn kết luận chỉ đúng ở một thước đo.

**Ô mạnh nhất (bản b):** Kỳ vọng lạm phát (Δ) × LEVEL+JUMP × kênh act tại h=2: γ=+0.0319, p=0.0000, p_Holm=0.0000 (họ `real_macro`).

**Dải sup-t:** hằng số c ∈ [2.353, 2.862] trên 25 horizon — so với z pointwise. 19/72 ô có IRF ra khỏi dải **đồng thời** ở ít nhất một horizon. Đọc IRF bằng dải pointwise trên ngần ấy horizon là đọc sai.

## Bảng γ — LEVEL, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0020 | 0.0043 | 0.642 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0016 | 0.0041 | 0.693 | 1.000 | — |
| Giá tài sản | Δln DXY | 6 | -0.0041 | 0.0046 | 0.378 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0478 | 0.0537 | 0.373 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | -0.0066 | 0.0351 | 0.851 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0129 | 0.0353 | 0.715 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0687 | 0.0909 | 0.450 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0189 | 0.0615 | 0.758 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | +0.0060 | 0.0922 | 0.948 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -1.0973 | 1.9459 | 0.573 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -2.2133 | 1.6702 | 0.185 | 0.740 | — |
| Giá tài sản | VIX (level) | 6 | -0.3711 | 1.4934 | 0.804 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | +0.0964 | 0.0994 | 0.332 | 0.996 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.1133 | 0.0944 | 0.230 | 0.691 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0484 | 0.0705 | 0.492 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0521 | 0.1292 | 0.686 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0927 | 0.2012 | 0.645 | 0.691 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0665 | 0.0759 | 0.381 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | +0.0971 | 0.5986 | 0.871 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.5946 | 0.5819 | 0.307 | 0.691 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.2366 | 0.2569 | 0.357 | 1.000 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0092 | 0.0118 | 0.434 | 0.434 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0094 | 0.0085 | 0.270 | 0.270 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | +0.0031 | 0.0061 | 0.608 | 0.608 | — |

## Bảng γ — INNOVATION, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0016 | 0.0043 | 0.711 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0011 | 0.0041 | 0.787 | 1.000 | — |
| Giá tài sản | Δln DXY | 6 | -0.0040 | 0.0044 | 0.361 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0466 | 0.0522 | 0.373 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | -0.0046 | 0.0341 | 0.893 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0123 | 0.0351 | 0.726 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0614 | 0.0921 | 0.505 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0117 | 0.0630 | 0.853 | 1.000 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | +0.0050 | 0.0901 | 0.956 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -1.0016 | 1.8997 | 0.598 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -2.0639 | 1.6382 | 0.208 | 0.831 | — |
| Giá tài sản | VIX (level) | 6 | -0.2619 | 1.4900 | 0.860 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | +0.0992 | 0.0983 | 0.313 | 0.939 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.1072 | 0.0920 | 0.244 | 0.731 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0451 | 0.0697 | 0.517 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0448 | 0.1281 | 0.726 | 1.000 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0918 | 0.1981 | 0.643 | 0.731 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0628 | 0.0758 | 0.408 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | +0.1037 | 0.5963 | 0.862 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.5948 | 0.5628 | 0.291 | 0.731 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.2281 | 0.2550 | 0.371 | 1.000 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0090 | 0.0117 | 0.443 | 0.443 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0096 | 0.0082 | 0.245 | 0.245 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | +0.0032 | 0.0060 | 0.597 | 0.597 | — |

## Bảng γ — LEVEL+JUMP, kênh pooled, bản b (có battery)

| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |
|---|---|---|---|---|---|---|---|
| Giá tài sản | Δln DXY | 1 | +0.0002 | 0.0005 | 0.686 | 1.000 | — |
| Giá tài sản | Δln DXY | 2 | +0.0004 | 0.0004 | 0.295 | 0.589 | — |
| Giá tài sản | Δln DXY | 6 | -0.0006 | 0.0005 | 0.226 | 0.679 | — |
| Giá tài sản | Δln Oil (Brent) | 1 | -0.0028 | 0.0036 | 0.442 | 1.000 | — |
| Giá tài sản | Δln Oil (Brent) | 2 | -0.0005 | 0.0030 | 0.880 | 0.880 | — |
| Giá tài sản | Δln Oil (Brent) | 6 | +0.0066 | 0.0038 | 0.083 | 0.333 | — |
| Giá tài sản | ΔUS10Y (%) | 1 | +0.0199 | 0.0094 | 0.035 | 0.140 | — |
| Giá tài sản | ΔUS10Y (%) | 2 | +0.0099 | 0.0057 | 0.083 | 0.333 | — |
| Giá tài sản | ΔUS10Y (%) | 6 | -0.0072 | 0.0129 | 0.580 | 1.000 | — |
| Giá tài sản | VIX (level) | 1 | -0.1353 | 0.1971 | 0.493 | 1.000 | — |
| Giá tài sản | VIX (level) | 2 | -0.2353 | 0.1608 | 0.143 | 0.430 | — |
| Giá tài sản | VIX (level) | 6 | -0.0130 | 0.1645 | 0.937 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 1 | +0.0007 | 0.0109 | 0.951 | 1.000 | — |
| Vĩ mô thực | CPI (Δln) | 2 | -0.0024 | 0.0134 | 0.860 | 0.860 | — |
| Vĩ mô thực | CPI (Δln) | 6 | +0.0087 | 0.0063 | 0.168 | 0.503 | — |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 1 | -0.0258 | 0.0079 | 0.001 | 0.003 | **✓** |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 2 | +0.0520 | 0.0181 | 0.004 | 0.012 | **✓** |
| Vĩ mô thực | Kỳ vọng lạm phát (Δ) | 6 | +0.0088 | 0.0078 | 0.255 | 0.510 | — |
| Vĩ mô thực | IP (100·Δln) | 1 | -0.0043 | 0.0353 | 0.904 | 1.000 | — |
| Vĩ mô thực | IP (100·Δln) | 2 | -0.0368 | 0.0356 | 0.301 | 0.602 | — |
| Vĩ mô thực | IP (100·Δln) | 6 | +0.0098 | 0.0229 | 0.670 | 0.670 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 1 | +0.0007 | 0.0027 | 0.793 | 0.793 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 2 | +0.0005 | 0.0011 | 0.645 | 0.645 | — |
| Kênh vật lý | Cước biển (Δln PPI) | 6 | +0.0000 | 0.0007 | 0.991 | 0.991 | — |

## Hồi quy phân vị — phân phối dịch chuyển hay dày đuôi?

γ theo τ tại focal horizons, bản b, kênh pooled. `*` = p<0.1. **Không có dải sup-t** cho nhánh này (hàm ảnh hưởng của QuantReg cần ước lượng sparsity — đường đúng là bootstrap, chưa làm): đọc kèm cảnh báo bội trên 25 horizon.

`‡` = IRLS **không hội tụ** → ô để trống, không in số. 563/6000 hàng phân vị rơi vào trường hợp này: statsmodels chỉ WARN rồi trả hệ số của vòng lặp cuối, nên nếu không đếm thì số không đáng tin vẫn chạy thẳng vào bảng. Hồi quy phân vị ở τ đuôi trên mẫu 309 tháng là vùng dễ không hội tụ — đây là giới hạn của mẫu, không phải lỗi cấu hình.

### LEVEL

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.023 | -0.039 | -0.053* | ‡ | +0.005 |
| Δln Oil (Brent) | 2 | -0.010 | +0.015 | +0.001 | +0.012 | +0.054* |
| Δln Oil (Brent) | 6 | +0.003 | +0.017 | -0.016 | +0.004 | -0.032 |
| Δln DXY | 1 | -0.002 | +0.002 | +0.002 | +0.002 | +0.015* |
| Δln DXY | 2 | +0.007 | +0.006 | +0.003 | +0.001 | -0.005 |
| Δln DXY | 6 | +0.000 | -0.003 | -0.002 | -0.009* | -0.010* |
| VIX (level) | 1 | -0.515 | -0.788 | -1.717 | ‡ | +5.930* |
| VIX (level) | 2 | ‡ | ‡ | -1.743 | ‡ | -1.844 |
| VIX (level) | 6 | ‡ | ‡ | +0.346 | +2.894 | ‡ |
| ΔUS10Y (%) | 1 | -0.099 | ‡ | +0.052 | +0.078 | +0.226* |
| ΔUS10Y (%) | 2 | +0.080 | ‡ | -0.050 | ‡ | -0.030 |
| ΔUS10Y (%) | 6 | -0.100 | -0.142 | ‡ | +0.032 | +0.135* |
| IP (100·Δln) | 1 | -0.019 | +0.047 | -0.199 | -0.490* | -0.687* |
| IP (100·Δln) | 2 | +0.065 | +0.103 | +0.007 | -0.210 | -0.343* |
| IP (100·Δln) | 6 | ‡ | +0.506* | +0.336* | +0.120 | -0.033 |
| CPI (Δln) | 1 | +0.039 | -0.084 | -0.018 | +0.030 | +0.273* |
| CPI (Δln) | 2 | -0.329* | -0.058 | -0.095 | ‡ | -0.277* |
| CPI (Δln) | 6 | -0.022 | ‡ | +0.050 | ‡ | -0.073 |
| Kỳ vọng lạm phát (Δ) | 1 | +0.033 | -0.170* | -0.059 | -0.084 | -0.048 |
| Kỳ vọng lạm phát (Δ) | 2 | -0.043 | -0.105 | +0.001 | -0.028 | +0.300 |
| Kỳ vọng lạm phát (Δ) | 6 | +0.265* | +0.063 | +0.006 | -0.071 | +0.103 |
| Cước biển (Δln PPI) | 1 | -0.009 | +0.009* | +0.000 | -0.004 | +0.039* |
| Cước biển (Δln PPI) | 2 | +0.013 | +0.004 | +0.000 | +0.000 | +0.001 |
| Cước biển (Δln PPI) | 6 | ‡ | -0.001 | +0.001 | +0.001 | -0.006 |

### INNOVATION

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.009 | -0.049* | ‡ | -0.026 | +0.001 |
| Δln Oil (Brent) | 2 | +0.006 | +0.003 | -0.010 | +0.017 | +0.060* |
| Δln Oil (Brent) | 6 | -0.010 | +0.012 | ‡ | +0.004 | -0.023 |
| Δln DXY | 1 | -0.005 | ‡ | -0.001 | ‡ | +0.013* |
| Δln DXY | 2 | +0.009* | +0.003 | +0.006 | +0.004 | -0.003 |
| Δln DXY | 6 | ‡ | -0.002 | -0.001 | -0.008 | -0.012* |
| VIX (level) | 1 | -0.444 | -0.657 | ‡ | -3.068* | +4.819* |
| VIX (level) | 2 | +0.237 | -0.083 | -1.608 | -2.936* | -1.980 |
| VIX (level) | 6 | +1.300 | +0.570 | +0.706 | +5.315* | -5.336 |
| ΔUS10Y (%) | 1 | -0.139 | +0.017 | -0.001 | +0.069 | +0.187 |
| ΔUS10Y (%) | 2 | -0.009 | +0.059 | -0.057 | +0.002 | -0.039 |
| ΔUS10Y (%) | 6 | -0.072 | -0.176* | +0.094 | +0.042 | +0.091 |
| IP (100·Δln) | 1 | -0.039 | ‡ | ‡ | -0.466* | ‡ |
| IP (100·Δln) | 2 | +0.105 | +0.069 | ‡ | ‡ | -0.373* |
| IP (100·Δln) | 6 | +0.755* | +0.529* | +0.303* | ‡ | +0.002 |
| CPI (Δln) | 1 | +0.031 | -0.007 | -0.024 | +0.006 | +0.300* |
| CPI (Δln) | 2 | -0.257* | ‡ | -0.105* | -0.205* | -0.246* |
| CPI (Δln) | 6 | ‡ | -0.074 | +0.025 | -0.033 | -0.042 |
| Kỳ vọng lạm phát (Δ) | 1 | +0.197* | -0.170* | -0.069 | -0.089 | -0.020 |
| Kỳ vọng lạm phát (Δ) | 2 | -0.060 | -0.072 | -0.012 | ‡ | +0.233 |
| Kỳ vọng lạm phát (Δ) | 6 | +0.256* | +0.069 | -0.007 | -0.025 | +0.001 |
| Cước biển (Δln PPI) | 1 | -0.009 | +0.007 | +0.001 | +0.004 | +0.040* |
| Cước biển (Δln PPI) | 2 | +0.011 | +0.003 | +0.001 | -0.001 | +0.010* |
| Cước biển (Δln PPI) | 6 | +0.010 | -0.001 | +0.002 | +0.004 | ‡ |

### LEVEL+JUMP

| Outcome | h | τ=0.10 | τ=0.25 | τ=0.50 | τ=0.75 | τ=0.90 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 1 | -0.001 | -0.000 | -0.004 | +0.001 | -0.000 |
| Δln Oil (Brent) | 2 | -0.001 | -0.000 | -0.001 | +0.002 | +0.023* |
| Δln Oil (Brent) | 6 | +0.005* | +0.005 | +0.002 | +0.003 | -0.003 |
| Δln DXY | 1 | ‡ | +0.000 | +0.000 | -0.000 | +0.001 |
| Δln DXY | 2 | +0.001* | +0.001 | +0.000 | +0.000 | +0.001 |
| Δln DXY | 6 | +0.001 | ‡ | -0.001 | ‡ | -0.002* |
| VIX (level) | 1 | -0.266* | +0.131 | -0.022 | -0.421* | +1.202* |
| VIX (level) | 2 | +0.144* | +0.155 | -0.106 | -0.480* | -0.096 |
| VIX (level) | 6 | +0.269 | +0.180 | ‡ | +0.378 | -0.551 |
| ΔUS10Y (%) | 1 | -0.028* | +0.037* | +0.020* | +0.016 | +0.044* |
| ΔUS10Y (%) | 2 | +0.036* | +0.019 | +0.011 | +0.001 | +0.001 |
| ΔUS10Y (%) | 6 | -0.003 | -0.014 | -0.017 | +0.014 | +0.047* |
| IP (100·Δln) | 1 | +0.029 | +0.004 | -0.019 | -0.058 | -0.056 |
| IP (100·Δln) | 2 | ‡ | -0.008 | -0.002 | -0.048 | -0.053 |
| IP (100·Δln) | 6 | ‡ | +0.038* | +0.036 | +0.016 | -0.003 |
| CPI (Δln) | 1 | +0.010 | -0.000 | ‡ | -0.020* | -0.024 |
| CPI (Δln) | 2 | -0.040* | -0.004 | -0.009 | -0.018* | +0.077* |
| CPI (Δln) | 6 | +0.019* | ‡ | +0.011 | +0.003 | -0.003 |
| Kỳ vọng lạm phát (Δ) | 1 | +0.013 | -0.017 | -0.028* | -0.036* | -0.054 |
| Kỳ vọng lạm phát (Δ) | 2 | +0.025* | +0.006 | +0.014 | +0.061* | +0.044 |
| Kỳ vọng lạm phát (Δ) | 6 | +0.028 | +0.012 | +0.000 | +0.005 | -0.008 |
| Cước biển (Δln PPI) | 1 | -0.001 | -0.002* | -0.002* | +0.003* | ‡ |
| Cước biển (Δln PPI) | 2 | +0.001 | +0.001 | ‡ | -0.001 | -0.001 |
| Cước biển (Δln PPI) | 6 | +0.001 | +0.000 | -0.000 | +0.000 | -0.002* |

## Giới hạn — đọc trước khi trích số

- **Mẫu 309 tháng** là chi phí thật của thiết kế: LEVEL+JUMP cần 120 tháng cửa sổ (min_periods=60) cho ngưỡng phân vị, và EPU global chỉ có từ 1997. Một mẫu duy nhất cho mọi ô là điều kiện để bản a/b và ba thước đo so được với nhau (docs/14 §2 1a) — trộn mẫu thì 'hệ số yếu đi khi thêm control' có thể chỉ là đổi mẫu.
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
