# CÔNG THỨC MÔ HÌNH GPR ENGINE — THAM CHIẾU CHO REPORT

**Phiên bản:** 2.1 — 07/2026 (sửa theo review `08` / phản hồi `09`)
**Mục đích:** Tập hợp đầy đủ công thức từng tầng để viết report. Ký hiệu thống nhất, kèm nguồn học thuật và ghi chú triển khai. Công thức cuối (§5) là dạng áp dụng cho một quốc gia bất kỳ.
**Thay đổi v2 (bản v1 lưu tại `07_formulas_reference_v1_archived.md`):**
- §2: mọi "shock" dùng **innovation**, không dùng level ($\ln(1+\text{GPR})$ chỉ là mức, không phải cú sốc). Thêm decomposition level/persistent/innovation/jump.
- §3 (v2.1): phương trình tầng 2 đổi level → innovation cho khớp §2.0 (bản v2.0 còn sót `GPR̃^j_t`); thêm controls $Z_t$, EMSpread, ghi chú vô hiệu hóa kết quả G2a chạy trên level.
- §5.1: phương trình tầng 3 tách **3 hệ số** — global-direct ($\beta$), indirect qua macro ($\theta$), domestic-direct ($\lambda$).
- §5.2: indirect effect là **tích chập động (dynamic convolution)**, không phải nhân hai hệ số cùng horizon. Gọi là "transmission decomposition", không "causal mediation" (trừ khi có structural identification).
- §5.3: thay variance-share ngây thơ bằng **Shapley/LMG/historical contribution** (công thức cũ bỏ covariance, tổng có thể >100%).

---

## 0. QUY ƯỚC KÝ HIỆU

| Ký hiệu | Ý nghĩa |
|---|---|
| $t$ | thời điểm (ngày hoặc tháng) |
| $h$ | horizon dự báo (số ngày/tháng phía trước) |
| $c$ | quốc gia đích (VN, TH, ID...) |
| $j$ | nguồn shock (US, CN, RU, MidEast...) |
| $s_i$ | điểm địa chính trị của bài báo/phát ngôn $i$ |
| $N_t$ | tổng số bài báo trong kỳ $t$ (chuẩn hóa) |
| $M$ | biến vĩ mô toàn cầu (Oil, DXY, VIX, US10Y) |
| $r^c_t$ | tỷ suất sinh lời thị trường nước $c$ |
| $\perp$ | ký hiệu phần dư đã trực giao hóa (orthogonalized) |

**Quy ước biến đổi bắt buộc:** mọi chỉ số GPR vào hồi quy dùng $\widetilde{\text{GPR}} = \ln(1+\text{GPR})$ (do phân phối lệch phải mạnh — mean/std ≈ 0.05 với country-GPR nước nhỏ). Giá tài sản dùng log-difference $\Delta \ln$.

---

## 1. TẦNG 0 — LƯỢNG TỬ HÓA (tin tức/phát ngôn → số)

### 1.1. Điểm một đơn vị tin

**Dictionary (cổ điển, Caldara-Iacoviello 2022):**
$$
s_i = \mathbb{1}[\text{bài } i \text{ chứa từ khóa địa chính trị trong phạm vi gần}] \in \{0,1\}
$$

**LLM scoring (AI-GPR, Iacoviello-Tong 2026):**
$$
s_i = f_{\text{LLM}}(\text{text}_i \mid \text{rubric}) \in [0.0,\ 1.0]
$$

**Phát ngôn (S-GPR, thang có dấu — thiết kế riêng):**
$$
v_i = f_{\text{LLM}}(\text{statement}_i \mid \text{rubric}^{\pm}) \in [-1.0,\ +1.0]
$$
âm = hòa giải, dương = leo thang.

### 1.2. Tổng hợp thành chỉ số thời gian

**GPR tổng quát:**
$$
\boxed{\ \text{GPR}_t = 100 \times \frac{1}{N_t}\sum_{i \in D_t} s_i\ }
$$

**Country-specific:**
$$
\text{GPR}^{c}_t = 100 \times \frac{1}{N_t}\sum_{i \in D_t} s_i \cdot \mathbb{1}[\text{country}_i = c]
$$

**Bilateral (chỉ LLM làm được — trích actor→target):**
$$
\text{GPR}^{a \to b}_t = 100 \times \frac{1}{N_t}\sum_{i \in D_t} s_i \cdot \mathbb{1}[\text{actor}_i=a,\ \text{target}_i=b]
$$

### 1.3. Tách Threats / Acts
$$
\text{GPR}_t = \underbrace{\text{GPT}_t}_{\text{threats, cat 1-5}} + \underbrace{\text{GPA}_t}_{\text{acts, cat 6-8}}
$$

### 1.4. Trọng số người phát ngôn (Actor-Weighted)
$$
\text{AW-GPR}_t = 100 \times \frac{1}{N_t}\sum_{i \in D_t} w(\text{role}_i,\,\text{attention}_t)\cdot s_i
$$
Trọng số $w$ **ước lượng từ dữ liệu** (speaker fixed-effects, §4.4), không gán tay.

---

## 2. TẦNG 1 — SHOCK ĐỊA CHÍNH TRỊ (input của cascade)

### 2.0. LEVEL ≠ SHOCK — decomposition bắt buộc (sửa theo review 4.4)

$\ln(1+\text{GPR})$ chỉ là **mức**, chứa cả tin cũ lặp lại, phần đã dự báo, và regime kéo dài. Đưa mức vào hồi quy rồi gọi hệ số là "tác động của cú sốc" là **sai khái niệm**. Trước khi dùng trong bất kỳ tầng nào, tách:

$$
\begin{aligned}
\text{Level}_t      &= \ln(1+\text{GPR}_t) \\
\text{Persistent}_t &= \mathbb{E}_{t-1}[\text{Level}_t] \quad(\text{AR/EWMA dự báo 1 bước, chỉ dùng quá khứ}) \\
\boxed{\text{Innovation}_t} &= \text{Level}_t - \text{Persistent}_t \quad(\textbf{cú sốc chính cho Local Projection}) \\
\text{Jump}_t       &= \max(0,\ z_t - q_{0.95}) \quad(\text{phần đuôi, sự kiện cực đoan}) \\
\text{LevelPlusJump}_t &= \text{Level}_t + \text{Jump}_t
\end{aligned}
$$

Áp dụng riêng cho threats và acts: $\text{GPT}^{\text{innov}}_t$, và $\text{GPA}^{\text{surprise}}_t$ (§2.2). **Quy tắc: mọi ký hiệu "shock" từ đây trở đi là innovation/surprise, KHÔNG phải level.**

**Quy tắc thời điểm biết dữ liệu:** GPR daily của ngày $D$ chỉ vào information set từ
$D+1$; các giá trị mới biết trong cuối tuần được gộp vào phiên kế tiếp. GPR monthly
của tháng $M$ chỉ vào bucket quyết định $M+1$. Mọi backtest realtime vẫn phải lọc
theo timestamp `available_at`, không chỉ dịch index theo ngày/tháng.

### 2.1. Vector shock

$$
\mathbf{G}_t = \big(\text{GPT}^{\text{innov}}_t,\ \text{GPA}^{\text{surprise}}_t,\ \{\text{GPR}^{j,\text{innov}}_t\}_j,\ \text{Jump}_t\big)
$$

### 2.2. Surprise Index (phần shock chưa được price-in — thiết kế riêng)
$$
\boxed{\ \text{GPA}^{\text{surprise}}_t = \text{GPA}_t - \mathbb{E}\!\left[\text{GPA}_t \mid \text{GPT}_{t-1..t-k},\ \text{S-GPR}_{t-1..t-k},\ \text{Ladder}_{t-1}\right]\ }
$$
Kỳ vọng ước lượng bằng mô hình dự báo rolling (không dùng dữ liệu tương lai). Cơ sở: acts đã dự đoán trước thì thị trường đã định giá; chỉ phần bất ngờ mới di chuyển giá.

**Escalation Ladder (trạng thái cặp nước):**
$$
L^{a\text{-}b}_t \in \{S_0,\,S_1,\,S_2,\,S_3,\,S_4\}
$$
(bình thường → khẩu chiến → đe dọa → chuẩn bị → hành động). V1 rule-based theo ngưỡng percentile của 3 chân; V2 HMM regime-switching.

---

## 3. TẦNG 2 — GLOBAL MACRO RESPONSE (generic, dùng chung mọi nước)

**"1 cú sốc địa chính trị đẩy dầu/đô/risk-off toàn cầu bao nhiêu."** Đây là deliverable độc lập, không cần VN.

Với mỗi biến vĩ mô $M \in \{\Delta\ln\text{Oil},\,\Delta\ln\text{DXY},\,\text{VIX},\,\Delta\text{US10Y},\,\text{EMSpread}\}$, ước lượng bằng **Local Projection (Jordà 2005)** cho từng horizon $h$:

$$
\boxed{\ M_{t+h} = a_M^{(h)} + \sum_j \gamma_{M,j}^{(h)}\,\text{GPR}^{j,\text{innov}}_t + \sum_{k=1}^{p}\rho_{M,k}^{(h)} M_{t-k} + \Gamma^{(h)}Z_t + \eta_{M,t+h}\ }
$$

- **Shock ở đây là innovation (§2.0), KHÔNG phải level $\widetilde{\text{GPR}}^j_t$.** Đưa level vào rồi gọi $\gamma$ là "phản ứng với cú sốc" chính là lỗi review 4.4 chỉ ra: level có autocorrelation cao, phần lớn giá trị hôm nay đã biết từ hôm qua, nên $\gamma$ ước lượng được sẽ trộn "phản ứng với tin mới" và "mức rủi ro nền đang cao". Shock hợp lệ: $\text{GPR}^{j,\text{innov}}$, $\text{GPT}^{\text{innov}}$, $\text{GPA}^{\text{surprise}}$, $\text{Jump}$, hoặc channel-specific shock (energy/trade/sanction/military).
- $\gamma_{M,j}^{(h)}$ = **impulse response**: phản ứng của $M$ tại $h$ ngày sau 1 đơn vị **innovation** từ nguồn $j$.
- $Z_t$ = controls (lag của shock, biến vĩ mô khác) — cần để $\gamma$ không hút phần đã dự báo được.
- Sai số chuẩn: **Newey-West (HAC)** vì horizon chồng lấn.
- Theo channel (khi có S-GPR): shock kênh `energy` → $\gamma_{\text{oil}}$ cao; kênh `trade` → $\gamma_{\text{dxy}},\gamma_{\text{vix}}$ cao. **Không ép dấu kỳ vọng** — gate G2a đã bỏ tiêu chí "đúng dấu literature" (review 4.6): trade war có thể làm dầu GIẢM do cầu yếu.

**Ghi chú kết quả cũ:** report `docs/reports/G2a_global_macro.md` chạy trên **level**, không phải innovation → kết luận "GPRD coincident, không leading" **không có hiệu lực** với đặc tả này. Chuỗi level autocorrelated thì "coincident" gần như là kết quả mặc định. Phải chạy lại ở G2.0/G2a với innovation rồi mới kết luận GO/NO-GO.

**Kết quả tầng 2 = tập hợp IRF:**
$$
\text{IRF}_{M,j} = \big\{\gamma_{M,j}^{(0)},\,\gamma_{M,j}^{(1)},\,\dots,\,\gamma_{M,j}^{(H)}\big\}
$$

---

## 4. THÀNH PHẦN CHUẨN BỊ CHO TẦNG 3

### 4.1. Orthogonalization (tách phần riêng nước $c$ khỏi global)
$$
\boxed{\ \widetilde{\text{GPR}}^{c}_t = \underbrace{\hat f\big(\widetilde{\text{GPR}}^{\text{glob}}_t,\widetilde{\text{GPR}}^{US}_t,\widetilde{\text{GPR}}^{CN}_t,\text{Oil}_t\big)}_{\text{thành phần global}} + \underbrace{\widetilde{\text{GPR}}^{c,\perp}_t}_{\text{shock riêng nước }c}\ }
$$
Phần dư $\widetilde{\text{GPR}}^{c,\perp}$ chính là **direct shock** ở tầng 3. (Với VN, tương quan raw GPRC_VNM ~ GPRD global đo được ≈ 0.48 → có ~50% phương sai là thành phần riêng.)

### 4.2. Trọng số người phát ngôn (ước lượng)
Hồi quy phản ứng thị trường cửa sổ ngắn $[\tau, \tau+\delta]$ quanh thời điểm phát ngôn lên điểm × dummy người nói:
$$
\Delta r_{[\tau,\tau+\delta]} = \sum_a \beta_a\,(s_i \cdot \mathbb{1}[\text{speaker}=a]) + \text{controls} + e
$$
$\hat\beta_a$ chuẩn hóa → $w(\text{role}_a)$. (Bằng chứng: phát ngôn nguyên thủ/Fed Chair tác động > cấp thấp hơn.)

---

## 5. TẦNG 3 — COUNTRY TRANSMISSION (công thức cuối, áp cho 1 nước bất kỳ)

Đây là **công thức áp dụng cuối cùng**. Thay $c = $ VN, TH, ID... — cùng dạng, chỉ khác bộ hệ số.

### 5.1. Phương trình chính — BA hệ số (Local Projection, horizon $h$)

Sửa theo review 4.2: tách rõ **global-direct** ($\beta$), **indirect qua macro** ($\theta$), **domestic-direct** ($\lambda$). Mọi shock là innovation (§2.0), không phải level.

$$
\boxed{
\begin{aligned}
r^{c}_{t+h} = \alpha^{c}_{(h)}
&+ \underbrace{\sum_j \beta^{c}_{j,(h)}\,\text{GPR}^{j,\text{innov}}_t}_{\text{GLOBAL-DIRECT — global shock đánh thẳng NĐT nước }c,\text{ KHÔNG qua macro}} \\[4pt]
&+ \underbrace{\theta^{c}_{\text{oil},(h)}\Delta\ln\text{Oil}_t + \theta^{c}_{\text{dxy},(h)}\Delta\ln\text{DXY}_t + \theta^{c}_{\text{vix},(h)}\text{VIX}_t + \theta^{c}_{\text{rate},(h)}\Delta\text{US10Y}_t}_{\text{INDIRECT — qua kênh vĩ mô toàn cầu (tầng 2)}} \\[4pt]
&+ \underbrace{\lambda^{c}_{(h)}\,\text{GPR}^{c,\perp,\text{innov}}_t}_{\text{DOMESTIC-DIRECT — rủi ro riêng nước }c} \\[4pt]
&+ \Phi^{c}\mathbf{X}^{c}_t + \varepsilon^{c}_{t+h}
\end{aligned}
}
$$

- $\mathbf{X}^c_t$ = kiểm soát nội địa (lag $r^c$, thanh khoản, lãi suất trong nước).
- Phân biệt then chốt: $\beta$ (global-direct) và $\lambda$ (domestic-direct) là HAI thứ khác nhau — trước đây v1 gộp làm một. $\text{GPR}^{c,\perp}$ là phần riêng nước $c$ đã trực giao khỏi global (§4.1), KHÔNG phải là tác động trực tiếp của global shock.

### 5.2. Dynamic transmission decomposition (sửa theo review 4.1)

**Không** nhân hai hệ số cùng horizon. Indirect effect là **tích chập theo thời gian** — shock đẩy mediator ở bước $s$, mediator đánh thị trường ở bước $h-s$:

$$
\boxed{\ \text{Indirect}_{j\to c}(h) = \sum_M \sum_{s=0}^{h} \gamma_{M,j}(s)\,\theta^{c}_M(h-s)\ }
$$

Tổng tác động global của nguồn $j$:
$$
\text{Total}^{\text{global}}_{j\to c}(h) = \underbrace{\beta^{c}_{j,(h)}}_{\text{global-direct}} + \underbrace{\text{Indirect}_{j\to c}(h)}_{\text{qua macro, convolution}}
$$

Tác động domestic (riêng nước $c$, không từ nguồn $j$ nào bên ngoài):
$$
\text{Total}^{\text{domestic}}_{c}(h) = \lambda^{c}_{(h)}
$$

**Cách gọi tên (review 4.3, claims matrix §7):** đây là **transmission decomposition** ở dạng reduced-form/predictive. CHƯA gọi "causal mediation" cho tới khi có structural identification (LP-IV / proxy-SVAR). Diễn giải định lượng vẫn giữ: Indirect ≫ (β + λ) → nước $c$ chịu shock chủ yếu qua kênh vĩ mô toàn cầu; λ đáng kể → có rủi ro riêng, biện minh corpus bản địa.

### 5.3. Đóng góp từng kênh — Shapley / Historical (sửa theo review 4.5)

**KHÔNG dùng** $\text{Share}_M = \theta_M^2\text{Var}(M)/\text{Var}(r)$ — công thức này bỏ qua hiệp phương sai giữa Oil/DXY/VIX (chúng tương quan mạnh), làm $\sum_M \text{Share}_M$ có thể vượt 100%.

**Dùng thay:**
- Reduced-form: **Shapley / LMG decomposition** của $R^2$ — chia đều đóng góp qua mọi thứ tự đưa biến vào, xử lý được covariance.
$$
\text{Share}_k^{\text{Shapley}} = \sum_{S \subseteq K\setminus\{k\}} \frac{|S|!\,(|K|-|S|-1)!}{|K|!}\big[R^2(S\cup\{k\}) - R^2(S)\big]
$$
- Structural VAR: **FEVD / generalized FEVD**.
- Serving hàng ngày: **historical contribution** — hữu ích nhất cho giải thích thị trường:
```
VN-Index giảm hôm nay:
  VIX channel:            x%
  DXY channel:            y%
  Oil channel:            z%
  Vietnam-specific shock: k%
  unexplained:            phần còn lại
```

### 5.4. Hệ số exposure (tùy chọn — liên kết $\theta^c$ với cấu trúc kinh tế)
Nếu muốn giải thích *vì sao* $\theta^c$ cao/thấp theo đặc điểm nước:
$$
\theta^{c}_{M} = \bar\theta_M \cdot \big(1 + \delta_M \cdot \text{Exposure}^{c}_M\big)
$$
Ví dụ VN: $\text{Exposure}^{VN}_{\text{dxy}}$ hàm của (tỷ trọng XK sang Mỹ, tỷ trọng FII, độ mở tài khoản vốn). **Phần này chưa validate — cần backtest riêng.**

---

## 6. TẦNG TÍN HIỆU — TỪ MÔ HÌNH SANG GIAO DỊCH

### 6.1. Regime toàn cầu (từ tầng 2)
$$
\text{Regime}_t = \text{percentile}_{1Y}\!\big(\text{Global Macro Impact}_t\big),\quad \text{risk-off nếu} > 90
$$

### 6.2. Divergence signals (3 chân)
$$
\text{EARLY\_WARN}_t = z(\text{S-GPR}_t) - z(\text{GPR}_t);\quad
\text{SILENT\_RISK}_t = z(\text{Goldstein}^{-}_t) - z(\text{GPR}_t)
$$

### 6.3. Đánh giá tín hiệu
$$
\text{IC}_h = \text{corr}\big(\text{signal}_t,\ r^{c}_{t+h}\big),\qquad
\text{Sharpe} = \frac{\mathbb{E}[R_p]-R_f}{\sigma(R_p)}
$$
Governance (sửa theo review 4.8): dữ liệu chia Development (2015–2020) / Validation (2021–2023) / Pseudo-OOS (2024–2025) / **Final holdout 2026-H1 (khóa, chạm 1 lần)**. Báo cáo kèm **Deflated Sharpe**, White Reality Check/Hansen SPA, CI cho IC và cho chênh lệch Sharpe, sau phí. Gate: incremental IC > 0 với CI rõ + ổn định qua regime, KHÔNG chỉ "IC>0.03".

### 6.4. Ma trận claims — chỉ tuyên bố đúng mức nhận dạng (review 4.3, kết luận)
$$\text{measurement} \prec \text{association} \prec \text{prediction} \prec \text{structural response} \prec \text{causal effect}$$

| Thành phần | Claim tối đa |
|---|---|
| LLM score | measurement |
| GPR innovation → return (OLS/LP) | association / predictive |
| GPR innovation → market (reduced-form LP) | reduced-form response |
| LP-IV / proxy-SVAR (instrument hợp lệ) | structural response |
| tích chập hai hệ số (§5.2) | transmission decomposition |
| dynamic mediation CÓ identification | causal mediation |

---

## 7. BẢNG NGUỒN CÔNG THỨC (cho phần trích dẫn của report)

| Công thức | Nguồn | Trạng thái |
|---|---|---|
| §1.2 GPR aggregation | Caldara & Iacoviello (2022, AER 112(4):1194-1225) | Published |
| §1.1 LLM scoring | Iacoviello & Tong (2026, working paper) | Published |
| §1.3 GPT/GPA | Caldara & Iacoviello (2022) | Published |
| §2.0 Innovation-not-level | Chuẩn (news-shock / VAR innovation) | Chuẩn |
| §3, §5 Local Projection | Jordà (2005, AER 95(1):161-182) | Published |
| §5.2 Dynamic convolution (IRF chaining) | Chuẩn (impulse-response algebra) | Chuẩn |
| §3, §5 Panel VAR + country FE | Caldara, Conlisk, Iacoviello, Penn (2026, JIE 159:104188) | Published |
| §5 TVP-VAR connectedness (bản tài chính) | Cao & Vo (2025, Heliyon 11(4):e42703); Antonakakis-Gabauer | Published |
| §4.1 Orthogonalization | Kỹ thuật chuẩn (Frisch-Waugh-Lovell) | Chuẩn |
| §5.3 Shapley/LMG decomposition | Grömping (2007); Lindeman-Merenda-Gold | Published |
| §1.4, §4.2 Actor weighting | Filbien et al. + bằng chứng Fed-chair; đóng gói riêng | Predictive weight — tự xây |
| §5.1 Cấu trúc 3 hệ số (β/θ/λ) | Tổng hợp riêng | **Đóng góp gốc — reduced-form, cần backtest** |
| §1.1 S-GPR có dấu, §2.2 Surprise, §2 Ladder | Thiết kế riêng | **Đóng góp gốc — cần backtest** |
| §5.4 Exposure coefficient | Thiết kế riêng | **Chưa validate** |

**Lưu ý claim (quan trọng cho report):** §5 ở dạng reduced-form → gọi "transmission decomposition"/"predictive", KHÔNG gọi "causal", trừ khi bổ sung structural identification (G2.5).

---

## 8. TÓM TẮT MỘT TRANG (sơ đồ công thức)

```
TIN/PHÁT NGÔN ──[§1.1 f_LLM]──▶ s_i, v_i
      │
      ├──[§1.2 aggregate]──▶ GPR, GPR^c, GPR^{a→b}
      ├──[§1.3]──▶ GPT + GPA
      └──[§1.4]──▶ AW-GPR (predictive weight)
                        │
        [§2.0] LEVEL → PERSISTENT → INNOVATION   ← shock = innovation, KHÔNG phải level
        [§2.2 Surprise, §2 Ladder] ──▶ SHOCK VECTOR G_t (innovation-based)
                        │
        ┌───────────────┴───────────────┐
        ▼ TẦNG 2 (generic)
   [§3 Local Projection]  M_{t+h} = a + Σ_j γ·GPR^{j,innov} + Σρ·M_lag + Γ·Z + η
   innovation → Oil, DXY, VIX, US10Y, EMSpread     ← KHÔNG dùng level
   = γ_{M,j}(s)  (Global Macro Impact)   ← deliverable độc lập
        │
        ▼ TẦNG 3 (params riêng nước c)
   [§4.1 orthogonalize] → GPR^{c,⊥,innov}
   [§5.1] r^c = β·GPR^{j,innov}      (global-direct)
              + θ·(macro)            (indirect)
              + λ·GPR^{c,⊥,innov}    (domestic-direct)
              + controls
        │
   [§5.2] Indirect(h) = Σ_M Σ_s γ_{M,j}(s)·θ^c_M(h−s)   ← CONVOLUTION
          Total^global = β + Indirect ;  Total^domestic = λ
          (transmission decomposition, KHÔNG causal trừ khi có ID)
   [§5.3] Shapley / historical contribution   ← KHÔNG dùng θ²Var/Var
        │
        ▼
   [§6] regime · divergence · IC/Sharpe (Deflated, final holdout 2026-H1)
   [§6.4] claims: measurement ≺ association ≺ prediction ≺ structural ≺ causal
```
