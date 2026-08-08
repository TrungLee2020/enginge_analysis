# 17 — MASTER PLAN "GPR LIVE" (bản đã kiểm chứng)

**Phiên bản:** 1.1 — 2026-08-08. Dựa trên bản tổng hợp v1.0 của user (đề "10 — MASTER PLAN").
**Đánh số:** user đề "docs/10" nhưng `docs/10_action_plan.md` ĐÃ TỒN TẠI (2026-07-16, kế hoạch Phase F). Ghi đè số 10 sẽ xóa lịch sử quyết định đang được `docs/16`, `g0_governance.md` tham chiếu → dùng số **17** (số trống kế tiếp). Nội dung không đổi vì số.
**Quan hệ:** thay thế vai trò ĐỊNH HƯỚNG SẢN PHẨM của `11`, `13`, `14`, `15`, `16`. **Chưa archive 5 doc đó** — lý do ở §D2.
**Vẫn hiệu lực, không gộp:** `CLAUDE.md` (12 nguyên tắc — §2 dưới đây chỉ là tập con hướng sản phẩm) · `g0_governance.md` · `12_specification_curve_protocol.md` · `00_engine_design.md`.

> **Cách đọc doc này.** §1–§6 là kế hoạch (đã sửa). §7 là quyết định thật sự còn mở. §A–§D là **nhật ký kiểm chứng**: 6 chỗ v1.0 sai/đuối so với file và code thật, kèm số đo lại. Mọi số trong §A sinh bởi `scripts/check_master_plan_claims.py` — chạy lại được, không gõ tay (Guard P1).

---

## 1. SẢN PHẨM

**GPR Live** — nhận tin tức/phát ngôn địa chính trị, trả nhận định ảnh hưởng vĩ mô.

| Lớp | Nhịp | Claim tối đa | Nội dung |
|---|---|---|---|
| **Đo lường** | realtime | `measurement` | Sự kiện, actor, cường độ, kênh, vai trò nước, phân vị lịch sử. **Không dự báo** |
| **Nhận định — Global Macro Impact** | tháng + bản bất thường khi sốc đuôi | `predictive, chưa xác nhận holdout` | Phân phối vĩ mô có điều kiện theo kênh + khoảng + episode lịch sử kiểm chứng được |
| **Nhận định — Country Transmission (VN)** | tháng | **`association`, ĐỊNH TÍNH** cho tới khi `config/params/vn.yaml` có mục `fitted:` | Kênh phơi nhiễm + hướng. **Không độ lớn, không phân phối** |

Dòng thứ ba là chỗ v1.0 gộp chung: `pipeline/vn_exposure.py::has_quant_params` trả `False` cho tới khi có β/θ/λ ước lượng, nên VN **không thể** mang phân phối có điều kiện như Global (nguyên tắc #4 / §2.4). Tách hai dòng để không hứa nhầm khi pitch.

**Định vị:** nhà mô hình định lượng — có sai số, tái lập được, có track record công khai. Khác AI-GPR: có sản phẩm, có phát ngôn sơ cấp, có VN.

---

## 2. NGUYÊN TẮC (tập con hướng sản phẩm — KHÔNG thay CLAUDE.md)

`CLAUDE.md` có **12** nguyên tắc và vẫn là nguồn chân lý. 8 điều dưới là bản rút gọn để nói chuyện với người ngoài; 4 điều v1.0 bỏ sót nhưng **đang gánh phần lớn rủi ro kỹ thuật** được ghim lại ở đây:

1. **LLM đo và diễn đạt. Công thức truyền dẫn.** LLM không sinh số, không chấm gate, không chọn spec.
2. **Guard P1** — mọi số trong output khớp một trường payload, chặn cứng, chạy runtime qua `NarrativeBuilder.render()`. *(Tiền lệ lỗi thật: report ghi "1.8×" trong khi payload = 2.77×.)*
3. **Không claim vượt mức nhận dạng** — `measurement ≺ association ≺ prediction ≺ structural ≺ causal`. Reduced-form LP = "transmission decomposition", KHÔNG phải "causal".
4. **Không có tham số ước lượng thì không nói độ lớn.**
5. **Im lặng là hợp lệ.** n<5 episode, IQR đổi dấu, dữ liệu thiếu → "không kết luận được".
6. **Không tự chế công cụ thống kê.** `arch`, `statsmodels`, hoặc không gì cả.
7. **Ghim vintage mọi nguồn.** `data_version` phủ vintage từng chuỗi; AI-GPR ghim bằng `ai_gpr_vintage()` (hash file) vì URL không đổi mà nội dung đổi.
8. **Không tín hiệu giao dịch.**

**Bốn ràng buộc kỹ thuật v1.0 bỏ quên (giữ nguyên hiệu lực từ CLAUDE.md):**

- **#9 — shock là innovation, không phải level.** Chi phối trực tiếp §4.1.
- **#10 — KHÔNG forward-fill monthly → daily.** Đây là điều làm sai sót §3 của v1.0 trở nên nghiêm trọng, không chỉ là lỗi chính tả: xem §A2.
- **#11 — `available_at`, không phải `date`.** Mọi loader point-in-time qua `load_series(..., as_of=...)`.
- **#3 — final holdout 2026-H1 chạm đúng 1 lần.**

---

## 3. TẦNG DỮ LIỆU — INGEST, KHÔNG BUILD

**Bảng dưới đã sửa granularity theo file thật.** v1.0 ghi 3 dòng là `daily` trong khi file là `monthly`, và ghi 13 vùng oil trong khi file có 8 — hệ quả không nhỏ, xem §A1–A2.

| Nguồn | Nhịp THẬT | Trạng thái | Vai trò |
|---|---|---|---|
| AI-GPR headline (`GPR_AI`) | daily + monthly | ✅ đã tải, đã có loader + `ingest/ai_gpr.py` | shock chính |
| AI-GPR threats/acts | daily + monthly | ✅ | hai cơ chế truyền dẫn riêng |
| AI-GPR Oil × **8 cột vùng** (gộp từ 13 vùng của paper) | daily + monthly | ✅ | kênh năng lượng. **KHÔNG có cột `Southeast Asia` riêng** — nằm trong `GPR_OIL_Asia` (= Central Asia + SE Asia + China) |
| AI-GPR country × 200 × 4 vai | **monthly** | ✅ | VN qua vai `spillover` — **track THÁNG, không dùng được cho daily (#10)** |
| AI-GPR bilateral × 1.200 cặp có hướng | **monthly** | ✅ | phơi nhiễm theo cặp — **track THÁNG** |
| AI-GPR country × 8 loại sự kiện | **monthly** | ✅ | ứng viên đo phơi nhiễm theo loại sự kiện |
| `GPR_AER` (keyword C-I 2022, tính lại trên đúng 3 báo của AI-GPR) | daily + monthly | ✅ | chuỗi ĐỐI CHỨNG cho hiệu chỉnh sai số đo |
| GPR gốc C-I (`GPRD`/`GPRC`) | daily + monthly | ✅ đã ingest | proxy thứ hai |
| EPU | monthly | ✅ | battery control |
| **WUI** | quý | ⛔ `data/wui_global.csv` chưa có | battery — **tải tay**, thiếu thì report ghi rõ |
| Oil/DXY/VIX/US10Y/freight | daily + monthly | ✅ | biến tầng 2 |
| Real macro (IP, CPI, kỳ vọng lạm phát) | monthly | ✅ | outcome tầng 2 |
| **VNINDEX** | daily | ⛔ chưa có | tier3 VN |
| **WIG / IPSA** (nước pilot 1b) | daily | ⛔ không có trên FRED, chưa chốt nguồn | **chặn Phase 1b trước cả khi bắt đầu** — v1.0 không nhắc |

### 3.1. Hiệu chỉnh sai số đo — phát biểu lại theo TẦN SUẤT

v1.0 nói "tương quan chỉ 0.69 → sai số phân loại → dùng IV khử attenuation". Con số 0.69 là của **paper (tần suất tuần)**. Đo lại trên mẫu chung 1985-2026 của chính dự án:

| Tần suất | corr(AI-GPR, GPR_AER) |
|---|---|
| daily | **0.716** |
| weekly | **0.817** |
| monthly (1985+) | **0.853** |

Tương quan **tăng theo mức tổng hợp** — nhiễu phân loại phần lớn là nhiễu tần số cao và bị trung bình hóa mất. Hệ quả:

- Ở **daily** (chân A realtime, trigger): sai số đo đáng kể, IV/factor có lý do.
- Ở **monthly** (nơi tầng 2 thật sự chạy): attenuation nhỏ hơn nhiều so với ấn tượng "0.69" gợi ra. → **IV/nhân tố chung là nhánh ROBUSTNESS của 1a, không phải deliverable chính** của Phase 1.
- Giới hạn giữ nguyên: cả hai chỉ số đọc báo Mỹ → chia sẻ một phần sai số (sự chú ý của tòa soạn), IV không khử được phần chung, cần kiểm định over-identification.

---

## 4. TẦNG CÔNG THỨC

### 4.1. Phân rã kép — spec chính

$$y_{t+h} - y_{t-1} = \alpha_h + \beta_h^{P}\,\widehat{\Delta G}_t + \beta_h^{S}\,\hat u_t + \sum_j \phi_{h,j} y_{t-j} + \Gamma_h'\mathbf{c}_t + \varepsilon_{t+h}$$

$\widehat{\Delta G}_t$ = ANTICIPATED (fitted từ AR(p) trên **sai phân**), $\hat u_t$ = SURPRISE ≡ `shocks.innovation()`. Hai thành phần cộng lại bằng **đúng** Δ LEVEL (đồng nhất thức, đã khóa bằng test). Đưa cả hai vào cùng lúc, không chọn giữa các thước đo. **Thiết kế này giữ nguyên — nó là lối ra đúng.**

**Đã xóa khỏi v1.0: câu "thành phần dai dẳng tác động hơn gấp đôi (−0.271 vs −0.119), cả hai có ý nghĩa".** Đó là so sánh **hệ số thô** của hai regressor có phương sai lệch ~10 lần. `docs/reports/E2_component_decomposition_e73a0a307fc3.md` đã chạy đúng phép so sánh đó trên dữ liệu dự án: 34/45 ô có |β_P|>|β_S| theo thô, **chỉ 12 ô giữ được sau chuẩn hóa — 48.9% ô đảo chiều kết luận**. Ở ô chính (`GPR_ACT → IP`, h=2) thì SURPRISE mới là cái có ý nghĩa (p=0.042 vs 0.180). Dùng "hơn gấp đôi" làm lý do bênh vực spec kép là lặp lại đúng tai nạn thang đo mà registry đã ghi cho `LEVEL+JUMP`.

**Điều kiện bắt buộc (đã ký, `DEC-2026-08-03-dual-component`):**
- Đóng góp báo cáo **chuẩn hóa** (β×sd) qua `standardized_contribution`, không bao giờ hệ số thô.
- $\beta^P$ gọi là "phản ứng với thành phần đã dự báo được". Gọi là "tác động của cú sốc" = vi phạm #9, cổng máy `shock_axis.check_component_labelling` raise.

**Tương tác threat/act:** spec đầy đủ 4 regressor trong CÙNG một hồi quy. Xem §C3 — API hiện tại chưa trả về đủ hệ số cho spec này.

**Ba thước đo cũ {LEVEL, INNOVATION, LEVEL+JUMP}** xuống robustness khi spec kép chạy được trên AI-GPR — đúng như `DEC-2026-08-03-dual-component` đã ký. **Nhưng:** việc này **không tự động chốt** `SCA-01.primary_cell.shock` (xem §7 #2).

### 4.2. Tách kênh

Sốc năng lượng đẩy lãi suất **lên** (chi phí đẩy); sốc thương mại kéo **xuống** (phía cầu). Gộp kênh = cộng hai cơ chế ngược dấu → triệt tiêu.

Nguồn tách kênh, theo đúng cái đang có:
- **energy** → `GPR_OIL` + 8 cột vùng (daily). VN: dùng `GPR_OIL_Asia` và `GPR_OIL_MiddleEast`; **không có cột Southeast Asia riêng** để trỏ thẳng vào Malacca.
- **trade** → bilateral index (**monthly**), paper đã validate bằng gravity equation.
- **military / financial** → `EVENT_TYPE_TO_CHANNEL` (đã ký ý nghĩa `DEC-2026-08-05-event-type-channel`, **chưa nối production**; `terrorism`/`diplomatic_tension`/`other` giữ `None`).
- ⚠️ Bảng γ đang có (`docs/reports/data/t2_full_holm_*.csv`) tách theo `pooled/act/threat` — đó là **biến thể GPRD dùng làm shock**, KHÔNG phải 4 kênh truyền dẫn. `gamma_lookup.commitment_to_gamma_channel` là proxy tường minh. Tách γ theo 4 kênh thật là việc của 1a, chưa làm.

### 4.3. Số hạng đuôi + quantile

$J_t = \max(0, z_t - q^{roll}_{0.95})$ — tác động phi tuyến.

$Q_\tau(\cdot)$, $\tau \in \{.10,.25,.50,.75,.90\}$, không dưới 0.10. Điểm cốt lõi giữ nguyên: $\beta_{0.5}\approx 0$ **và** $\beta_{0.10}<0$ là tương thích — rủi ro làm **dày đuôi trái**, không dịch mức trung tâm.

**Hiệu chuẩn lại trên AI-GPR — kết quả đo thật (mẫu chung 1985-2026, n=15.187):**

| | AI-GPR | GPR_AER | GPRD |
|---|---|---|---|
| sd | **47.6** | 61.8 | 61.5 |
| autocorr(1) daily | **0.580** | 0.498 | **0.754** |
| autocorr(1) weekly | **0.852** | 0.820 | **0.871** |
| skew / kurtosis | 2.09 / 9.5 | 1.87 / 7.6 | **3.74 / 28.8** |
| % ngày bằng 0 | **0.00%** | 0.21% | 0.01% |

- "mượt hơn (sd ~48 vs ~61)" ✅ đúng.
- "đuôi phải mỏng hơn" ✅ đúng, và mỏng hơn **nhiều** (kurtosis 9.5 vs 28.8) → ngưỡng q95/q99 và toàn bộ thiết kế trigger **bắt buộc** chạy lại phân vị trên chính AI-GPR, không mượn ngưỡng GPRD.
- "không có ngày bằng 0" ✅ đúng cho `GPR_AI`/`THREATS`/`ACTS`.
- ❌ **"dai hơn (0.73 vs 0.62)" — phải nói rõ so với AI.** So với `GPR_AER` (cùng 3 tờ báo): AI-GPR dai hơn thật (0.580 vs 0.498 daily; 0.852 vs 0.820 weekly). So với **GPRD** — chuỗi dự án đang dùng làm shock: **AI-GPR dai KÉM hơn** ở cả hai tần suất. Hệ quả thẳng vào §4.1: giới hạn tự ghi của E2 ("AI-GPR dai hơn nên R² của AR sẽ cao hơn, khoảng cách chuẩn hóa **có thể không đảo**") lấy GPRD làm mốc thì **không còn là lối thoát** — nhiều khả năng kết luận đảo chiều của E2 vẫn đứng trên AI-GPR. Phải chạy E2 lại để biết (§6 Phase 1, việc đầu tiên).
- ⛔ **Zero-inflation ở kênh năng lượng — v1.0 không nhắc:** `GPR_OIL` bằng 0 ở **31.8%** số ngày; theo vùng còn nặng hơn (MiddleEast 50.5%, Russia 81.1%, Asia 88.4%, NorthSea 99.7%). Mọi phân vị/JUMP/trigger trên kênh energy **bắt buộc** dùng quy ước `expanding_percentile` strict `<` của `indices/s_gpr.py`, nếu không ngày im ắng sẽ ra p≈100 và trigger nổ mỗi ngày. Với NorthSea/Venezuela/Americas, mật độ 0 cao tới mức **percentile không còn nghĩa** — dùng mô hình hai phần (có/không) hoặc bỏ vùng đó khỏi trigger.

### 4.4. Suy diễn

LP lag-augmented (MO-PM 2021: lag của **cả y lẫn shock**) + SE HC1. Dải **sup-t** cho họ horizon. Holm trong họ outcome pre-registered {asset_price 4 · real_macro 3 · physical 1}.

**Ràng buộc code phải ghi vào spec (v1.0 mâu thuẫn với chính nó):**
- `simultaneous=True` (sup-t) **chỉ hợp lệ với** `inference="lag_augmented"` — ghép với HAC thì raise (hai bộ SE trong một dải).
- `simultaneous=True` + `method="quantile"` → **`NotImplementedError`**: hàm ảnh hưởng của hồi quy phân vị chưa làm, cần bootstrap. Nên §4.3 (quantile) và §4.4 (sup-t) **không thể áp cùng một ô**. Quy ước: **sup-t cho nhánh OLS; nhánh phân vị báo cáo pointwise + Holm, và ghi rõ trong report là "không hiệu chỉnh đồng thời theo horizon"**. Không tự chế bootstrap (§2.6).
- "không block bootstrap" ở đây nói về **SE của LP**, không rút lại moving-block bootstrap dưới null của `docs/12` (SCA) — hai thứ khác mục đích. ℓ đã hiệu chỉnh: tháng=18, ngày=40.
- QuantReg (IRLS) không hội tụ → `run_local_projection` trả cột `converged`, bảng in `‡` thay vì số (386/6000 hàng của T2-full rơi vào đó).

### 4.5. Tầng 3 — block exogeneity

$$A_{XZ}(L) = \mathbf{0}\ \forall L$$

$\mathbf{X}$ = khối ngoại (shock, oil, DXY, VIX, US10Y, freight); $\mathbf{Z}$ = khối nội $[r^c_t, p_t, g^d_t]$. Đây **là** "1 engine, n bộ params" viết bằng kinh tế lượng, kiểm định được bằng Granger khối $\mathbf{Z}\nrightarrow\mathbf{X}$ — cổng bắt buộc trước khi thêm nước.

⚠️ Với VN, khối $\mathbf{Z}$ cần $r^c$ (VNINDEX — chưa có) **và** $p$ (chính sách — chưa có rubric, xem §4.6). Cổng Granger cho VN **chưa chạy được**, không chỉ vì thiếu VNINDEX.

### 4.6. VN

- **Vai `spillover` chiếm ưu thế trong CỬA SỔ dự án, không phải "gần như luôn luôn".** Đo trên file thật:

| Giai đoạn | % biên độ spillover | % số tháng spillover áp đảo | Vai áp đảo |
|---|---|---|---|
| 2015–2026 (dev+val+OOS) | **67.4%** | **64.7%** | spillover |
| 1960–1989 | 17.1% | 9.2% | **respondent** (57.1% / 63.3%) |
| Toàn mẫu 1960–2026 | 17.9% | 29.8% | **respondent** (56.7% / 50.2%) |

  Cơ chế hợp lý (VN chuyển từ "trong cuộc chiến" sang "nền kinh tế mở hứng sốc bên ngoài"), chuyển tiếp trơn. **Giả định spillover hợp lệ trong đúng cửa sổ ước lượng — sai nếu khái quát ngược lịch sử.** Ngay trong 2015+, `respondent` vẫn chiếm 26.5% biên độ, nên vẫn phải mang cả hai vai vào spec, không vứt.

- **Hệ quả #10 (v1.0 bỏ sót):** country + bilateral index là **monthly**. Câu "không cần corpus tiếng Việt cho v0" **chỉ đúng cho track THÁNG**. Sản phẩm VN **daily** vẫn bị chặn bởi #10 — không được ffill monthly xuống ngày. Đường daily VN cần: AI-GPR daily global + bilateral **monthly làm biến chậm riêng**, hoặc corpus báo Việt (V-phase). **VNINDEX không phải blocker duy nhất.**
- Kênh: năng lượng (`GPR_OIL_Asia`, `GPR_OIL_MiddleEast`) · thương mại (bilateral Mỹ–Trung–Việt, hai chiều rủi ro/cơ hội) · vận tải/Malacca (proxy = freight PPI, **đo truyền dẫn chi phí chứ không đo tắc nghẽn**) · tỷ giá.
- **Biên độ ±7%** của HOSE chặt cụt cơ học ở vùng đuôi → dùng lợi suất tích lũy $k\geq3$ ngày, không dùng một phiên. (Ảnh hưởng thẳng tới §4.3: quantile τ=0.10 trên lợi suất một phiên bị censoring.)
- Khối chính sách: nhận dạng kiểu Aruoba–Drechsel (NLP trên văn bản → dự đoán có điều kiện → phần dư), vì VN không có phái sinh lãi suất để đo surprise. **Rubric riêng** (nới lỏng↔thắt chặt), không dùng lại thang leo thang.

---

## 5. TẦNG LLM

**Chỉ hai việc:** chấm điểm theo rubric, viết narrative từ payload.

| | Tầng A — replication | Tầng B — của mình |
|---|---|---|
| Nguồn | tin báo chí | phát ngôn sơ cấp |
| Thang | 0–1 đơn cực, prompt nguyên văn Appendix A.6 | ±1.0 lưỡng cực |
| Trường | threat/act, oil+vùng, country+event_type | + commitment, specificity, actor_weight |
| Dùng để | so được với chuỗi công bố | đo thứ AI-GPR không đo |

Hai chỉ số **tách bạch, không trộn**. Zero-shot, JSON structured, cắt 2.000 ký tự (tầng A) / 3.000 (tầng B). Mọi subindex dùng **chung mẫu số $A_t$**.

⚠️ **`temperature`: v1.0 ghi 0, code `statement_scorer.DEFAULT_TEMPERATURE = 0.1`** (theo ECB LGPT). Đây không phải chi tiết nhỏ: temperature nằm trong khóa cache và trong 5 trục version, đổi nó = **vô hiệu toàn bộ điểm đã chấm**. Chốt một giá trị rồi sửa cả hai nơi trong cùng commit; nếu chọn 0 thì phải backfill lại.

**Versioning:** `model_version` + `prompt_version` + `rubric_version` + `temperature` + cache theo hash. Chuỗi vào track record dùng **model local pin cứng** (`DEC-2026-08-02-chanb-window`).

**Hiệu chuẩn đã biết (audit của paper):** model **nén đỉnh thang**, gần như không chấm trên 0.8 → điểm cao là hiểu thấp so với thực tế. Model **chấm cao ở đáy** → hay nhầm bất ổn nội địa và tranh chấp thương mại thành GPR. (Điểm thứ hai chính là lý do §7 #1 tồn tại.)

---

## 6. LỘ TRÌNH

### Phase 1 — "Công thức nói gì?" (~2–3 tuần)

**Đã xong, gạch khỏi checklist v1.0:** `load_ai_gpr_daily/monthly` + 4 loader Country Decompositions + `ai_gpr_vintage()` (hash file) + `ingest/ai_gpr.py` (12 chuỗi tổng hợp vào `ext_series`). Không còn việc "tải + viết loader".

Việc **thật sự** còn lại:

- [ ] **P1.0 — sửa đường dẫn.** Loader mặc định trỏ `data/ai_gpr_data_daily.csv`, `data/data_gpr_daily_recent.xls`; repo đang có `data/AI-GPRs/…` và `data/GPR index/data_gpr_daily_recent (1).xls`. Hiện **không script nào chạy được ngay** (§C5).
- [ ] **P1.1 — chạy lại E2 trên AI-GPR.** E2 tự ghi đây là việc để khép lại, và §4.3 vừa cho thấy lối thoát "AI-GPR dai hơn" không áp dụng với mốc GPRD. Kết quả quyết định cách đọc §4.1.
- [ ] **P1.2 — hiệu chuẩn lại phân vị/JUMP trên AI-GPR**, gồm xử lý zero-inflation kênh energy (§4.3).
- [ ] **P1.3 — code: cho `build_monthly_panel()` đổi được NGUỒN shock** (GPR gốc ↔ AI-GPR). Hiện hard-code file xls (§C2). Không có cái này thì "chạy ba bản" của 1a không thực hiện được.
- [ ] **P1.4 — code: trả về đủ hệ số cho spec đa regressor.** `estimate_tier2()` chỉ báo cáo hệ số của `shock`; ANTICIPATED+SURPRISE (và spec 4 regressor threat/act) cần `return_all=True` nối xuyên qua tier2, kèm `supt_c` riêng từng hệ số (§C3).
- [ ] **P1.5 — code: cột ANTICIPATED/SURPRISE vào panel.** `delta_decomposition` đã có nhưng chưa được builder nào gọi; `components=True` hiện là act/threat, không phải cặp phân rã (§C4).
- [ ] **1a**: tier2 tháng, spec phân rã kép, threats/acts, Oil×vùng, quantile, sup-t (theo ràng buộc §4.4), h=0..24. Ba bản: **GPR gốc · AI-GPR · IV/factor (robustness, §3.1)**. Battery EPU (+ WUI nếu tải được file).
- [ ] **1b**: cascade tier3 end-to-end, nhãn PLUMBING. ⛔ **Chốt nguồn WIG/IPSA trước** — `pilot_market_series_missing` đang mở, không có FRED.
- [ ] Registry: spec phân rã kép làm ô chính **cần chữ ký MỚI** (§7 #2); ba thước đo cũ → robustness. `vn_market_series_missing` **đã có sẵn**, không phải thêm.

**⛔ Cổng:** bảng γ tồn tại · cascade chạy hết · độ lớn effect thật được ghi (đầu vào cho mọi câu hỏi power sau).

### Phase 2 — Chân B (~4–5 tuần)

- [ ] Collector 2 nguồn (Trump + MOFA CN, đã ký) + scorer tầng B + bảng DB + card template thuần
- [ ] Backfill + human audit 500 mẫu × 2 người → α ≥ 0.6
- [ ] `s_gpr.py` + `ladder.py` V1 + trigger rules (ngưỡng S1/S3 vẫn chờ user — `docs/00` §4.1 chưa cho)
- [ ] Cổng contamination **chỉ cho `commitment`** — paper đã bác lo ngại cho tầng chấm cường độ (tương quan 0.95 với prompt neo ngày); dự đoán "đe dọa có thành hiện thực không" là chuyện khác

**⛔ Cổng:** card thật < 3 phút · α ≥ 0.6

### Phase 3 — Sản phẩm (~4 tuần)

- [ ] `analogue.py` (đã có: n<5 raise, IQR đổi dấu → không kết luận, `available_at ≤ t` kể cả khi retrieval)
- [ ] Composer + guard P1 → Model Brief đầu tiên (đã có thân; còn thiếu số thật để đổ vào)
- [ ] Serving: FastAPI + Kafka → BeaverX agents (pipeline + Kafka consumer đã chạy; **chưa test end-to-end với Postgres/Kafka sống**)
- [ ] Track record (CRPS/Brier, công khai)
- [ ] VNINDEX → tier3 VN → **Country Transmission VN v0** (chỉ khi `vn.yaml` có `fitted:`; trước đó giữ claim `association` như §1)

**⛔ Cổng:** brief đủ 4 tầng claim · 0 số bịa/200 card · VN có β/θ/λ

### Phase 4 — Refinement (không chặn gì)

Lưới SCA (`docs/12`) · gold set · E1c · power study tại effect thật · V-phase corpus tiếng Việt · khối chính sách VN · mở rộng nước (mỗi nước qua cổng Granger).

---

## 7. QUYẾT ĐỊNH ĐANG CHẶN (đã lọc — 4/6 mục của v1.0 ĐÃ KÝ RỒI)

`config/hypothesis_registry.yaml` §`decisions:` + `tests/test_registry_locked.py::LOCKED_DECISION_IDS` cho thấy 4 mục v1.0 liệt kê là "đang chặn" thực ra đã ký từ 2026-08-02. Để nguyên chúng trong bảng "đang chặn" là mời mở lại quyết định đã khóa — mà mở lại thì phải sửa `LOCKED_DECISION_IDS` cùng commit, đúng cơ chế test bắt.

| # | Quyết định | Trạng thái THẬT | Việc |
|---|---|---|---|
| 1 | **Ranh giới định nghĩa GPR**: theo AI-GPR (loại tranh chấp thương mại) hay mở sang geoeconomic? | 🔴 **MỞ — thật sự mới, chưa có chữ ký nào** | **Đề xuất: tách hai chỉ số.** Tầng A theo đúng AI-GPR (để so sánh được); thương mại/thuế quan đo bằng chỉ số RIÊNG ở tầng B. Không trộn vào một điểm. Trùng khớp với hiệu chuẩn "model chấm cao ở đáy, hay nhầm tranh chấp thương mại thành GPR" (§5) |
| 2 | **Chốt ô chính `SCA-01.primary_cell.shock`** | 🔴 **MỞ — v1.0 không liệt kê nhưng đây mới là mục chặn thật** | `DEC-2026-08-03-dual-component` ghi rõ: chốt ô chính **bằng spec kép là chốt bằng THIẾT KẾ chứ không bằng E1c-exo** — đúng thứ mà việc để UNRESOLVED sinh ra để tránh. Cần **chữ ký MỚI**, kèm quyết định có bỏ ràng buộc gold-set/E1c-exo hay không |
| 3 | g0 §7.1 SHOCK (LEVEL / INNOVATION / LEVEL+JUMP) | ✅ **ĐÃ KÝ** `DEC-2026-08-02-shock-axis`, amend bởi `DEC-2026-08-03-dual-component` | Không mở lại. Cổng máy `gate_shock_eligibility` (LEVEL chỉ eligible với lag_augmented) **vẫn nguyên hiệu lực** |
| 4 | g0 §7.2 cửa sổ chân B | ✅ **ĐÃ KÝ** `DEC-2026-08-02-chanb-window` — (i)+(ii), 2024–25 = dev window | Không mở lại |
| 5 | Họ kiểm định Holm | ✅ **ĐÃ KÝ** `DEC-2026-08-02-holm-family` — nhóm outcome pre-register (4/3/1) | Không mở lại |
| 6 | 2 nguồn đầu chân B | ✅ **ĐÃ KÝ** `DEC-2026-08-02-sources-trading` — Trump + MOFA CN, bỏ tín hiệu giao dịch | Không mở lại |
| 7 | Người chấm mẫu thứ hai (α ≥ 0.6) | 🟡 **MỞ — ràng buộc nhân sự thật**, không ủy quyền máy được | Cần con người |
| 8 | `temperature` LLM: 0 hay 0.1 | 🟡 **MỞ — mới, do §5 lộ ra** | Chốt rồi sửa doc + code cùng commit; chọn 0 thì phải backfill điểm cũ |

---

## 8. KHÔNG LÀM

Không xây lại chỉ số tin tức · không thêm thước đo shock mới · không thêm chẩn đoán E1x · không tự chế bootstrap/hiệu chỉnh · không tín hiệu giao dịch · không chạm holdout ngoài một lần đã định · không để LLM sinh số/chấm gate/chọn spec · không claim dự báo từ dữ liệu `commitment` chấm trước cutoff · không nhảy từ tin thẳng sang chỉ số một nước · **không ffill monthly (country/bilateral/GPRC) xuống daily** · **không mở lại quyết định đã ký mà không sửa `LOCKED_DECISION_IDS` cùng commit**.

---

## 9. HOÀN THIỆN v1

Một phát ngôn thật lúc 14:07 → card 14:10. Cuối tháng → brief với γ thật (sống sót qua battery), phân phối thật, analogue kiểm chứng được. VN có β/θ/λ riêng. Track record công khai chấm ≥1 chu kỳ.

**Tuần này:** P1.0 (đường dẫn) → P1.1 (chạy lại E2 trên AI-GPR) → P1.2 (hiệu chuẩn phân vị) → P1.3–P1.5 (3 lỗ hổng code) → 1a. **Bạn chốt §7 #1, #2 và #8.**

---

# PHỤ LỤC — NHẬT KÝ KIỂM CHỨNG v1.0

Mọi số ở §A sinh bởi `python scripts/check_master_plan_claims.py` (đọc file thật trong `data/`, không hard-code).

## §A. Sai về DỮ LIỆU

| # | v1.0 nói | File thật | Hệ quả |
|---|---|---|---|
| **A1** | "Oil × **13 vùng** daily; có `Southeast Asia`" | **8 cột**: MiddleEast/Russia/USA/Venezuela/Africa/Americas/Asia/NorthSea. Không có cột SE Asia (nằm trong `Asia` = CentralAsia+SEAsia+China) | Kênh năng lượng VN **không** trỏ thẳng được vào Malacca/SE Asia. Paper có 13 vùng, file công khai gộp còn 8 |
| **A2** | "country × 200 **daily**", "bilateral × 1.200 **daily**" | **monthly** cả hai: 799 hàng, 1960-01-01→2026-07-01, bước trung vị 31 ngày | 🔴 Nặng nhất. §4.6 dựng trên tiền đề daily. Nguyên tắc #10 cấm ffill → **track VN daily vẫn bị chặn**, VNINDEX không phải blocker duy nhất |
| **A3** | "tương quan chỉ **0.69** → sai số đo → dùng IV" | 0.716 daily · 0.817 weekly · **0.853 monthly** | Attenuation nhỏ hơn nhiều ở đúng tần suất tier2 chạy → IV xuống robustness (§3.1) |
| **A4** | "AI-GPR **dai hơn** (0.73 vs 0.62)" | Dai hơn `GPR_AER` ✅ (0.580 vs 0.498) nhưng **dai kém hơn GPRD** (0.580 vs 0.754 daily; 0.852 vs 0.871 weekly) | Đóng lối thoát mà E2 chừa cho §4.1 — kết luận "chuẩn hóa thì đảo chiều" nhiều khả năng vẫn đứng. Phải chạy P1.1 |
| **A5** | "không có ngày bằng 0" | ✅ đúng cho `GPR_AI`/`THREATS`/`ACTS`. **Nhưng `GPR_OIL` = 0 ở 31.8% số ngày**, theo vùng tới 50–99.7% | Thiết kế phân vị/trigger kênh energy phải xử lý zero-inflation; vài vùng percentile mất nghĩa hoàn toàn |
| **A6** | "VN vai spillover **gần như luôn luôn**" | Chỉ đúng 2015+ (67.4% biên độ / 64.7% số tháng). Toàn mẫu: **respondent 56.7%**. 1960-89: respondent 57.1% | Giả định hợp lệ trong cửa sổ ước lượng; sai nếu khái quát lịch sử. Ngay 2015+ respondent vẫn 26.5% → giữ cả hai vai |

## §B. Mâu thuẫn LOGIC nội bộ

- **B1 — §4.1 dùng bằng chứng đã bị bác.** "−0.271 vs −0.119, hơn gấp đôi" là hệ số thô; E2 đã đo: 48.9% ô đảo chiều sau chuẩn hóa, và ở ô chính SURPRISE mới có ý nghĩa. Spec kép giữ nguyên (nó đúng), lý do bênh vực phải đổi.
- **B2 — §4.3 và §4.4 loại trừ nhau trong code.** `simultaneous=True` + `method="quantile"` → `NotImplementedError`. Đã ghi quy ước xử lý ở §4.4.
- **B3 — §7 mở lại 4 quyết định đã khóa** (shock-axis, holm-family, chanb-window, sources-trading — đều trong `LOCKED_DECISION_IDS`). Đồng thời **bỏ sót** mục chặn thật: `SCA-01.primary_cell.shock` vẫn UNRESOLVED.
- **B4 — §2 rút gọn 12 nguyên tắc còn 8**, mất #9/#10/#11/#3 — trong đó #10 chính là thứ làm A2 thành lỗi nghiêm trọng. Đã ghim lại ở §2.
- **B5 — temperature 0 (doc) vs 0.1 (code)**, trong khi temperature nằm trong khóa cache và trục version.
- **B6 — §1 hứa "phân phối vĩ mô có điều kiện" cho cả VN**, nhưng `vn.yaml` chưa có `fitted:` → `has_quant_params=False` → nguyên tắc #4 cấm nói độ lớn. Đã tách thành hai dòng deliverable.

## §C. Việc CÒN THIẾU mà v1.0 không liệt kê

- **C1** — Phase 1 mục đầu ("`load_ai_gpr()` + 5 subindices, ghim vintage") **đã xong từ 2026-08-05**, gồm cả `ingest/ai_gpr.py`. Checklist cũ.
- **C2** — `build_monthly_panel()` hard-code nguồn GPR từ file xls, **không có tham số đổi sang AI-GPR** → "chạy ba bản" của 1a chưa thực hiện được.
- **C3** — `estimate_tier2()` chỉ trả hệ số của một `shock`; regressor thứ hai rơi vào `controls` và hệ số bị vứt. Spec kép (2 regressor) và spec threat/act (4 regressor) cần nối `return_all=True` — `run_local_projection` đã hỗ trợ, kèm `supt_c` riêng từng hệ số.
- **C4** — `shocks.delta_decomposition` chưa được builder nào gọi; `build_monthly_panel(components=True)` là act/threat, **không phải** cặp ANTICIPATED/SURPRISE.
- **C5** — Đường dẫn: loader mặc định `data/ai_gpr_data_daily.csv` + `data/data_gpr_daily_recent.xls`; repo có `data/AI-GPRs/…` + `data/GPR index/data_gpr_daily_recent (1).xls`. Không script nào chạy được ngay.
- **C6** — Blocker thiếu trong bảng §3 của v1.0: `pilot_market_series_missing` (WIG/IPSA — **chặn 1b**), `wui_global_csv` (battery §4.1), `gold_events_csv` (E1c-exo → ô chính).
- **C7** — E2 tự ghi "chạy lại trên AI-GPR ngay khi có dữ liệu" — dữ liệu **đã có**, việc chưa làm, và §A4 khiến nó thành việc đầu tiên chứ không phải việc phụ.

## §D. Đánh số & lưu trữ

- **D1** — `docs/10_action_plan.md` đã tồn tại → bản này là `docs/17_master_plan.md`.
- **D2** — **Chưa** chuyển `11/13/14/15/16` sang `docs/archive/`. Lý do: chính 5 doc đó (đặc biệt `docs/16` §3, đã tự đính chính **hai lần** về granularity) mang những đính chính mà v1.0 làm mất — archive trước khi bản chốt hấp thụ hết là chôn luôn đường kiểm chứng. Archive sau khi §7 #1/#2/#8 có chữ ký và §A được xác nhận.
