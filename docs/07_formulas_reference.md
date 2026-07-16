# CÔNG THỨC MÔ HÌNH GPR ENGINE — THAM CHIẾU CHO REPORT

**Phiên bản:** 1.0 — 07/2026
**Mục đích:** Tập hợp đầy đủ công thức từng tầng để viết report. Ký hiệu thống nhất, kèm nguồn học thuật và ghi chú triển khai. Công thức cuối (§5) là dạng áp dụng cho một quốc gia bất kỳ.

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

Vector shock tại $t$:
$$
\mathbf{G}_t = \big(\widetilde{\text{GPT}}_t,\ \widetilde{\text{GPA}}_t,\ \{\widetilde{\text{GPR}}^{j}_t\}_j,\ \text{Surprise}_t\big)
$$

**Surprise Index (phần shock chưa được price-in — thiết kế riêng):**
$$
\boxed{\ \text{Surprise}_t = \text{GPA}_t - \mathbb{E}\!\left[\text{GPA}_t \mid \text{GPT}_{t-1..t-k},\ \text{S-GPR}_{t-1..t-k},\ \text{Ladder}_{t-1}\right]\ }
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

Với mỗi biến vĩ mô $M \in \{\Delta\ln\text{Oil},\,\Delta\ln\text{DXY},\,\text{VIX},\,\Delta\text{US10Y}\}$, ước lượng bằng **Local Projection (Jordà 2005)** cho từng horizon $h$:

$$
\boxed{\ M_{t+h} = a_M^{(h)} + \sum_j \gamma_{M,j}^{(h)}\,\widetilde{\text{GPR}}^{j}_t + \sum_{k=1}^{p}\rho_{M,k}^{(h)} M_{t-k} + \eta_{M,t+h}\ }
$$

- $\gamma_{M,j}^{(h)}$ = **impulse response**: phản ứng của biến vĩ mô $M$ tại $h$ ngày sau 1 đơn vị shock từ nguồn $j$.
- Sai số chuẩn: **Newey-West (HAC)** vì horizon chồng lấn.
- Theo channel (khi có S-GPR): shock kênh `energy` → $\gamma_{\text{oil}}$ cao; kênh `trade` → $\gamma_{\text{dxy}},\gamma_{\text{vix}}$ cao.

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

### 5.1. Phương trình chính (Local Projection, horizon $h$)

$$
\boxed{
\begin{aligned}
r^{c}_{t+h} = \alpha^{c}_{(h)}
&+ \underbrace{\theta^{c}_{\text{oil},(h)}\Delta\ln\text{Oil}_t + \theta^{c}_{\text{dxy},(h)}\Delta\ln\text{DXY}_t + \theta^{c}_{\text{vix},(h)}\text{VIX}_t + \theta^{c}_{\text{rate},(h)}\Delta\text{US10Y}_t}_{\text{INDIRECT — shock đã truyền qua kênh vĩ mô toàn cầu (tầng 2)}} \\[4pt]
&+ \underbrace{\lambda^{c}_{(h)}\,\widetilde{\text{GPR}}^{c,\perp}_t}_{\text{DIRECT — đánh thẳng vào tâm lý NĐT nước } c} \\[4pt]
&+ \underbrace{\Phi^{c}\mathbf{X}^{c}_t}_{\text{kiểm soát nội địa}} + \varepsilon^{c}_{t+h}
\end{aligned}
}
$$

Trong đó $\mathbf{X}^c_t$ = biến kiểm soát nội địa (lag của chính $r^c$, thanh khoản, lãi suất trong nước...).

### 5.2. Phân rã tổng tác động (mediation)

Tổng tác động của một shock địa chính trị nguồn $j$ lên thị trường nước $c$:

$$
\boxed{
\underbrace{\frac{\partial r^{c}_{t+h}}{\partial\,\widetilde{\text{GPR}}^{j}_t}}_{\text{Total}}
= \underbrace{\lambda^{c}_{(h)}\cdot\frac{\partial\widetilde{\text{GPR}}^{c,\perp}}{\partial\widetilde{\text{GPR}}^{j}}}_{\text{Direct}}
+ \underbrace{\sum_{M}\theta^{c}_{M,(h)}\cdot\gamma^{(h)}_{M,j}}_{\text{Indirect (qua tầng 2)}}
}
$$

- **Indirect** = (shock đẩy biến vĩ mô $M$ bao nhiêu: $\gamma_{M,j}$ từ tầng 2) × (nước $c$ nhạy với $M$ bao nhiêu: $\theta^c_M$ từ tầng 3).
- Diễn giải: nếu Indirect ≫ Direct → nước $c$ chịu shock chủ yếu qua kênh vĩ mô toàn cầu (điển hình cho nền kinh tế nhỏ mở). Nếu Direct đáng kể → có rủi ro riêng không qua global (biện minh cho corpus bản địa).

### 5.3. Variance decomposition (đóng góp từng kênh)
Khi $r^c$ biến động, tỷ lệ đóng góp của mỗi kênh:
$$
\text{Share}_{M} = \frac{\big(\theta^{c}_{M}\big)^2\,\text{Var}(M)}{\text{Var}(r^{c})},\qquad
\text{Share}_{\text{direct}} = \frac{\big(\lambda^{c}\big)^2\,\text{Var}(\widetilde{\text{GPR}}^{c,\perp})}{\text{Var}(r^{c})}
$$

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
Mọi giá trị báo cáo là **out-of-sample** (2023+).

---

## 7. BẢNG NGUỒN CÔNG THỨC (cho phần trích dẫn của report)

| Công thức | Nguồn | Trạng thái |
|---|---|---|
| §1.2 GPR aggregation | Caldara & Iacoviello (2022, AER 112(4):1194-1225) | Published |
| §1.1 LLM scoring | Iacoviello & Tong (2026, working paper) | Published |
| §1.3 GPT/GPA | Caldara & Iacoviello (2022) | Published |
| §2 Local Projection | Jordà (2005, AER 95(1):161-182) | Published |
| §3, §5 Panel VAR + country FE | Caldara, Conlisk, Iacoviello, Penn (2026, JIE 159:104188) | Published |
| §5 TVP-VAR connectedness (bản tài chính) | Cao & Vo (2025, Heliyon 11(4):e42703); Antonakakis-Gabauer | Published |
| §4.1 Orthogonalization | Kỹ thuật chuẩn (Frisch-Waugh-Lovell) | Chuẩn |
| §1.4, §4.2 Actor weighting | Filbien et al. + bằng chứng Fed-chair; đóng gói riêng | Ý tưởng có cơ sở, chỉ số tự xây |
| §2/§5 Cấu trúc 3 tầng mediation | Tổng hợp riêng (mediation analysis chuẩn) | **Đóng góp gốc — cần backtest** |
| §1.1 S-GPR có dấu, §2 Surprise, §2 Ladder | Thiết kế riêng | **Đóng góp gốc — cần backtest** |
| §5.4 Exposure coefficient | Thiết kế riêng | **Chưa validate** |

---

## 8. TÓM TẮT MỘT TRANG (sơ đồ công thức)

```
TIN/PHÁT NGÔN ──[§1.1 f_LLM]──▶ s_i, v_i
      │
      ├──[§1.2 aggregate]──▶ GPR, GPR^c, GPR^{a→b}
      ├──[§1.3]──▶ GPT + GPA
      └──[§1.4]──▶ AW-GPR
                        │
        [§2 Surprise, Ladder] ──▶ SHOCK VECTOR  G_t
                        │
        ┌───────────────┴───────────────┐
        ▼ TẦNG 2 (generic)              
   [§3 Local Projection]                
   G_t → Oil, DXY, VIX, US10Y           
   = γ_{M,j}  (Global Macro Impact)     ← deliverable độc lập
        │
        ▼ TẦNG 3 (params riêng nước c)
   [§4.1 orthogonalize] → GPR^{c,⊥}
   [§5.1] r^c = θ^c·(macro) + λ^c·GPR^{c,⊥} + controls
        │
   [§5.2 mediation]  Total = Direct + Indirect
   [§5.3 variance decomp]  đóng góp từng kênh
        │
        ▼
   [§6] regime, divergence, IC/Sharpe (OOS)
```
