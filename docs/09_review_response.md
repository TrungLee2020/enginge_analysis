# 09 — PHẢN HỒI REVIEW & KẾ HOẠCH TIẾP THU

**Phiên bản:** 1.0 — 07/2026
**Phản hồi cho:** `08_review_and_recommendations.md`
**Nguyên tắc phản hồi:** tách rõ (A) lỗi phải sửa để KHÔNG SAI — làm ngay trước G2; (B) nâng cấp để đạt chuẩn PUBLISH — làm ở track research song song, không chặn sản phẩm. Đánh giá tổng thể: review chất lượng cao, phần lớn tiếp thu. Vài điểm hạ ưu tiên có ghi lý do.

---

## 1. PHÂN LOẠI TOÀN BỘ ĐIỂM REVIEW

Ký hiệu: 🔴 bắt buộc sửa trước G2 · 🟡 tiếp thu, ưu tiên trung bình · 🟢 track research/publish, không chặn sản phẩm · ⚪ phản biện/điều chỉnh mức độ

| # | Điểm review | Phán quyết | Hành động |
|---|---|---|---|
| 4.1 | Dynamic mediation phải là convolution, không nhân cùng horizon | 🔴 | Sửa công thức §5 (file 07) → tích chập |
| 4.2 | Tách global-direct vs domestic-direct (3 hệ số β/θ/λ) | 🔴 | Sửa phương trình tầng 3 |
| 4.3 | Macro mediator nội sinh → cần structural ID cho claim nhân quả | 🟢 | Tách 2 mode; reduced-form cho sản phẩm, structural là G2.5 optional |
| 4.4 | GPR level ≠ shock; cần innovation/persistent/surprise, đưa lên G2 | 🔴 | Thêm decomposition vào G2.0, sửa mọi shock term |
| 4.5 | Variance decomposition sai (bỏ covariance) → Shapley/FEVD | 🔴 | Thay công thức §5.3 |
| 4.6 | Gate G2a confirmation bias ("đúng dấu literature") | 🔴 | Viết lại tiêu chí gate |
| 4.7 | Tần suất trộn; không forward-fill monthly→daily; tách 3 pipeline | 🔴 | Ràng buộc: daily VN backtest KHÔNG dùng GPRC_VNM monthly |
| 4.8 | Backtest leakage; cần final holdout + Deflated Sharpe/SPA | 🔴 | Final holdout 2026-H1 khóa; thêm test |
| 4.9 | LLM validation cần gold set, không chỉ correlation | 🟡 | Mở rộng V1 metrics khi tới G5 |
| 4.10 | Severity tách khỏi threat/act | 🟡 | Thêm trường severity (optional V1) |
| 4.11 | Denominator/coverage; balanced source index + quality flag | 🟡 | Bảng `index_quality` + cờ coverage (chủ yếu cho V-phase corpus VN) |
| 4.12 | Dedup theo event cluster; tách Attention vs Event Risk | 🟡 | Event clustering ở chân C (G6) |
| 4.13 | S-GPR selection bias, official silence là thông tin | 🟡 | Giữ sum/mean/max + silence flag (G5) |
| 4.14 | Actor weighting endogeneity → "predictive weight" | 🟡 | Đổi tên + list control (đã một phần lường trước) |
| 4.15 | GDELT cần daily cho warning, không chỉ monthly | 🟡 | 2 bảng daily+monthly (G6) |
| 4.16 | LLM historical reconstruction rủi ro cao | 🟢→hạ cấp | Chỉ exploratory appendix, ra khỏi main model |
| G0 | Research governance trước ingest | 🔴 | Thêm bước G0 |
| available_at | Thêm vào schema | 🔴 | Sửa schema ext_series |
| claims matrix | Chỉ claim đúng mức nhận dạng | 🔴 | Thêm ma trận, rẻ và quan trọng |

---

## 2. TÁM ĐIỂM BẮT BUỘC (🔴) — CHI TIẾT TIẾP THU

### 2.1 [4.4] Innovation thay Level — ĐIỂM QUAN TRỌNG NHẤT
**Vấn đề:** $\ln(1+\text{GPR})$ là mức, gộp tin mới + tin lặp + phần đã dự báo + regime. Hệ số của nó không phải "tác động của shock".
**Sửa:** tại G2.0 xây song song 6 biến, mọi hồi quy "shock" dùng innovation/surprise, KHÔNG dùng level:
```
GPR_LEVEL       = ln(1+GPR)
GPR_PERSISTENT  = E_{t-1}[LEVEL]           (AR/EWMA dự báo 1 bước)
GPR_INNOVATION  = LEVEL - PERSISTENT       ← shock chính cho LP
GPR_JUMP        = max(0, z_t - q95)
GPT_INNOVATION  = tách riêng threats
GPA_SURPRISE    = GPA - E[GPA | GPT,S-GPR,Ladder]   (đã có ở §2 file 07)
```
Ảnh hưởng: mọi công thức tầng 2/3 đổi `shock_j` từ level → innovation.

### 2.2 [4.1] Dynamic convolution
**Sai (v1):** $\text{Indirect}(h)=\sum_M \theta_{M,h}\gamma_{M,j,h}$ (nhân cùng $h$).
**Đúng:** tích chập theo thời gian —
$$\text{Indirect}_{j\to c}(h)=\sum_M\sum_{s=0}^{h}\gamma_{M,j}(s)\,\theta^c_M(h-s)$$
Diễn giải: shock đẩy mediator ở bước $s$, mediator đánh thị trường ở bước $h-s$. Đây là chuỗi động thực, không phải tích điểm.

### 2.3 [4.2] Ba hệ số direct/indirect/domestic
Phương trình tầng 3 tách rõ:
- $\beta^c_{j,h}$: **global-direct** — global shock đánh thẳng tâm lý NĐT nước $c$, KHÔNG qua macro.
- $\theta^c_{M,h}$: **indirect** — qua kênh macro (Oil/DXY/VIX/US10Y).
- $\lambda^c_h$: **domestic-direct** — rủi ro riêng nước $c$ ($\text{GPR}^{c,\perp}$).
(Chi tiết công thức: §5 file 07 đã sửa.)

### 2.4 [4.5] Shapley/FEVD thay variance-share ngây thơ
**Bỏ:** $\text{Share}_M=\theta_M^2\text{Var}(M)/\text{Var}(r)$ (bỏ covariance, tổng có thể >100%).
**Dùng:** reduced-form → Shapley/LMG decomposition của $R^2$; structural → FEVD/generalized FEVD; serving hàng ngày → **historical contribution** ("VN-Index giảm hôm nay: VIX x%, DXY y%, Oil z%, VN-specific k%, unexplained ...").

### 2.5 [4.6] Gate G2a không confirmation-bias
**Bỏ tiêu chí "γ đúng dấu literature".** Lý do: trade war có thể làm dầu GIẢM (cầu yếu), khác supply shock làm dầu tăng — ép một dấu là sai. Gate mới:
1. Dữ liệu/pipeline đúng (available_at, no forward-fill).
2. IRF ổn định qua các specification hợp lý.
3. CI báo đầy đủ.
4. Dấu & độ lớn CÓ giải thích kinh tế (không bắt buộc trùng kỳ vọng).
5. Kết quả null/âm vẫn lưu.
6. Channel-specific shock giải thích tốt hơn generic khi phù hợp.

### 2.6 [4.7] Ràng buộc tần suất — HỆ QUẢ LỚN
- Tách 3 pipeline: **daily financial** / **monthly macro** / **event-intraday**.
- **KHÔNG forward-fill** GPRC_VNM monthly → daily (tạo persistence & lead-lag giả).
- **Hệ quả trực tiếp:** daily backtest cho VN KHÔNG dùng được GPRC_VNM. Daily country shock phải đến từ: AI-GPR daily, bilateral daily, hoặc corpus báo Việt (V-phase). → **G2b track daily ban đầu chỉ chạy với GPRD global + macro; GPRC_VNM chỉ vào track monthly.** Đây là điều chỉnh scope quan trọng.

### 2.7 [4.8] Final holdout + chống snooping
Chia dữ liệu:
```
2015–2020  Development/training
2021–2023  Validation/model selection
2024–2025  Pseudo-OOS walk-forward
2026-H1    FINAL HOLDOUT — khóa, chạm đúng 1 lần cuối cùng
```
Thêm: Deflated Sharpe Ratio, White Reality Check / Hansen SPA, block bootstrap, purging + embargo, CI cho IC và cho chênh lệch Sharpe, transaction-cost sensitivity. Gate G3 đổi từ "IC>0.03 & Sharpe>benchmark" → "incremental IC>0 với CI rõ, ổn định qua regime, dương sau phí".

### 2.8 [available_at + G0 + claims matrix]
- **Schema:** thêm `available_at, revised_at, source_version, data_version, quality_flag` vào `ext_series`; quy tắc backtest `available_at ≤ decision_time`, không dùng `date` làm proxy.
- **G0 Research Governance** (trước ingest): hypothesis registry, holdout policy, multiple-testing policy, causal claims matrix, versioning policy.
- **Causal claims matrix** — chỉ claim đúng mức nhận dạng:

| Thành phần | Claim tối đa cho phép |
|---|---|
| LLM score | measurement |
| GPR→return OLS/LP | association / predictive |
| GPR innovation→market LP | reduced-form response |
| LP-IV / proxy-SVAR (nếu instrument hợp lệ) | structural response |
| tích hai hệ số (convolution) | transmission decomposition |
| dynamic mediation CÓ identification | causal mediation |

---

## 3. ĐIỂM PHẢN BIỆN / ĐIỀU CHỈNH MỨC ĐỘ (⚪🟢)

### 3.1 [4.3/G2.5] Structural identification — đúng học thuật, KHÔNG chặn sản phẩm
Review muốn LP-IV/proxy-SVAR để claim nhân quả. Đúng — nhưng chỉ cần cho **publish paper**, không cần cho **sản phẩm** (risk monitoring + tín hiệu BeaverX chỉ cần reduced-form/predictive). Quyết định: structural là **G2.5 optional trên track nghiên cứu**, chạy song song, không phải điều kiện chặn G3/G4. Điều bắt buộc (và rẻ): **gọi tên đúng** — "transmission decomposition"/"predictive", không "causal" — cho tới khi có ID. Điểm này đồng ý 100%.

### 3.2 [4.16] Historical reconstruction — hạ cấp mạnh hơn
Đồng ý và hạ cấp: ra khỏi main model hoàn toàn, chỉ exploratory appendix. Không để LLM web-search tự do; nếu dùng phải search trong archive định trước, mỗi event kèm date/source/verification/confidence/version.

### 3.3 [4.10] Severity — tiếp thu nhưng optional ở V1
Đúng về khái niệm (nuclear threat severity cao ≠ act nhẹ). Nhưng thêm chiều chấm làm rubric nặng & audit khó. Quyết định: thêm trường `severity` vào schema, **optional ở V1**; chỉ bắt buộc nếu human audit cho thấy trộn severity gây sai lệch đáng kể.

### 3.4 [4.14] Actor weighting — phần lớn đã lường trước
Đã có ý "predictive weight, không causal". Tiếp thu bổ sung danh sách control (severity, event-FE, time-FE, pre-event vol, attention). Không phải sửa lớn.

---

## 4. THỨ TỰ THỰC THI SAU TIẾP THU (cập nhật build order)

```
G0  Research Governance         ← MỚI: registry, holdout policy, claims matrix, versioning
G1  Ingest & Data Audit         ← +available_at/revised_at/quality_flag; audit publication time
G2.0 Feature foundation         ← MỚI: level/persistent/innovation/jump/surprise; tách 3 pipeline
G2a Global Macro (reduced-form) ← innovation→macro; gate không confirmation-bias
G2b Country reduced-form        ← direct innovation→VN (daily: GPRD only; monthly: +GPRC_VNM)
G2c So sánh generic vs channel vs threat vs act-surprise
G2.5 Structural ID (optional)   ← track nghiên cứu, không chặn
G3  Locked backtest             ← final holdout 2026-H1; Deflated Sharpe, SPA; benchmark non-GPR
G4  Serving risk monitor        ← triển khai được cả khi alpha fail; historical contribution
G5  S-GPR                       ← +gold set validation, silence modeling, sum/mean/max
G6  Physical events             ← GDELT daily+monthly; event clustering; recon chỉ appendix
G7  Fusion                      ← nested A/A+B/A+C/A+B+C/+divergence; delta-IC + CI mỗi bước
```

Điểm khác biệt lớn so với build order cũ: thêm **G0** và **G2.0**; **G2b tách daily/monthly** do ràng buộc forward-fill; **G3 siết governance**; **G2.5 structural** đưa vào nhưng không chặn.

---

## 5. FILE BỊ ẢNH HƯỞNG (cần cập nhật theo doc này)

| File | Thay đổi |
|---|---|
| `07_formulas_reference.md` | **ĐÃ SỬA** → v2: convolution (§5.2), 3 hệ số (§5.1), innovation thay level (§2), Shapley (§5.3), bảng claims. Bản cũ lưu ở `07_..._v1_archived.md` |
| `05_build_order.md` | Thêm G0, G2.0; tách G2b daily/monthly; siết G3 (cần cập nhật) |
| `06_transmission_cascade_update.md` | Sửa mục mediation → convolution; 3 hệ số (cần cập nhật) |
| `sql/001_schema_core.sql` | Thêm available_at/revised_at/quality_flag (cần cập nhật) |
| `CLAUDE.md` | Thêm nguyên tắc: innovation-not-level, no forward-fill, claims matrix (cần cập nhật) |

Ưu tiên đã làm ngay: **file 07** (vì phục vụ report). Các file còn lại cập nhật ở vòng sau.

---

## 6. KẾT LUẬN PHẢN HỒI

Review đúng ở phần cốt lõi: rủi ro lớn nhất không phải code/hạ tầng mà là **định nghĩa shock (level vs innovation), nhận dạng nhân quả, dynamic transmission, leakage backtest**. Tám điểm 🔴 phải sửa trước khi kết quả G2 có nghĩa. Phần còn lại tiếp thu theo lịch, có vài chỗ hạ ưu tiên để không làm dự án nặng lên trước khi có sản phẩm.

Giá trị giữ nguyên: kiến trúc 3 chân + global-first + gate incremental value + research-trước-serving vẫn đúng và được review khen. Việc sửa là **tinh chỉnh phương pháp bên trong khung đó**, không phải làm lại khung.
