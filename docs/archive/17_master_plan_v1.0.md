> ⛔ **BẢN v1.0 — ĐÃ ĐƯỢC THAY THẾ BỞI `docs/17_master_plan.md` (v1.1, 2026-08-08).**
> Giữ lại để tra lịch sử quyết định. **Không dùng làm căn cứ thi công**: bản này có 6 sai lệch về dữ liệu và 6 mâu thuẫn logic đã kiểm chứng trên file/code thật — liệt kê đầy đủ ở phụ lục của `docs/17_master_plan.md`.
> Tên file gốc trên main (`1ef98a8`) gõ nhầm; tiêu đề dưới đây ghi số cũ, số thật của doc này là **17**.

# 10 — MASTER PLAN (BẢN CHỐT)

**Phiên bản:** 1.0 — 2026-08-03. **Tự chứa.**
**Thay thế hẳn:** `11_product_plan.md`, `13_e1c_and_grid_plan.md`, `14_product_completion_plan.md`, `15_global_pipeline.md`, `16_ai_gpr_supplement.md`. Năm doc đó chuyển sang `docs/archive/`, chỉ giữ để tra lịch sử quyết định.
**Vẫn hiệu lực, không gộp vào đây:** `CLAUDE.md` (nguyên tắc), `g0_governance.md` (holdout, chữ ký), `12_specification_curve_protocol.md` (giao thức SCA — nay là refinement), `00_engine_design.md` (rubric chân B, schema DB).

---

## 1. SẢN PHẨM

**GPR Live** — nhận tin tức/phát ngôn địa chính trị, trả nhận định ảnh hưởng vĩ mô.

| Lớp | Nhịp | Claim tối đa | Nội dung |
|---|---|---|---|
| **Đo lường** | realtime | `measurement` | Sự kiện, actor, cường độ, kênh, vai trò nước, phân vị lịch sử. **Không dự báo** |
| **Nhận định** | tháng + bản bất thường khi sốc đuôi | `predictive, chưa xác nhận holdout` | Phân phối vĩ mô có điều kiện theo kênh + khoảng + episode lịch sử kiểm chứng được |

**Deliverable:** Global Macro Impact (chính, generic) · Country Transmission (VN trước).

**Định vị:** nhà mô hình định lượng. Khác S&P/ECB ở chỗ có sai số, tái lập được, có track record công khai. Khác AI-GPR ở chỗ có sản phẩm, có phát ngôn sơ cấp, có VN.

---

## 2. NGUYÊN TẮC BẤT BIẾN

1. **LLM đo và diễn đạt. Công thức truyền dẫn.** LLM không sinh số, không chấm gate, không chọn spec.
2. **Guard P1** — mọi số trong output khớp một trường payload, chặn cứng. Áp cho cả report nghiên cứu lẫn sản phẩm. *(Đã có tiền lệ lỗi: "1.8×" trong khi số tính được là 2.77×.)*
3. **Không claim vượt mức nhận dạng.** "Trong N đợt tương tự, X diễn biến thế này" — không bao giờ "sẽ".
4. **Không có tham số ước lượng thì không nói độ lớn.** Nói kênh và hướng, ghi rõ chưa ước lượng.
5. **Im lặng là hợp lệ.** n<5 episode, IQR đổi dấu, dữ liệu thiếu → ghi "không kết luận được".
6. **Không tự chế công cụ thống kê.** `arch` (bootstrap, SPA, StepM), `statsmodels` (QuantReg), hoặc không gì cả.
7. **Ghim vintage mọi nguồn.** Trang AI-GPR cập nhật định kỳ, GPR gốc có hiệu chỉnh hồi tố. `data_version` phủ vintage từng chuỗi.
8. **Không tín hiệu giao dịch.** Ngoài định vị, và gỡ rủi ro pháp lý tư vấn đầu tư VN.

---

## 3. TẦNG DỮ LIỆU — INGEST, KHÔNG BUILD

| Nguồn | Nhịp | Vai trò |
|---|---|---|
| **AI-GPR** headline | daily | shock chính |
| **AI-GPR threats/acts** | daily | hai cơ chế truyền dẫn riêng |
| **AI-GPR Oil × 13 vùng** | daily | kênh năng lượng; có `Southeast Asia` |
| **AI-GPR country × 200** | daily | VN qua vai `spillover` |
| **AI-GPR bilateral × 1.200 cặp** | daily | phơi nhiễm theo cặp |
| **GPR gốc** (C-I) | daily + monthly | proxy thứ hai cho hiệu chỉnh sai số đo |
| EPU, WUI | monthly | battery control |
| Oil/DXY/VIX/US10Y/freight | daily + monthly | biến tầng 2 (đã có) |
| Real macro (IP, CPI, kỳ vọng lạm phát) | monthly | outcome tầng 2 (đã có) |
| VNINDEX | daily | **chưa có** — blocker duy nhất của tier3 VN |

**Hiệu chỉnh sai số đo (mới):** AI-GPR và GPR gốc tương quan chỉ **0.69** dù chấm cùng ba tờ báo — chênh lệch là sai số phân loại, không phải khái niệm khác nhau. Sai số đo làm hệ số **lệch về 0** kiểu errors-in-variables. Dùng chỉ số này làm **công cụ (IV)** cho chỉ số kia, hoặc trích nhân tố chung, để khử attenuation.
*Giới hạn phải ghi:* cả hai dựa trên báo chí Mỹ → chia sẻ một phần sai số (sự chú ý của tòa soạn). IV không khử được phần chung. Cần kiểm định over-identification.

---

## 4. TẦNG CÔNG THỨC

### 4.1. Phân rã kép — spec chính

$$y_{t+h} - y_{t-1} = \alpha_h + \beta_h^{P}\,\widehat{\Delta G}_t + \beta_h^{S}\,\hat u_t + \sum_j \phi_{h,j} y_{t-j} + \Gamma_h'\mathbf{c}_t + \varepsilon_{t+h}$$

$\widehat{\Delta G}_t$ = fitted từ AR(p), $\hat u_t$ = residual. **Đưa cả hai vào cùng lúc, không chọn giữa các thước đo.**

Bằng chứng: thành phần dai dẳng tác động **hơn gấp đôi** thành phần bất ngờ (−0.271 vs −0.119), cả hai có ý nghĩa. `INNOVATION` sẵn có chính là $\hat u_t$ — chỉ cần thêm cột fitted.

**Điều này thay thế toàn bộ tranh luận LEVEL / INNOVATION / LEVEL+JUMP** (g0 §7.1). Ba thước đo cũ xuống robustness.

**Tương tác threat/act:** threat truyền qua phần dai dẳng; act chỉ khi bất ngờ. Spec đầy đủ 4 regressor.

### 4.2. Tách kênh

Sốc năng lượng đẩy lãi suất **lên** (chi phí đẩy); sốc thương mại kéo **xuống** (phía cầu). Gộp kênh = cộng hai cơ chế ngược dấu → triệt tiêu. Dùng Oil GPR × vùng + threats/acts thay cho tách thô.

### 4.3. Số hạng đuôi + quantile

$J_t = \max(0, z_t - q^{roll}_{0.95})$ — tác động phi tuyến, chỉ leo thang đáng kể trên ~4σ.

$Q_\tau(\cdot)$, $\tau \in \{.10,.25,.50,.75,.90\}$, **không dưới 0.10**. Điểm cốt lõi: $\beta_{0.5}\approx 0$ **và** $\beta_{0.10}<0$ là tương thích — rủi ro làm **dày đuôi trái**, không dịch mức trung tâm.

**Hiệu chuẩn lại trên AI-GPR:** chuỗi này mượt hơn (sd 48.5 vs 60.6), dai hơn (autocorr 0.73 vs 0.62), đuôi phải mỏng hơn, không có ngày bằng 0. Ngưỡng q95/q99 và toàn bộ thiết kế trigger phải chạy lại phân vị.

### 4.4. Suy diễn

LP lag-augmented + SE White (không HAC, không block bootstrap cho phần dư). Dải **sup-t** cho họ horizon — CI theo từng điểm trên 25–31 horizon là vô nghĩa. Holm trong họ outcome pre-registered {asset_price · real_macro · physical}.

### 4.5. Tầng 3 — block exogeneity

$$A_{XZ}(L) = \mathbf{0}\ \forall L$$

$\mathbf{X}$ = khối ngoại (shock, oil, DXY, VIX, US10Y, freight); $\mathbf{Z}$ = khối nội $[r^c_t, p_t, g^d_t]$. Đây **là** "1 engine, n bộ params" viết bằng kinh tế lượng. Kiểm định được bằng Granger $\mathbf{Z}\nrightarrow\mathbf{X}$ — cổng bắt buộc trước khi thêm nước.

### 4.6. VN

- Vai `spillover` gần như luôn luôn → dùng country/bilateral index, **không cần corpus tiếng Việt cho v0**
- Kênh: năng lượng · thương mại (Mỹ–Trung, hai chiều rủi ro/cơ hội) · **vận tải/Malacca** · tỷ giá
- **Biên độ 7%** chặt cụt cơ học ở vùng đuôi → dùng lợi suất tích lũy $k\geq3$ ngày, không dùng một phiên
- Khối chính sách: nhận dạng kiểu Aruoba–Drechsel (NLP trên văn bản → dự đoán có điều kiện → phần dư), vì VN không có phái sinh lãi suất để đo surprise. Rubric **riêng** (nới lỏng↔thắt chặt), không dùng lại thang leo thang

---

## 5. TẦNG LLM

**Chỉ hai việc:** chấm điểm theo rubric, viết narrative từ payload.

Hai chỉ số **tách bạch**, không trộn:

| | Tầng A — replication | Tầng B — của mình |
|---|---|---|
| Nguồn | tin báo chí | phát ngôn sơ cấp |
| Thang | 0–1 đơn cực, prompt nguyên văn Appendix A.6 | ±1.0 lưỡng cực |
| Trường | threat/act, oil+vùng, country+event_type | + commitment, specificity, actor_weight |
| Dùng để | so được với chuỗi công bố | đo thứ AI-GPR không đo |

Cấu hình: temperature 0, zero-shot, JSON structured, cắt 2.000 ký tự (tầng 1) / 3.000 (tầng 2). Mọi subindex dùng **chung mẫu số $A_t$**.

**Versioning:** `model_version` + `prompt_version` + `rubric_version` + cache theo hash. Chuỗi vào track record dùng **model local pin cứng** — Llama 3.1 8B tương quan 0.91 với GPT-4o mini, đủ dùng và không bị deprecate.

**Hiệu chuẩn đã biết (từ audit của paper):** model **nén đỉnh thang**, gần như không chấm trên 0.8 → điểm cao là hiểu thấp so với thực tế. Model **chấm cao ở đáy** → hay nhầm bất ổn nội địa và tranh chấp thương mại thành GPR.

---

## 6. LỘ TRÌNH

### Phase 1 — "Công thức nói gì?" (~2–3 tuần, bắt đầu ngay)

- [ ] `load_ai_gpr()` + 5 subindices, ghim vintage
- [ ] Hiệu chuẩn lại phân vị/JUMP trên AI-GPR (§4.3)
- [ ] **1a**: tier2 tháng, spec phân rã kép (§4.1), threats/acts, Oil×vùng, quantile, sup-t, h=0..24. Chạy **ba bản**: GPR gốc · AI-GPR · IV/factor → đo attenuation thật. Kèm battery (EPU/WUI/AI-GPR làm control)
- [ ] **1b**: cascade tier3 end-to-end, nước pilot **Ba Lan hoặc Chile** (ngoài lộ trình bán). Nhãn PLUMBING — mục tiêu là ba tầng ghép được, Shapley tổng 100%
- [ ] Registry: spec phân rã kép làm ô chính; ba thước đo cũ → robustness; thêm `vn_market_series_missing`

**⛔ Cổng:** bảng γ tồn tại · cascade chạy hết · độ lớn effect thật được ghi (đầu vào cho mọi câu hỏi power sau)

### Phase 2 — Chân B (~4–5 tuần)

- [ ] Collector 2 nguồn + scorer tầng B + bảng DB + card template thuần
- [ ] Backfill + human audit 500 mẫu × 2 người → α ≥ 0.6
- [ ] `s_gpr.py` + `ladder.py` V1 + trigger rules
- [ ] Cổng contamination **chỉ cho `commitment`** — paper đã kiểm và bác bỏ lo ngại cho tầng chấm cường độ (tương quan 0.95 với prompt neo ngày), nhưng dự đoán "đe dọa có thành hiện thực không" là chuyện khác

**⛔ Cổng:** card thật < 3 phút · α ≥ 0.6

### Phase 3 — Sản phẩm (~4 tuần)

- [ ] `analogue.py` (k-NN, n<5 im lặng, luôn liệt kê episode)
- [ ] Composer + guard P1 → Model Brief đầu tiên
- [ ] Serving: FastAPI + Kafka → BeaverX agents
- [ ] Track record (CRPS/Brier, công khai)
- [ ] VNINDEX → tier3 VN → **Country Transmission VN v0**

**⛔ Cổng:** brief đủ 4 tầng claim · 0 số bịa/200 card · VN có β/θ/λ

### Phase 4 — Refinement (không chặn gì)

Lưới SCA (`docs/12`) · gold set · E1c · power study tại effect thật · V-phase corpus tiếng Việt · khối chính sách VN · mở rộng nước (mỗi nước qua cổng Granger)

---

## 7. QUYẾT ĐỊNH ĐANG CHẶN

| # | Quyết định | Chặn | Đề xuất |
|---|---|---|---|
| 1 | **Ranh giới định nghĩa GPR**: theo AI-GPR (loại tranh chấp thương mại) hay mở sang geoeconomic? | Phase 1 + 2 | **Tách hai chỉ số**: tầng A theo đúng AI-GPR (so sánh được); thương mại/thuế quan đo bằng chỉ số riêng ở tầng B. Không trộn vào một điểm |
| 2 | g0 §7.1 SHOCK | 1a | **Đã được §4.1 thay thế** — ký phân rã kép, không chọn A/B/C |
| 3 | g0 §7.2 cửa sổ chân B | 2c | (i)+(ii): KĐ8 daily/weekly, 2024–25 làm dev window |
| 4 | Họ kiểm định | Holm | Nhóm outcome pre-registered |
| 5 | 2 nguồn đầu chân B | Phase 2 | Trump + MOFA CN (trục Mỹ–Trung) |
| 6 | Người chấm mẫu thứ hai | α ≥ 0.6 | — ràng buộc nhân sự thật |

---

## 8. KHÔNG LÀM

Không xây lại chỉ số tin tức · không thêm thước đo shock mới · không thêm chẩn đoán E1x · không tự chế bootstrap/hiệu chỉnh · không tín hiệu giao dịch · không chạm holdout ngoài một lần đã định · không để LLM sinh số/chấm gate/chọn spec · không claim dự báo từ dữ liệu `commitment` chấm trước cutoff · không nhảy từ tin thẳng sang chỉ số một nước.

---

## 9. HOÀN THIỆN v1

Một phát ngôn thật lúc 14:07 → card 14:10. Cuối tháng → brief với γ thật (sống sót qua battery), phân phối thật, analogue kiểm chứng được. VN có β/θ/λ riêng. Track record công khai chấm ≥1 chu kỳ.

**Tuần này:** `load_ai_gpr()` + hiệu chuẩn phân vị + chạy 1a. Bạn chốt §7.1 và §7.5–7.6.