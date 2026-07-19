# G2a — Global Macro Impact (Tầng 2 cascade) — shock: innovation

> **pipeline_note (2026-07-19):** Tính trên pipeline trước `c93a877`; HEAD hiện tại đã đổi information-time alignment, weekend aggregation, macro-day intersection và default shock. Các con số dưới đây là artifact lịch sử, không tái lập trực tiếp từ HEAD.

> 🔬 Research deliverable. Local Projection (Jordà 2005), docs/07_formulas_reference_v2.md §3. Sinh tự động bởi `scripts/run_tier2.py`.

## Metadata

- **shock_type**: `innovation` (transform: `innovation`)
- **data_version** (sha256 GPR daily): `8cc9bfb5c3b6`
- **AR order (PERSISTENT, BIC/dev-window, pre-registered)**: GPRD=5, GPRD_ACT=5, GPRD_THREAT=2 — spec khóa ở `config/hypothesis_registry.yaml`
- **git commit**: `7c925c8`
- **generated_at**: 2026-07-18T08:20:19
- **panel range**: 1990-01-03 → 2026-07-02 (9517 ngày giao dịch)
- **macro**: oil, dxy, vix, us10y | **shocks**: GPRD, GPRD_ACT, GPRD_THREAT
- **horizons**: 0..30 ngày | **macro_lags (ρ)**: 5 | HAC/Newey-West SE

## Câu hỏi

"Một cú sốc địa chính trị (GPRD) đẩy dầu / đô / risk-off toàn cầu bao nhiêu?" — deliverable độc lập, country-agnostic. Đây là **INDIRECT channel** (tầng 2) mà mọi nước dùng chung; tầng 3 (params riêng nước) ước lượng sau.

## Cổng G2a: **PENDING HUMAN REVIEW — máy đã chấm tiêu chí 1/2/3/5; người review quyết tiêu chí 4/6 rồi ghi GO/NO-GO + lý do vào report này**

Gate 6 tiêu chí (docs/09 §2.5 — ĐÃ BỎ tiêu chí 'đúng dấu literature', review 08 §4.6): (1) pipeline đúng · (2) IRF ổn định qua spec · (3) CI đầy đủ · (4) dấu/độ lớn CÓ giải thích kinh tế (người review, không ép trùng kỳ vọng) · (5) null vẫn lưu · (6) channel-specific > generic khi phù hợp. Shock chính `GPRD`:

- **Δln Oil (Brent)**: 2/31 horizon p<0.10; đỉnh |γ| tại h=29 (γ=-0.0020, p=0.025). Dấu và độ lớn CẦN GIẢI THÍCH KINH TẾ (tiêu chí 4 — người review; KHÔNG ép trùng kỳ vọng literature).
- **Δln DXY (USD broad)**: 2/31 horizon p<0.10; đỉnh |γ| tại h=16 (γ=-0.0003, p=0.005). Dấu và độ lớn CẦN GIẢI THÍCH KINH TẾ (tiêu chí 4 — người review; KHÔNG ép trùng kỳ vọng literature).
- **VIX (level)**: 13/31 horizon p<0.10; đỉnh |γ| tại h=29 (γ=-0.6044, p=0.004). Dấu và độ lớn CẦN GIẢI THÍCH KINH TẾ (tiêu chí 4 — người review; KHÔNG ép trùng kỳ vọng literature).
- **ΔUS10Y (yield %)**: 4/31 horizon p<0.10; đỉnh |γ| tại h=25 (γ=+0.0060, p=0.001). Dấu và độ lớn CẦN GIẢI THÍCH KINH TẾ (tiêu chí 4 — người review; KHÔNG ép trùng kỳ vọng literature).

### Human review (điền tay sau khi đọc kết quả)

- Tiêu chí 4 — giải thích kinh tế cho từng kênh có ý nghĩa: _chưa điền_
- Tiêu chí 6 — so channel-specific (chờ S-GPR): _chưa áp dụng_
- **Kết luận người review (GO/NO-GO + lý do + ngày + người):** _chưa điền_

## Bảng IRF (γ) — shock `GPRD`

γ = impulse response: phản ứng biến vĩ mô tại h ngày sau shock **+1 độ lệch chuẩn** GPRD (chuẩn hóa, không log1p — xem ghi chú biến đổi). **β_std** = γ/std(macro) → 'số σ macro phản ứng trên 1σ shock', so sánh được giữa các kênh (β_std≈0 cho DXY/oil là thật, không phải lỗi). **In đậm** = p<0.10.

| Macro | h | γ (beta) | β_std (σ/σ) | SE | p-value | 90% CI |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | 0 | 0.0005 | +0.019 | 0.0009 | 0.562 | [-0.0009, 0.0019] |
| Δln Oil (Brent) | 1 | -0.0007 | -0.028 | 0.0011 | 0.503 | [-0.0025, 0.0010] |
| Δln Oil (Brent) | 5 | -0.0000 | -0.001 | 0.0009 | 0.973 | [-0.0015, 0.0015] |
| Δln Oil (Brent) | 10 | 0.0003 | +0.012 | 0.0007 | 0.678 | [-0.0009, 0.0015] |
| Δln Oil (Brent) | 20 | -0.0006 | -0.024 | 0.0013 | 0.625 | [-0.0028, 0.0015] |
| Δln Oil (Brent) | 30 | **0.0014** | +0.056 | 0.0008 | 0.084 | [0.0001, 0.0028] |
| Δln DXY (USD broad) | 0 | -0.0000 | -0.011 | 0.0001 | 0.727 | [-0.0002, 0.0001] |
| Δln DXY (USD broad) | 1 | -0.0001 | -0.021 | 0.0001 | 0.527 | [-0.0003, 0.0001] |
| Δln DXY (USD broad) | 5 | -0.0000 | -0.006 | 0.0001 | 0.845 | [-0.0002, 0.0002] |
| Δln DXY (USD broad) | 10 | -0.0001 | -0.027 | 0.0001 | 0.394 | [-0.0003, 0.0001] |
| Δln DXY (USD broad) | 20 | -0.0000 | -0.005 | 0.0001 | 0.874 | [-0.0002, 0.0002] |
| Δln DXY (USD broad) | 30 | -0.0001 | -0.022 | 0.0001 | 0.502 | [-0.0003, 0.0001] |
| VIX (level) | 0 | 0.0172 | +0.002 | 0.0619 | 0.781 | [-0.0846, 0.1191] |
| VIX (level) | 1 | -0.0799 | -0.010 | 0.0868 | 0.357 | [-0.2226, 0.0629] |
| VIX (level) | 5 | -0.0851 | -0.011 | 0.1241 | 0.493 | [-0.2893, 0.1191] |
| VIX (level) | 10 | -0.1092 | -0.014 | 0.1376 | 0.427 | [-0.3355, 0.1171] |
| VIX (level) | 20 | -0.2658 | -0.034 | 0.1848 | 0.150 | [-0.5698, 0.0382] |
| VIX (level) | 30 | **-0.4871** | -0.063 | 0.2195 | 0.026 | [-0.8481, -0.1261] |
| ΔUS10Y (yield %) | 0 | **0.0034** | +0.060 | 0.0019 | 0.074 | [0.0003, 0.0066] |
| ΔUS10Y (yield %) | 1 | 0.0016 | +0.027 | 0.0019 | 0.398 | [-0.0015, 0.0046] |
| ΔUS10Y (yield %) | 5 | 0.0001 | +0.002 | 0.0018 | 0.959 | [-0.0029, 0.0030] |
| ΔUS10Y (yield %) | 10 | 0.0020 | +0.034 | 0.0019 | 0.314 | [-0.0012, 0.0052] |
| ΔUS10Y (yield %) | 20 | 0.0028 | +0.049 | 0.0018 | 0.119 | [-0.0002, 0.0058] |
| ΔUS10Y (yield %) | 30 | **0.0040** | +0.070 | 0.0019 | 0.035 | [0.0009, 0.0072] |

## Đồ thị IRF

### Δln Oil (Brent)

![IRF oil](figs/irf_oil_GPRD_innovation.png)

### Δln DXY (USD broad)

![IRF dxy](figs/irf_dxy_GPRD_innovation.png)

### VIX (level)

![IRF vix](figs/irf_vix_GPRD_innovation.png)

### ΔUS10Y (yield %)

![IRF us10y](figs/irf_us10y_GPRD_innovation.png)

## KĐ3 — Threat vs Act (β_std theo nhiều horizon)

β_std = γ/std(macro) cho GPRD_THREAT vs GPRD_ACT — act có **mạnh & trễ hơn** threat không? Câu hỏi global thuần túy. `*` = p<0.10.

| Macro | shock | h=0 | h=1 | h=5 | h=10 | h=20 |
|---|---|---|---|---|---|---|
| Δln Oil (Brent) | THREAT | -0.000 | -0.048* | -0.007 | -0.011 | +0.000 |
| Δln Oil (Brent) | ACT | +0.013 | +0.015 | -0.008 | +0.006 | -0.010 |
| Δln DXY (USD broad) | THREAT | -0.004 | -0.006 | -0.004 | -0.011 | -0.003 |
| Δln DXY (USD broad) | ACT | -0.012 | -0.025 | -0.013 | -0.027 | -0.009 |
| VIX (level) | THREAT | +0.000 | -0.007 | -0.015 | -0.022 | -0.039* |
| VIX (level) | ACT | -0.000 | -0.006 | -0.005 | -0.009 | -0.010 |
| ΔUS10Y (yield %) | THREAT | +0.035 | -0.006 | +0.006 | +0.021 | +0.039 |
| ΔUS10Y (yield %) | ACT | +0.027 | +0.025 | -0.001 | -0.010 | +0.021 |

## Robustness — γ(VIX) qua sub-sample (tiêu chí 2: ổn định qua spec)

β_std VIX theo GPRD trên các giai đoạn. Dấu/độ lớn ổn định qua sub-sample → không phải artifact của 1 giai đoạn. Diễn giải dấu là việc của người review (tiêu chí 4). `*` = p<0.10.

| Sub-sample | n | h=1 | h=5 | h=10 |
|---|---|---|---|---|
| full | 9517 | -0.010 | -0.011 | -0.014 |
| pre-2008 | 4691 | -0.001 | +0.010 | -0.018 |
| post-2008 | 4826 | -0.019 | -0.031 | -0.019 |
| post-2015 | 3000 | -0.013 | -0.023 | -0.007 |

## Ghi chú biến đổi & nhận diện (đọc kỹ)

- **Transform shock**: `innovation`. Với level: z-score giữ biên độ spike (log1p ép 370→5.9 — chỉ dành cho country-GPR nước nhỏ, docs/07v2 §0). Với innovation (G2.0): shock đã là phần residual, đọc γ là 'phản ứng / 1 đơn vị tin mới'.
- **Panel lưới business-day liên tục + complete-case một lần** (data_files.build_tier2_panel): tránh lỗi trước đây khi NaN rải rác khiến mỗi horizon chạy trên mẫu khác nhau và AR-lag nhảy qua khe NaN (gây γ VIX âm giả). Nay mọi horizon dùng cùng mẫu.
- **DXY nối dài**: DTWEXM (major, 1973→2019) nối DTWEXBGS (broad, 2006→) ở cấp return Δln (overlap 2006–2019 corr=0.926). Nhờ vậy có đủ 4 kênh macro 1990+ thay vì chỉ 2006+ (broad-only).

## Giới hạn & bước sau

- Chưa orthogonalize giữa các shock (GPRD chứa cả threat+act); transmission decomposition đầy đủ chờ tầng 3 (G2b).
- Chưa tách theo `channel` (energy/trade) — cần S-GPR (G5). Khi có, chạy lại theo channel (tiêu chí 6 của gate).
- Diễn giải kết quả (leading/coincident, cơ chế kinh tế của dấu) thuộc mục Human review phía trên — KHÔNG hard-code vào script.
