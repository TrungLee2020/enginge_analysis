# 11 — PRODUCT PLAN v2.1 (BẢN ĐẦY ĐỦ)

**Phiên bản:** 2.1 — 2026-07-18. Thay thế v1.0 và v2.0. **Tự chứa — không cần đọc hai bản kia.**
**Quan hệ tài liệu:** đặt trên `00_engine_design.md`, `06_transmission_cascade_update.md`, `10_action_plan.md`. Ràng buộc claim: `07_formulas_reference_v2.md` §6.4 + `g0_governance.md` §5.
**Dùng để làm gì:** mở ra và viết code theo. §5 là spec công thức, §7 là bảng module, §10 là trình tự thi công.

---

## 0. ĐỊNH VỊ

**Nhà mô hình định lượng rủi ro địa chính trị → vĩ mô.** Xây trên dữ liệu địa chính trị lịch sử (GPR 1985+, chỉ số theo nước 120 năm) và tin tức/phát ngôn. Cùng lĩnh vực với S&P Global, **khác phương pháp**: họ xuất bản phân tích do chuyên gia viết, không khoảng tin cậy, không tái lập được, không có track record kiểm chứng được; ta định lượng, có sai số, có track record công khai.

Ba ràng buộc chi phối toàn bộ doc:

**R1 — Không bán dự báo điểm.** Mọi output là phân phối hoặc khoảng. Vừa là khác biệt cạnh tranh, vừa là trung thực với độ mạnh tín hiệu thực tế. **Hệ quả quan trọng: β yếu không giết sản phẩm phân phối** — nó chỉ làm dải rộng ra, và dải rộng là câu trả lời có nội dung ("bất định cao, đừng tin ai nói chắc").

**R2 — Track record công khai từ ngày đầu.** Công bố phân phối, chấm bằng CRPS (liên tục) và Brier (nhị phân), lịch sử mở. Thứ duy nhất xây được uy tín cho nhà mô hình chưa có thương hiệu — và là thứ đối thủ có thương hiệu để mất sẽ không làm.

**R3 — Chiều sâu lịch sử là moat.** Không cạnh tranh ở dữ liệu vận tải/thương mại hiện tại (S&P mạnh, ta không với tới). Cạnh tranh ở chuỗi episode dài — thứ sản phẩm phân phối cần và họ không ưu tiên.

### 0.1. Phát hiện định hình kiến trúc: chân A không realtime được

GPRD publish trễ ~1 ngày (`CLAUDE.md` #11, `available_at = date + 1d`); GPRC monthly còn trễ hơn. Vai trò 3 chân trong **sản phẩm** khác vai trò trong **nghiên cứu**:

| Chân | Trong research (docs 00–10) | Trong PRODUCT |
|---|---|---|
| A — Media (GPRD/GPRC) | Nguồn shock chính, làm econometrics | **Xương sống hiệu chuẩn lịch sử.** Phân vị, so sánh episode, ước lượng phản ứng. Không sinh cảnh báo realtime |
| B — Statements (S-GPR) | Nâng cấp có cổng, ở G5 | **Động cơ realtime chính.** Trump/Tập/FED/MOFA đăng lúc nào biết lúc đó, `published_at` chính xác đến phút |
| C — Events (GDELT) | Nâng cấp có cổng, ở G6 | Chân realtime thứ hai (update 15 phút), cross-check chân B. Giai đoạn sau |

**Kết luận thi công:** chân B lên đường găng sản phẩm. Không có chân B thì không có lớp realtime, bất kể tầng 2/3 pass hay fail.

Không mâu thuẫn kỷ luật cũ: `docs/09` §4 đã ghi G4 serving "triển khai được cả khi alpha fail"; `CLAUDE.md` tách Mục tiêu A (chỉ số — chắc đạt) khỏi Mục tiêu B (alpha — giả thuyết). Doc này nói rõ: **launch là Mục tiêu A. Alpha không phải điều kiện launch, và §13 đề nghị bỏ hẳn khỏi lộ trình.**

---

## 1. NGUYÊN TẮC BẤT BIẾN CỦA SẢN PHẨM

Bổ sung cho `CLAUDE.md`, phạm vi product.

**P1 — Không con số nào do LLM sinh ra.** LLM chỉ (a) chấm điểm phát ngôn theo rubric, (b) diễn đạt thành câu từ các trường **đã tính sẵn**. Mọi số đến từ DB. Test tự động: mọi số trong narrative phải khớp một trường trong payload; không khớp → **chặn xuất bản**, không phải cảnh báo.

**P2 — Không claim vượt mức nhận dạng.** Không bao giờ viết "sẽ làm VIX tăng". Viết "trong N đợt tương tự, VIX tăng trung vị x, IQR [a,b]". Ràng buộc này là **tài sản** — nó phân biệt sản phẩm với hàng chục bản tin AI đoán mò.

**P3 — Nói rõ khi không biết.** $n < 5$ episode, hoặc IQR đổi dấu → ghi "không kết luận được", không giấu. Card im lặng đúng lúc đáng tin hơn card luôn có ý kiến.

**P4 — Silence là thông tin.** Không có tin ≠ không có gì để nói. Trạng thái ladder duy trì ở bậc cao nhiều ngày là một nhận định riêng (`docs/09` điểm 4.13).

**P5 — Không khuyến nghị giao dịch.** Mô tả rủi ro, không nói mua/bán. Quan trọng vì BeaverX là nền tảng tư vấn đầu tư — ranh giới "thông tin" vs "khuyến nghị" có hệ quả pháp lý ở VN.

**P6 — Phân phối, không phải điểm.** Xem R1. Mọi phát biểu định lượng đi kèm khoảng.

**P7 — Realtime không nhận định.** Lớp realtime chỉ đo lường. Nhận định chỉ xuất hiện ở bản định kỳ. Lý do ở §2.1.

---

## 2. SẢN PHẨM

### 2.1. Hai lớp, hai nhịp — và vì sao

Literature tìm thấy tác động ở **tần suất tháng** trên **vĩ mô thực** (Caldara–Iacoviello 2022; Brignone–Gambetti–Ricci; ECB LGPT). Nhóm chạy **tần suất ngày trên giá tài sản** thấy liên kết yếu (CausalAlpha; và chính G2a của bạn). S&P Global — với toàn bộ nguồn lực của họ — xuất bản theo tháng.

Nhịp sản phẩm phải theo nhịp mà tín hiệu tồn tại, không theo nhịp mà công nghệ cho phép.

| Lớp | Nhịp | Claim ceiling | Nội dung |
|---|---|---|---|
| **1 — Đo lường** | realtime (giây–phút) | `measurement` | Trạng thái ladder, S-GPR, phân vị hiện tại, phát hiện sốc đuôi. **Không nhận định, không dự báo** |
| **2 — Nhận định** | tháng + bản bất thường khi $J_t > 0$ đáng kể | `association` / `predictive` | Phân phối có điều kiện theo kênh, kèm khoảng |

### 2.2. Measurement Card (lớp 1 — realtime)

```
┌────────────────────────────────────────────────────────────┐
│ ⚠️  LEO THANG · Mỹ → Trung Quốc · kênh THƯƠNG MẠI          │
│ 14:07 UTC+7 · 18/07/2026 · độ trễ phát hiện: 41 giây       │
├────────────────────────────────────────────────────────────┤
│ SỰ KIỆN                                                     │
│ Trump tuyên bố áp thuế bổ sung, hiệu lực 01/08.             │
│ Nguồn: Truth Social · [link]                                │
│                                                             │
│ ĐO LƯỜNG                          (claim: measurement)      │
│ v = +0.92  (bậc "Tuyên bố hành động")                       │
│ commitment = announced_action · specificity = 0.85          │
│ actor_role = head_of_state (w=1.0) · channel = trade        │
│                                                             │
│ TRẠNG THÁI                        (claim: measurement)      │
│ S-GPR(US→CN) 7 ngày: 2.1 → 4.8 (phân vị 94 kể từ 2015)     │
│ Escalation Ladder: S2 đe dọa → S4 hành động  ⬆ CHUYỂN BẬC  │
│ Đã ở S2 được 11 ngày                                        │
│ JUMP = 0.62  (vượt ngưỡng q95)  ⟶ kích hoạt bản bất thường │
│                                                             │
│ Đây là ghi nhận trạng thái, KHÔNG phải dự báo.              │
│ Nhận định định lượng sẽ có trong bản bất thường.            │
│                                                             │
│ [ ] Hữu ích   [ ] Không                                     │
└────────────────────────────────────────────────────────────┘
```

### 2.3. Model Brief (lớp 2 — định kỳ / bất thường)

```
┌────────────────────────────────────────────────────────────┐
│ BẢN BẤT THƯỜNG · sốc kênh THƯƠNG MẠI · 18/07/2026          │
├────────────────────────────────────────────────────────────┤
│ TRẠNG THÁI KÍCH HOẠT              (claim: measurement)      │
│ JUMP = 0.62 · phân vị 96 kể từ 1985 · kênh: trade          │
│                                                             │
│ PHÂN PHỐI CÓ ĐIỀU KIỆN            (claim: predictive)       │
│ Sản lượng CN toàn cầu, 6 tháng tới, thay đổi tích lũy:      │
│   τ=0.90  +1.2%                                             │
│   τ=0.50  −0.1%   ← trung vị gần như không đổi              │
│   τ=0.10  −2.8%   ← đuôi trái dày lên rõ                    │
│   P(giảm > 2%) = 18%  (baseline vô điều kiện: 7%)          │
│                                                             │
│ Đọc: cú sốc này không dịch chuyển kết quả kỳ vọng,          │
│ nó làm dày đuôi trái. Rủi ro tăng, không phải mức giảm      │
│ trung tâm tăng.                                             │
│                                                             │
│ BỐI CẢNH LỊCH SỬ                  (claim: association)      │
│ 6 lần chuyển S2→S4 trên trục US-CN kể từ 2018.              │
│ Diễn biến thực tế 6 tháng sau, trung vị (IQR):              │
│   VIX   +2.1 điểm  (+0.4 … +5.2)   5/6 lần tăng            │
│   DXY   +0.6%      (−0.2 … +1.1)                            │
│   Oil   −1.2%      (−3.4 … +0.8)   ← phân tán, không kết luận│
│   [xem danh sách 6 episode]                                 │
│                                                             │
│ ĐỘ TIN CẬY                                                  │
│ Mẫu analogue nhỏ (n=6). Phân phối ước lượng trên panel       │
│ tháng 1985–2026, n≈490. CI bootstrap theo khối.             │
│                                                             │
│ TRACK RECORD: [xem lịch sử chấm điểm CRPS/Brier]            │
└────────────────────────────────────────────────────────────┘
```

Bốn tầng, **mỗi tầng gắn nhãn claim theo `07v2` §6.4**, giảm dần độ chắc chắn. Người dùng thấy rõ đâu là sự thật đo được, đâu là ước lượng, đâu là quy nạp từ quá khứ.

### 2.4. Deliverable thương mại

1. **Global Macro Impact** (chính) — generic, bán cho bất kỳ ai, không cần VN.
2. **Country Transmission** (phụ) — `config/params/<country>.yaml`, VN trước.

Lớp đo lường realtime phục vụ **cả hai** — nó là lớp đo của engine global, không phải tính năng riêng VN.

---

## 3. KIẾN TRÚC

```
   NGUỒN (chân B + C)              XỬ LÝ                        PHỤC VỤ
┌──────────────────┐
│ Truth Social     │─┐
│ WhiteHouse RSS   │ │   ┌──────────┐   ┌───────────┐   ┌──────────────┐
│ Fed RSS          │ ├──▶│ collector│──▶│  dedup +  │──▶│   SCORER     │
│ MOFA CN          │ │   │  (poll)  │   │ clustering│   │ encoder lọc  │
│ USTR / Commerce  │ │   └──────────┘   └───────────┘   │ → LLM chấm   │
│ SBV / MoF (VN)   │ │        │                         └──────┬───────┘
│ GDELT 15-min     │─┘        │                                 │
└──────────────────┘          │                                 ▼
                              │                        ┌────────────────┐
                              │                        │  INDEX UPDATE  │
                              │                        │ S-GPR, ladder, │
                              │                        │ JUMP, phân vị  │
                              │                        └────────┬───────┘
                              │                                 ▼
                              │                        ┌────────────────┐
                              │                        │ MEASUREMENT    │──▶ Lớp 1 (realtime)
                              │                        │ CARD           │
                              │                        └────────┬───────┘
                              │                                 │ JUMP > ngưỡng
                              │                                 ▼
                              │            ┌───────────────┐  ┌────────────────┐
                              │            │  ANALOGUE     │  │ QUANTILE MODEL │
                              │            │  RETRIEVAL    │  │ phân phối theo │
                              │            │  (§6)         │  │ kênh + CI (§5) │
                              │            └───────┬───────┘  └────────┬───────┘
                              │                    └──────────┬────────┘
                              │                               ▼
                              │                     ┌──────────────────┐
                              │                     │ BRIEF COMPOSER   │──▶ Lớp 2 (định kỳ)
                              │                     │ LLM narrate,     │
                              │                     │ số từ payload    │
                              │                     │ + guard P1       │
                              ▼                     └────────┬─────────┘
                   ┌──────────────────┐                      ▼
                   │ chân A nightly   │          ┌───────────────────────┐
                   │ GPRD ingest t+1  │─────────▶│ gpr-api (FastAPI)     │
                   │ = hiệu chuẩn     │          │ Kafka → BeaverX agents│
                   │ + panel tháng    │          │ Web UI · track record │
                   └──────────────────┘          └───────────────────────┘
```

**Ngân sách độ trễ** (lớp 1, nguồn tier-1): p50 < 60s, p95 < 180s.

| Chặng | Ngân sách |
|---|---|
| Poll interval nguồn tier-1 | 15s |
| Dedup + cluster | < 2s |
| Encoder lọc | < 1s |
| LLM scoring | < 8s |
| Index + ladder + JUMP update | < 1s |
| Guard P1 + publish | < 2s |

Trượt tầng: nếu LLM timeout → xuất card **rút gọn** chỉ có ĐO LƯỜNG thô (không cần LLM). Sản phẩm không im lặng vì LLM chậm.

Lớp 2 không có ràng buộc độ trễ — chạy theo lịch.

---

## 4. THÀNH PHẦN — ĐỐI CHIẾU CODE HIỆN CÓ

| # | Thành phần | Trạng thái | Ghi chú |
|---|---|---|---|
| C1 | Collector chân B | ❌ | Nguồn tĩnh (archive) backfill; RSS/poll realtime |
| C2 | Dedup + event clustering | ❌ | `docs/09` điểm 4.12 |
| C3 | `scoring/statement_scorer.py` | 🔴 stub | Rubric + prompt đã thiết kế `00` §2.3–2.4. Đường găng |
| C4 | `indices/s_gpr.py` | 🔴 stub | Công thức `00` §2.5 |
| C5 | `econometrics/ladder.py` | 🔴 stub | V1 rule-based, ngưỡng version-hóa `00` §4.1 |
| C6 | `econometrics/analogue.py` | ❌ mới | §6 |
| C7 | Card/Brief composer + guard P1 | ❌ | |
| C8 | Serving: gpr-api + Kafka + UI | ❌ (G4) | |
| C9 | Feedback loop + eval harness | ❌ | §11 |
| C10 | `scoring/track_record.py` | ❌ mới | CRPS/Brier, lịch sử công khai (R2) |
| C11 | `econometrics/surprise.py` | 🔴 stub | Bất ngờ chính sách cửa sổ hẹp (§5.6) |
| C12 | `econometrics/panel_var.py` | 🔴 stub | Block-exogenous VAR (§5.5) |
| — | `local_projection`, `tier2`, `tier3`, `shocks` | ✅ | Cần sửa theo §5 |
| — | ingest chân A ×3, `dataset`, `data_files` | ✅ | Cần thêm §5.3 và cước vận tải |

---

## 5. SPEC CÔNG THỨC (→ `07_formulas_reference_v3.md`)

### 5.1. Baseline hiện tại (giữ để so sánh)

$$y_{t+h} - y_{t-1} = \alpha_h + \gamma_h s_t + \sum_{j=1}^{5}\phi_{h,j} y_{t-j} + \Gamma_h' \mathbf{c}_t + \varepsilon_{t+h}$$

Ba giả định ngầm mà bằng chứng đều bác: tác động **tỉ lệ với cỡ sốc**; **đồng nhất qua kênh**; nằm ở **trung bình có điều kiện**.

### 5.2. Số hạng đuôi

$$y_{t+h} - y_{t-1} = \alpha_h + \gamma_h s_t + \delta_h J_t + \sum_{j=1}^{p}\phi_{h,j} y_{t-j} + \Gamma_h' \mathbf{c}_t + \varepsilon_{t+h}$$

$$J_t = \max\!\left(0,\ s_t - q_{0.95}^{\text{rolling}}\right)$$

`JUMP` **đã có trong `shocks.py`** (D2 đã xong), chỉ chưa đưa vào ma trận thiết kế.

**Cơ sở:** Brignone–Gambetti–Ricci — cú sốc GPR chỉ leo thang đáng kể trên khoảng 4σ; sốc 4σ sâu hơn và dai hơn hẳn 4 lần sốc 1σ; sốc gắn với đe dọa được dự đoán trước thể hiện phi tuyến rõ rệt. ECB LGPT tái lập được.

**Kiểm định:** $H_0: \delta_h = 0$. Nếu $\delta_h$ có ý nghĩa trong khi $\gamma_h \approx 0$ → cơ chế chỉ tồn tại ở đuôi.

**Ngưỡng:** $q_{0.95}$ trước. Thử $q_{0.99}$ chỉ như robustness đã **đăng ký trước**, không dò.

### 5.3. Tách kênh

$$\gamma_h s_t \;\longrightarrow\; \sum_{k \in K} \gamma_h^{(k)} s_t^{(k)}, \qquad K = \{\text{energy},\ \text{trade},\ \text{financial},\ \text{military}\}$$

- **Giai đoạn 1 (ngay):** tách thô `GPRD_ACT` / `GPRD_THREAT` — đã có, không cần chân B.
- **Giai đoạn 2:** phân loại kênh từ LLM, taxonomy 4 kênh theo ECB LGPT.

**Kỳ vọng có hướng — để ĐỌC kết quả, KHÔNG dùng làm tiêu chí cổng** (`docs/09` §2.5 đã bỏ tiêu chí "đúng dấu literature" vì confirmation bias). ECB thấy sốc năng lượng đẩy cả lãi suất ngắn và dài hạn lên (chi phí đẩy), sốc thương mại làm lãi suất giảm (phía cầu); năng lượng chủ yếu qua kênh lạm phát và tài chính, thương mại chủ yếu lên hoạt động thực và tạo áp lực giảm phát.

Nếu ra $\gamma^{(energy)}_{\text{US10Y}} > 0 > \gamma^{(trade)}_{\text{US10Y}}$ thì $\gamma$ gộp $\approx 0$ của G2a được giải thích trọn vẹn: đang cộng hai cơ chế ngược dấu.

**Biến tầng 2 cần thêm — cước vận tải biển.** Việc đi vòng tránh Hormuz đang gây áp lực lên các điểm nghẽn thứ cấp gồm kênh Panama và **eo Malacca**, tạo rủi ro phân tán về địa lý nơi tắc nghẽn mạng lưới trở thành kênh chính gây gián đoạn thương mại. Malacca là cửa ngõ thương mại VN — kênh vật lý này **không nằm trong 4 biến Oil/DXY/VIX/US10Y**. Biến vẫn generic, nhưng nước xuất khẩu châu Á nhạy hơn hẳn nước phát triển.

### 5.4. Hồi quy phân vị — trục sản phẩm

$$Q_\tau\!\left(y_{t+h} - y_{t-1} \mid \Omega_t\right) = \alpha_{h,\tau} + \gamma_{h,\tau} s_t + \delta_{h,\tau} J_t + \sum_j \phi_{h,j,\tau} y_{t-j} + \Gamma_{h,\tau}'\mathbf{c}_t$$

$\tau \in \{0.10,\ 0.25,\ 0.50,\ 0.75,\ 0.90\}$ → khớp skewed-$t$ → mật độ có điều kiện (quy trình growth-at-risk, Adrian–Boyarchenko–Giannone).

**Vì sao mấu chốt:** $\gamma_{h,0.5} \approx 0$ **và** $\gamma_{h,0.10} < 0$ có ý nghĩa là hoàn toàn tương thích. Rủi ro địa chính trị không dịch chuyển kết quả kỳ vọng — nó **kéo dài đuôi trái**. Khớp Caldara–Iacoviello: GPR cao đi kèm xác suất thảm họa kinh tế cao hơn, tăng trưởng kỳ vọng thấp hơn, rủi ro đuôi dưới lớn hơn.

Nghĩa là: **kết quả G2a có thể không sai — chỉ đo sai đại lượng.** OLS đo trung bình; hiện tượng nằm ở phân vị dưới.

**Ràng buộc mẫu:** panel tháng 1985–2026 ≈ 490 quan sát. Tại $\tau=0.10$ còn ~49 điểm đuôi — đủ. **Không đi dưới $\tau=0.10$.** Ghi vào registry để sau không ai nới.

**Suy diễn:** block bootstrap cho CI (LP có phần dư tự tương quan theo $h$).

### 5.5. Tầng 3 — block exogeneity

$$\begin{bmatrix}\mathbf{X}_t\\ \mathbf{Z}_t\end{bmatrix} = \begin{bmatrix}A_{XX}(L) & \mathbf{0}\\ A_{ZX}(L) & A_{ZZ}(L)\end{bmatrix}\begin{bmatrix}\mathbf{X}_{t-1}\\ \mathbf{Z}_{t-1}\end{bmatrix} + \mathbf{u}_t, \qquad A_{XZ}(L) = \mathbf{0}\ \ \forall L$$

- $\mathbf{X}$ = khối ngoại: shock GPR, dầu, DXY, VIX, US10Y, cước vận tải
- $\mathbf{Z}$ = khối nội: $[r^c_t,\ p_t,\ g^{d}_t]$ — thị trường, chính sách, GPR nội địa

Khối $\mathbf{0}$ góc trên phải **chính là** "1 engine, n bộ params" viết bằng ngôn ngữ kinh tế lượng: biến nội địa không tác động lên biến toàn cầu, cả cùng kỳ lẫn có độ trễ. Đây là cơ sở lý thuyết cho `CLAUDE.md` #8 — hiện #8 là quyết định thiết kế chưa có biện minh hình thức.

**Ba hệ quả:**
1. Ước lượng tầng 1–2 **một lần là hợp lệ** với mọi nước nhỏ mở gắn vào sau.
2. Thêm nước **không phải re-estimate engine**, chỉ thêm file params. Engine là tài sản; mỗi nước là SKU chi phí biên ~0.
3. **Kiểm định được:** Granger $\mathbf{Z} \nrightarrow \mathbf{X}$. Không bác bỏ → có bằng chứng thống kê rằng kiến trúc engine+params hợp lệ cho nước đó.

**Lợi ích kỹ thuật:** áp đặt ngoại sinh cho phép đưa nhiều biến quốc tế hơn đồng thời giảm số tham số phải ước lượng, cải thiện chất lượng ước lượng.

**Ngoại sinh là tài sản nghiên cứu:** ECB/BoE không giả định được cú sốc GPR ngoại sinh với khu vực đồng euro — EA đủ lớn để có phản hồi. Với VN thì được. Tiền lệ đúng khu vực: Sato–Zhang–McAleer (2011) SVAR + block exogeneity cho Đông Á; Gossé (2013) SVAR block-exogeneity Bayesian; Cushman–Zha (1997) là gốc.

**Vòng lặp phản hồi phải nằm TRONG $\mathbf{Z}$.** Nếu chạy ngược lên tầng 2 thì sơ đồ nhận dạng sụp (Cholesky với GPR đặt đầu chỉ hợp lệ khi biến khác không tác động ngược cùng kỳ). Nó không sụp vì VN nhỏ.

**Không làm:** ước lượng tác động của VN lên vĩ mô toàn cầu. VN quá nhỏ; kết quả sẽ là nhiễu và không ai mua.

### 5.6. Khối phản hồi chính sách

$p_t$ nội sinh trong $\mathbf{Z}$: chính sách phản ứng theo thị trường, thị trường phản ứng theo chính sách.

**Nội sinh đồng thời:** OLS/LP thường cho hệ số lẫn lộn. **Nhận dạng:** bất ngờ chính sách trong cửa sổ hẹp quanh công bố (kiểu Gürkaynak–Sack–Swanson) — dùng phần *bất ngờ*, khi chỉ thông tin đó thay đổi. Yêu cầu `published_at` đến phút; **nguyên tắc #5 vốn viết cho actor-weighting, giờ là điều kiện bắt buộc cho khối này.**

**Rubric riêng bắt buộc.** Trục leo thang (`00` §2.3: −1 hòa giải … +1 hành động) **không dùng lại được**. Trục chính sách là nới lỏng ↔ thắt chặt, hoặc thích ứng ↔ đối đầu. Ép hai thứ vào một thang hỏng cả hai. Cần `rubric_version` riêng; nguồn: SBV, Bộ Tài chính, Bộ Công Thương, Chính phủ, VCCI.

**Lợi ích kép:** corpus tiếng Việt phục vụ **hai** mục đích — $g^d_t$ (λ, domestic-direct) và hàm phản ứng chính sách. Đây là lý do V-phase được kéo lên sớm (§10).

### 5.7. Chặt cụt biên độ giá (chỉ VN)

$$r^{obs}_t = \max\!\left(-L,\ \min(L,\ r^*_t)\right), \qquad L = 7\%$$

`vn.yaml` đã có `price_limit_pct: 7.0`, `settlement: T+2.5`.

Với sốc lớn, OLS trên $r^{obs}$ lệch về 0 **một cách cơ học** — và đúng ở vùng đuôi, nơi §5.2 nói tác động thật xuất hiện. **Hai cơ chế cùng đẩy ước lượng tuyến tính về 0.** Đây là lập luận VN-specific không paper toàn cầu nào viết.

**Xử lý:** lợi suất tích lũy $k$ ngày, $k \geq 3$, để phần bị cắt tràn ra hết. (Tobit là lựa chọn thay thế, phức tạp hơn, không khuyến nghị trước.)

### 5.8. Replication harness (chạy trước mọi thứ khác)

Chạy lại đúng specification headline của Caldara–Iacoviello (tần suất, mẫu, biến, phương pháp như paper) **trên chính pipeline của bạn**.

- Tái lập được → pipeline đúng; kết quả null là phát hiện thật.
- Không tái lập được → **có bug**; mọi kết luận G2a vô nghĩa.

Đây là unit test cấp hệ thống. Nếu pipeline sai thì analogue retrieval (dùng chung `data_files`, chung transform) cũng sai theo.

---

## 6. ANALOGUE RETRIEVAL

**Xuất xứ — đọc kỹ:** thiết kế này là suy luận từ case-based reasoning, **không có tiền lệ trong literature GPR**. Khác mức độ chắc chắn so với §5.2/§5.3/§5.5 vốn đều có nguồn. Có tiền lệ *phương pháp* gần: IMF GFSR định nghĩa sự kiện GPR lớn là khi chỉ số vượt 2 độ lệch chuẩn, rồi đo biến động tích lũy của chỉ số chứng khoán tại mốc 1 ngày, 1 tuần, 1 tháng, 3, 6, 12 tháng — event-study phân phối, cùng họ.

**Giá trị:** vẫn hoạt động **kể cả khi tầng 2/3 cho kết quả null**. Claim ceiling = `association`, không cần identification, không có bậc tự do để overfit.

**Episode descriptor:**
```
z(GPRD_level), z(GPRD_innovation), JUMP,
GPRD_ACT/THREAT ratio, channel one-hot,
ladder_state(pair), days_in_state,
VIX percentile, DXY 20d trend, oil 20d trend,
regime flag (pre-2008 / 2008-2015 / post-2015)
```

**Truy hồi:** k-NN (k=5..20, cosine trên descriptor chuẩn hóa), **loại trừ cửa sổ ±30 ngày quanh $t$** (chống rò rỉ trùng episode). Mỗi láng giềng → đường vĩ mô thực tế $h$ tháng sau → trung vị + IQR + tỉ lệ cùng dấu.

**Ràng buộc bắt buộc:**
- $n < 5$ → không xuất phần bối cảnh (P3)
- IQR đổi dấu → ghi "phân tán, không kết luận"
- **Luôn liệt kê được danh sách episode** — người dùng bấm xem "6 lần đó là những lần nào". Tính kiểm chứng được là điểm bán hàng chính; đây là nơi chân A (1985+) tạo giá trị đối thủ không có
- Chỉ dùng dữ liệu `available_at ≤ t` (`CLAUDE.md` #11), kể cả trong retrieval

**Hybrid re-rank (tùy chọn, cũng chưa có nguồn):** k-NN số bắt "trạng thái thị trường giống nhau" nhưng không bắt "bản chất sự kiện giống nhau". k-NN lấy 30 ứng viên → LLM re-rank xuống 8 kèm lý do. **Ràng buộc cứng: LLM chỉ chọn từ danh sách ứng viên, không bao giờ sinh episode.** Bịa episode là biến thể nguy hiểm nhất của bịa số.

**Mẫu mỏng cho VN:** sự kiện tác động mạnh riêng VN thì hiếm → thường chạm $n<5$. Xử lý: **kho episode lấy từ global, tham số truyền dẫn lấy từ VN** — đúng cấu trúc engine+params. Nhưng chỉ chạy được sau khi tầng 3 có hệ số.

---

## 7. THAY ĐỔI CODE THEO MODULE

| Module | Trạng thái | Việc |
|---|---|---|
| `econometrics/local_projection.py` | ✅ | Thêm cột $J_t$. Thêm `quantile_lp()` dùng `statsmodels.QuantReg`. Block bootstrap CI |
| `econometrics/tier2_global_macro.py` | ✅ | Vòng lặp thêm chiều $\tau$ và chiều kênh $k$. Horizon tháng cho nhánh macro |
| `econometrics/shocks.py` | ✅ (D2) | Không đổi — `JUMP` đã có |
| `econometrics/panel_var.py` | 🔴 stub | Block-exogenous VAR (§5.5) + Granger test khối |
| `econometrics/tier3_country.py` | ✅ | Lợi suất tích lũy $k$ ngày (§5.7). Chỗ cho $p_t$ |
| `econometrics/surprise.py` | 🔴 stub | Bất ngờ chính sách cửa sổ hẹp (§5.6) |
| `econometrics/ladder.py` | 🔴 stub | V1 rule-based |
| `econometrics/analogue.py` | ❌ mới | §6 |
| `data/dataset.py` | ✅ | Thêm cước vận tải. Bật nhánh monthly macro outcomes (cần viết `build_monthly_panel()` — CHƯA có, xem E3) |
| `scoring/statement_scorer.py` | 🔴 stub | Pipeline 2 tầng: encoder lọc (ngưỡng ~0.6) → LLM chấm. `temperature=0.1`, JSON nghiêm ngặt, zero-shot. Thêm trường `channel` |
| `scoring/policy_scorer.py` | ❌ mới | Rubric riêng (§5.6) |
| `scoring/track_record.py` | ❌ mới | CRPS/Brier, lịch sử công khai (R2) |
| `indices/s_gpr.py` | 🔴 stub | Công thức `00` §2.5 |

**Pipeline 2 tầng — cơ sở:** ECB LGPT dùng encoder tinh chỉnh lọc trước (giữ bài có xác suất trên 0.6), rồi mới đưa GPT-4o trích xuất, vì dùng riêng mô hình lớn tuy giảm false negative nhưng chi phí tính toán cực cao và tốc độ trở thành nút thắt. Họ đặt nhiệt độ 0.1 để giảm phương sai và tăng khả năng tái lập, và ép JSON nghiêm ngặt vì vừa cho output máy đọc được vừa giảm mơ hồ so với trả lời tự do.

**Versioning khi dùng LLM nhiều hơn:** `CLAUDE.md` #4 hiện yêu cầu `model_version` + `rubric_version`. **Thêm:** `prompt_version`, `temperature` cố định, cache output theo hash nội dung. Không có cái này thì `data_version` trong report mất ý nghĩa vì một nửa pipeline không xác định.

**LLM tuyệt đối không được làm:** sinh số; chấm gate GO/NO-GO; chọn specification. Cái thứ ba tinh vi nhất — để LLM "chọn spec tốt nhất" là data snooping qua cửa mới, đúng thứ `docs/10` §5 cảnh báo. Spec do BIC trên development window quyết, đã khóa trong registry.

---

## 8. GIẢ THUYẾT ĐĂNG KÝ + CỔNG

### 8.1. Đăng ký trước khi chạy (registry)

| id | Nội dung | Bước |
|---|---|---|
| KĐ-N1 | $\delta_h \neq 0$ với $J_t = \max(0, s_t - q_{0.95})$; $\gamma_h$ có thể $= 0$ | E2 |
| KĐ-N2 | Tác động lên vĩ mô thực tần suất tháng, $h = 0..24$ tháng | E3 |
| KĐ-N3 | $\gamma_{h,0.10} < 0$ có ý nghĩa trong khi $\gamma_{h,0.5} \approx 0$ | E4 |
| KĐ-N4 | $\gamma^{(energy)}$ và $\gamma^{(trade)}$ khác dấu ở biến lãi suất | E3 |
| KĐ-N5 | Block exogeneity không bị bác bỏ với VN (Granger $\mathbf{Z} \nrightarrow \mathbf{X}$) | P2 |
| KĐ8 | S-GPR có dẫn trước GPR không (đã có trong docs) | P1 |

`p = 5/5/2` **đã khóa — không đụng.** Các KĐ trên là id mới, không sửa KĐ cũ.

### 8.2. Cổng

| Cổng | Điều kiện |
|---|---|
| **G-E0** | Replication harness (§5.8): tái lập được kết quả đã publish, **hoặc** tìm ra bug |
| **G-E1** | Chẩn đoán E1 xong, đã chọn nhánh sửa chữa, ghi vào registry |
| **G-E2** | KĐ-N1 có kết luận. NO-GO không chặn — sang E3 |
| **G-E3** | KĐ-N2 pass → có deliverable chính. Fail → xem lại toàn bộ giả thuyết tầng 2 |
| **G-E4** | Phân phối ước lượng được, CI hợp lý, CRPS baseline có |
| **G-B1** | Human audit chân B: Krippendorff α ≥ 0.6, **2 người chấm độc lập**. α < 0.6 → gộp 7 bậc thành 5 (`00` §8) |
| **G-B2** | Guard P1 zero-fail trên 200 card |
| **G-P1** | Block exogeneity không bị bác bỏ cho nước định thêm |
| **G-L** | 4 tuần chạy liên tục, ≥70% card đánh dấu hữu ích, 0 sự cố số bịa |

**Cổng mới cần thêm vào `docs/05`:** G-P1 (block exogeneity là điều kiện để một nước dùng kiến trúc engine+params). Hiện chưa có.

---

## 9. VẤN ĐỀ GOVERNANCE PHẢI QUYẾT TRƯỚC KHI CHẠM HOLDOUT

**Sự việc:** final holdout là 2026-H1. Ngày 28/02/2026 Mỹ và Israel không kích Iran; Iran đáp trả nhắm vào tàu qua eo Hormuz; bảo hiểm không còn hoặc quá đắt, eo biển đóng cửa trên thực tế. IEA gọi đây là gián đoạn nguồn cung lớn nhất trong lịch sử thị trường dầu, dòng chảy từ ~20 mb/d xuống mức nhỏ giọt. Brent +65% trong tháng 3 — mức tăng theo tháng cao nhất từng ghi nhận.

**Hai vấn đề ngược chiều:**
1. Final holdout không còn là mẫu out-of-sample hợp lệ — nó là chế độ cực đoan đơn lẻ. Chạm một lần, kết quả bị chi phối bởi đúng một episode.
2. Nhưng đây **chính là** cú sốc >4σ mà KĐ-N1 cần. Dữ liệu chứng minh cơ chế cốt lõi đang bị khóa trong két.

| | Cách | Đánh đổi |
|---|---|---|
| A | Giữ chính sách, chạm 1 lần, báo cáo kèm cảnh báo chế độ đơn lẻ | Trung thực nhất với G0, kết quả khó diễn giải |
| B | Dời holdout sang 2026-H2+, đưa 2026-H1 vào pseudo-OOS | Thêm episode đuôi để học, nhưng phải chờ dữ liệu và ghi rõ lý do dời (không thì giống dò) |
| C | Tách holdout: 2026-H1 (chế độ chiến sự) + 2026-H2+ (bình thường hóa), báo cáo riêng | Giữ được cả hai, phức tạp hơn |

Nghiêng về **C**. Quyết định của bạn, và **phải ghi vào `g0_governance.md` trước khi chạm**, kèm ngày và lý do — ghi sau thì không phân biệt được với dò dữ liệu.

---

## 10. LỘ TRÌNH

Hai track song song. **Track E (econometrics) có thứ tự cứng — không làm song song trong nội bộ track.**

### Track E — Kinh tế lượng

**E0 — Replication harness** (§5.8). ~2 ngày. Chặn mọi thứ.

**E1 — Chẩn đoán spec innovation.** Nửa ngày. **Không cần đăng ký giả thuyết, không chạm holdout.**

Vẽ `LEVEL`, `PERSISTENT`, `INNOVATION`, `JUMP` của GPRD, 2026-02-01 → 2026-06-30, đánh dấu 28/02.

**Bối cảnh:** cú sốc dầu địa chính trị lớn nhất lịch sử đã xảy ra **bên trong mẫu ước lượng** (panel G2a tới 2026-07-02). Mô hình hiện tại cho γ(oil) ≈ 0.0005 tại h=0, p=0.56. **Một mô hình không phát hiện được cú sốc đó, khi nó nằm ngay trong mẫu, thì vấn đề ở specification chứ không ở thế giới.**

| Quan sát | Kết luận | Hành động |
|---|---|---|
| `JUMP` bật 28/02, `INNOVATION` không | AR(5) khử mất tín hiệu | **Bỏ kết luận G2a.** Đăng ký giả thuyết mới với `JUMP` làm shock chính. Giải thích luôn bất thường γ(VIX) ở **horizon dài** (h≈29, γ=−0.60, p=0.004 — VIX GIẢM sau shock, phản trực giác; γ(VIX) tại h=0 KHÔNG có ý nghĩa, p=0.78) |
| Cả hai bật | Spec shock ổn | Vấn đề ở tuyến tính / biến đích / horizon → E2–E4 |
| `LEVEL` cao kéo dài, cả hai phẳng sau vài ngày | Sốc dai dẳng, innovation chỉ bắt ngày đầu | Cần cả `LEVEL` lẫn `JUMP` trong design matrix |

**E2 — Số hạng đuôi.** 1 ngày. KĐ-N1.
**E3 — Chuyển tần suất tháng + vĩ mô thực + tách kênh thô.** 2–3 ngày. KĐ-N2, KĐ-N4. **`build_monthly_panel()` CHƯA có** — D2 cố ý chỉ xây track daily (`build_tier2_panel`, tôn trọng #10), phần monthly hoãn sang đây. E3 phải viết mới, không phải "chạy nhánh có sẵn".
**E4 — Hồi quy phân vị.** 3–5 ngày. KĐ-N3. Đây là bước biến engine thành sản phẩm bán được.

### Track P — Sản phẩm

**P0 — Đóng vòng lặp.** ~3 tuần. Done = một phát ngôn thật sinh ra Measurement Card đúng trong 3 phút, trên máy bạn.
- C1 tối giản: **2 nguồn** — Trump (Truth Social) + MOFA Trung Quốc. (Chọn trục Mỹ–Trung vì đó là kênh thương mại, kênh chi phối VN, và ECB xác nhận trade shock có cơ chế riêng. Nếu bạn ưu tiên trục lãi suất thì đổi MOFA → Fed RSS.)
- C3 scorer: prompt `00` §2.4, model rẻ trước (GPT-4o-mini), JSON strict, retry + validate. Thêm trường `channel`.
- Bảng `statements` + `statement_scores` (schema `00` §6).
- C7 tối giản: card **template thuần, chưa LLM** — chỉ ĐO LƯỜNG + TRẠNG THÁI thô.
- Xuất ra terminal/Slack webhook. Chưa cần API, chưa cần UI.

⛔ **Cổng P0:** 20 phát ngôn thật chạy qua pipeline không lỗi; bạn đọc 20 điểm và thấy ≥16 hợp lý.

**P1 — Có chỉ số & bối cảnh.** ~5 tuần.
- Backfill chân B: Trump archive 2015+, Fed/BIS speeches, WH statements. Ước $100–250 (`00` §2.6). Cần cho analogue có mẫu.
- **Human audit 500 mẫu, 2 người chấm** (`00` §2.4) — *không bỏ qua*. Điều kiện để claim `measurement`.
- C4 `s_gpr.py` + C5 `ladder.py` (V1 rule-based).
- C2 dedup/clustering.
- **C6 analogue retrieval** — kho episode từ chân A 1985+.
- C7 đầy đủ: Brief composer + **guard P1** (test tự động khớp số).
- C10 track record harness (R2) — bắt đầu chấm từ bản Brief đầu tiên.
- Trigger rules: $J_t$ vượt ngưỡng, chuyển bậc ladder, S-GPR vượt phân vị 90, im lặng kéo dài ở bậc cao (P4).

⛔ **Cổng P1:** G-B1, G-B2, KĐ8 chạy được (pass/fail đều lưu, không chặn).

**P2 — Launch nội bộ.** ~4 tuần.
- C8: `gpr-api` FastAPI + Kafka topic → BeaverX agents; UI web tối giản (feed + trang episode detail + trang track record).
- Mở rộng nguồn: WH, Fed, USTR/Commerce (B5–B7) + GDELT daily (chân C, cross-check).
- **Kéo V-phase corpus tiếng Việt lên đây** — thay đổi lớn nhất so với `docs/00` §7, nơi V-phase nằm cuối lộ trình. Lý do: literature nói chỉ số từ báo địa phương khác chỉ số từ báo nước ngoài, và khác biệt đó có thể quyết định việc tác động có ý nghĩa thống kê hay không (Bondarenko et al. 2024; Alonso-Alvarez et al. 2025 xây chỉ số song phương 34 nước, 15 ngôn ngữ, thấy độ chính xác cải thiện rõ với nguồn địa phương). `GPRC_VNM` hiện tại là "báo Mỹ nghĩ gì về VN". Cộng với §5.6: corpus này còn nuôi luôn khối phản ứng chính sách.
- C9: feedback loop + eval harness §11.
- C11 + C12: khối phản hồi chính sách + block-exogenous VAR.
- Chuyển scorer sang Qwen3-14B/vLLM nếu pass (chi phí + độ trễ).
- Alert routing + chống mệt mỏi cảnh báo (rate limit theo cặp, gộp cluster).

⛔ **Cổng P2:** G-L, G-P1.

**P3 — Thương mại hóa.** Global Macro Impact (chính) + Country Transmission (VN trước, rồi TH/ID/PH — cùng là nền kinh tế nhỏ mở, block exogeneity áp dụng y hệt).

### Phụ thuộc chéo

- E1 chặn E2–E4 **và** chặn tầng "phân phối" của Brief (P1 §2.3).
- E4 xong → Brief có tầng model. Chưa xong → Brief chỉ có analogue. **Sản phẩm vẫn launch được.**
- P1 (chân B có điểm) → E3 tách kênh đúng (thay vì tách thô ACT/THREAT).

---

## 11. ĐÁNH GIÁ

Sai lầm cần tránh: đo sản phẩm bằng metric của Mục tiêu B. Launch là Mục tiêu A, có bộ metric riêng.

| Tầng | Metric | Ngưỡng |
|---|---|---|
| Đo lường (scorer) | Krippendorff α với human gold set; F1 trên `commitment`, `channel` | α ≥ 0.6; F1 ≥ 0.75 |
| Phát hiện | Recall trên gold set ~50 sự kiện lớn 2018–2026; độ trễ p50/p95 | recall ≥ 0.9; p50 < 60s |
| Chất lượng card/brief | % đánh dấu hữu ích; **tỉ lệ số bịa (phải = 0)** | ≥ 70%; 0 |
| **Phân phối** | **CRPS vs baseline vô điều kiện; Brier cho sự kiện ngưỡng; PIT histogram** | **CRPS < baseline; PIT phẳng** |
| Im lặng | False-negative: sự kiện lớn mà hệ không ra card | ≤ 10% |

**Gold set dựng ngay ở P0**, không để sau — `docs/09` điểm 4.9: correlation không đủ để validate LLM.

---

## 12. RỦI RO

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| **LLM bịa số** | 🔴 | Guard P1 chặn cứng (không cảnh báo — chặn). Card rút gọn không LLM làm fallback |
| **Overclaim → hệ quả pháp lý** (BeaverX là tư vấn đầu tư VN) | 🔴 | P2/P5/P7. Nhãn claim hiện trên card. Rà soát pháp lý trước P2. Bỏ hẳn tín hiệu giao dịch (§13) |
| **E1 cho kết quả "spec hỏng"** | 🟡 | Đã lường: nhánh sửa chữa có sẵn trong bảng E1. Chi phí là thời gian, không phải bế tắc |
| Scraping gãy (Truth Social, MOFA) | 🟡 | Nguồn tĩnh (archive, BIS, Fed RSS) làm xương sống; scrape là phụ. Alert khi 1 nguồn im bất thường |
| Alert fatigue | 🟡 | Rate limit theo cặp; gộp cluster; ngưỡng điều chỉnh được |
| Mẫu analogue mỏng cho cặp hiếm / cho VN | 🟡 | Nới descriptor (bỏ ràng buộc cặp, giữ channel); $n<5$ im lặng; kho global + params VN |
| Chân B backfill lệch nguồn | 🟡 | Chuẩn hóa theo nhịp đăng từng nguồn (`00` §2.5); `index_quality` + cờ coverage |
| Track E kéo track P chậm | 🟡 | Hai track tách hẳn. Launch không chờ cổng econometrics nào ngoài E1 |
| **Kịch bản xấu nhất: E2–E4 đều null** | 🟡 | Sản phẩm rút về đo lường + analogue toàn cầu. Vẫn bán được, nhạt hơn. **Chấp nhận trước khi bắt đầu, không phát hiện ở tháng thứ tư** |

---

## 13. QUYẾT ĐỊNH CẦN CHỐT

1. **Vấn đề holdout §9 — A, B hay C?** Phải ghi vào `g0_governance.md` trước khi chạm.

2. **Nới nguyên tắc #6 của `CLAUDE.md`?** Kế hoạch này đưa chân B vào production trước khi chứng minh incremental IC. Đề xuất: **nới có điều kiện** — chân B vào **sản phẩm đo lường** ngay, nhưng vẫn phải qua cổng IC trước khi vào bất kỳ output định lượng nào. Nếu đồng ý, **sửa #6 cho tường minh** — repo này sống bằng kỷ luật đó; nới ngầm một lần là mở cửa cho nới lần sau.

3. **Bỏ hẳn tín hiệu giao dịch khỏi lộ trình?** Đề xuất: bỏ. Không thuộc định vị nhà mô hình, và gỡ luôn rủi ro pháp lý. Nhà mô hình bán ước lượng và bất định; ai muốn giao dịch tự dùng.

4. **2 nguồn đầu: Trump + MOFA CN, hay Trump + Fed?** Xem P0.

5. **Human audit 500 mẫu — ai là người chấm thứ hai?** Ràng buộc nhân sự thật, chặn G-B1. Giải trước P1.

6. **Card rút gọn không LLM có đủ dùng không?** Nếu có, P0 rút xuống ~2 tuần và bỏ được một lớp rủi ro.

---

## 14. VIỆC TUẦN NÀY

Bốn việc, độc lập với 6 quyết định trên:

- [ ] **E1** — biểu đồ `LEVEL/PERSISTENT/INNOVATION/JUMP` quanh 2026-02-28. Nửa ngày. Không cần cổng, không chạm holdout. **Kết quả quyết định E2–E4 chạy trên shock nào.**
- [ ] Chốt Human review G2a đang treo (`docs/reports/G2a_innovation_*.md`). Kết quả nào cũng không chặn E1, nhưng phải đóng để track research đi tiếp.
- [ ] Dựng **gold set 50 sự kiện lớn 2018–2026** (tay, một buổi). Dùng cho metric §11 và làm test cho analogue.
- [ ] Xác minh truy cập 2 nguồn đã chọn: rate limit, cấu trúc, có `published_at` đến phút không (`CLAUDE.md` #5).