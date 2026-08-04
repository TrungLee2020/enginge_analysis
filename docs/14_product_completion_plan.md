# 14 — KẾ HOẠCH HOÀN THIỆN SẢN PHẨM

**Phiên bản:** 1.2 — 2026-07-21. Thay thế v1.1 (cùng ngày). **Tự chứa.**
**Khác v1.1:** sáu sửa từ vòng đối chiếu văn bản ↔ **code thật** — (i) §1.1 trả 3 dòng về §1.2: LP lag-augmented/sup-t, `arch` SPA/StepM, quantile regression **chưa tồn tại trong code**; (ii) §1.2 thêm M0 outcome vĩ mô thực (IP/CPI/kỳ vọng lạm phát) — cascade cũ dừng ở kênh tài chính, chưa chạm "xu hướng vĩ mô"; (iii) §2 1a thêm ràng buộc **cùng mẫu** cho bản a/b và trục SHOCK; (iv) §2 1c thêm việc sửa cổng máy `GATE_ELIGIBLE_SHOCK_TYPES`; (v) §3.1 thêm va chạm cutoff × split khóa cứng; (vi) §6 thêm 2 quyết định mới. **v1.1 §1.1 sai ở 3 dòng — đừng lập kế hoạch dựa trên bản đó.**
**Khác v1.0:** ba sửa từ vòng rà văn liệu — (i) cổng contamination + quy tắc post-cutoff cho chân B (Phase 2); (ii) `surprise.py` đổi sang nhận dạng kiểu Aruoba–Drechsel (Phase 4, spec §5); (iii) benchmark battery EPU/WUI + KĐ8 viết lại (Phase 1a). Còn lại giữ nguyên.
**Quan hệ tài liệu:** phần spec công thức, nguyên tắc P1–P7, và mẫu card/brief của `11_product_plan.md` §1–2, §5 **vẫn hiệu lực**. `docs/13` (E1c/gold-set/lưới) hạ xuống refinement, không chặn.
**Nguyên tắc neo:** cái gì đã có thì dùng, không xây lại. Công thức đã viết thì chạy trước, tinh chỉnh sau. LLM đo và diễn đạt; công thức truyền dẫn.

---

## 0. SẢN PHẨM LÀ GÌ (một đoạn)

**GPR Live** — nhận tin tức/phát ngôn địa chính trị, trả về nhận định ảnh hưởng vĩ mô, hai lớp:

1. **Measurement Card** (realtime): sự kiện, actor, cường độ (rubric ±1.0), kênh, trạng thái leo thang, phân vị so với 40 năm. *Không dự báo.* Claim = `measurement`.
2. **Model Brief** (tháng + bản bất thường khi sốc đuôi): phân phối vĩ mô có điều kiện theo kênh + khoảng tin cậy + bối cảnh episode kiểm chứng được. Claim tối đa = `predictive, chưa xác nhận holdout` (track tháng — đã ghi `g0` §2).

Hai deliverable: **Global Macro Impact** (generic) · **Country Transmission** (VN trước; β/θ/λ + khối phản hồi chính sách).

---

## 1. TRẠNG THÁI

### 1.1. Đã có, đủ dùng, không đụng

| Thành phần | Nguồn |
|---|---|
| GPR 40 năm; **LEVEL = shock mặc định** ⚠️ xem §6.4 | C-I 2022; E0 xác nhận trên pipeline mình (β=−0.37, p=0.008, h=2 tháng) |
| Panel tháng 5 **kênh truyền dẫn** (oil/dxy/vix/us10y/freight) + alignment + daily | code, 108 test. ⚠️ đây là KÊNH, không phải outcome vĩ mô — xem M0 §1.2 |
| Panel tháng đổi được **nước** (`country=`) | `build_monthly_panel(country="POL")` — mở khóa Phase 1b (2026-07-21) |
| **Outcome vĩ mô thực** IP/CPI/kỳ vọng lạm phát | `load_real_macro_monthly` + `transform_real_macro`; `ip` dùng ĐÚNG `100·Δln(INDPRO)` của E0 (2026-07-21) |
| **Benchmark battery** EPU US/Global | `load_benchmark_monthly` + `transform_benchmark` (log1p, cùng quy ước GPR) (2026-07-21). WUI phải tải tay → `data/wui_global.csv` |
| LP Jordà + HAC/Newey-West | `local_projection.py` — **chỉ có bấy nhiêu**, xem M8 §1.2 |
| Công thức tầng 2/3: γ kênh, block-exo + Granger test, Shapley/LMG, tích chập indirect | `tier2_global_macro.py`, `tier3_country.py`, `panel_var.py` |
| Công thức LLM scorer | ECB LGPT: encoder lọc (~0.6) → LLM, temp 0.1, JSON strict, taxonomy 4 kênh |
| Rubric cường độ ±1.0 + prompt + schema DB | docs/00 §2 — khoảng trống ECB ghi nhận nhưng không làm |
| Nguyên tắc P1–P7 + mẫu card/brief | docs/11 §1–2 |

### 1.2. Thiếu — toàn bộ kế hoạch nằm ở đây

⚠️ **M8–M10 là sửa sai của v1.1**: ba dòng này từng nằm ở §1.1 "đã có, đủ dùng, không đụng". Chúng **không có trong code**. Kiểm lại bằng `grep -rn "sup_t\|lag_augment\|import arch\|QuantReg" src/ scripts/` → 0 kết quả.

| # | Thiếu | Chặn bởi |
|---|---|---|
| M0 | ✅ **Outcome vĩ mô thực** (IP/CPI/kỳ vọng lạm phát) — XONG 2026-07-21 | — |
| M8 | ✅ **LP lag-augmented + SE White + dải sup-t** — XONG 2026-07-21 | — |
| M9 | ✅ **Quantile regression** (`method="quantile"`, τ bất kỳ) — XONG 2026-07-21 | — |
| M10 | ✅ **Holm giữa outcome** — XONG 2026-08-02 (`multiplicity.py`). Thủ tục đã có; **chọn HỌ** vẫn chờ §6.6 (`family` không có mặc định — có chủ đích) | — (phần code); §6.6 cho phần chữ ký |
| M1 | ✅ **Bảng γ thật** — XONG 2026-08-02, `docs/reports/T2_full_f2579b30928f.md` (n=231 tháng, 3600 hàng γ). Chờ **human review** | — |
| M2 | Bộ β/θ/λ đầu tiên (tier3 chưa từng chạy dữ liệu thật) | nước pilot (không phải VN) |
| M3 | β/θ/λ cho VN | `VNINDEX` — đường nối BeaverX. Registry: thêm `vn_market_series_missing` |
| M4 | Chân B: collector + scorer + S-GPR + ladder | 2 quyết định §6 |
| M5 | ✅ **Analogue retrieval** — XONG 2026-08-03 (`econometrics/analogue.py`). Bốn ràng buộc docs/11 §6 đều là **cơ chế**, không phải lời hứa | — |
| M6 | ✅ **Composer + guard P1** — XONG 2026-08-03 (`reporting/{guard,composer}.py`). Serving còn lại ở 3c | serving: chờ đường nối BeaverX |
| M7 | Track record harness (CRPS/Brier) | M6 ✅ → làm được |

---

### 1.3. Dải sup-t đã nuốt phần lớn bài toán bội (mới v1.2)

Con số "≈4.500 t-test" ở v1.2 bản đầu **đếm sai bản chất**. Bội chia ba chiều, và chúng không cùng loại:

| Chiều | Số kiểm định | Xử lý |
|---|---|---|
| **Horizon** (h=0..24) | ×25 — **lớn nhất** | ✅ **Dải sup-t xử lý xong.** Đây chính là việc của nó: một hằng số `c` chung cho cả đường, bao phủ đồng thời toàn IRF ở mức danh nghĩa. Nhìn 25 horizon bằng dải pointwise thì ~2,5 điểm nằm ngoài **ngay cả khi mô hình đúng** |
| **Outcome** (8 biến) | ×8 | ❌ Còn lại. Holm hoặc Romano–Wolf giữa các outcome |
| **Thước đo shock** (§6.4) | ×3 nếu chọn A | ❌ Còn lại — nhưng nếu SHOCK là **trục báo cáo** thì đây là ba bảng riêng, không phải ba lần thử cùng một giả thuyết |

Vậy M10 thực chất chỉ còn: **hiệu chỉnh giữa các outcome**. Nhỏ hơn hẳn, và không cần SPA/StepM (thứ dành cho so sánh nhiều *chiến lược*) — Holm trên 8 outcome là đủ và không tự chế.

Việc còn phải quyết: **cái gì tính là một họ kiểm định** (§6.6).

## 2. PHASE 1 — "Công thức nói gì?" (≈2 tuần, bắt đầu ngay)

- [ ] **1a-0. Nền inference (M8+M9+M10) — LÀM TRƯỚC 1a.** Không có thì bảng γ ra bằng đúng cái inference mà registry nói là sai (`SCA-01.lp_inference`), và τ không chạy được. Đây là điều kiện kỹ thuật, không phải bậc tự do: ba thứ đều đã pre-register.
- [ ] **1a. Tier2 tháng đầy đủ:** SHOCK làm **trục báo cáo** (§6.4); **outcome = 4 kênh tài chính + freight + IP/CPI/kỳ vọng lạm phát**; tách ACT/THREAT; OLS + quantile τ∈{.10,.25,.50,.75,.90}; h=0..24; sup-t. **Kèm benchmark battery:** mọi hồi quy chạy hai bản — (a) GPR một mình, (b) GPR + EPU + WUI làm control. Hệ số sống sót ở bản (b) mới là đóng góp riêng của GPR. → `docs/reports/T2_full_*.md` — **bảng γ đầu tiên về hiện tượng**.

  Ba ràng buộc bắt buộc, phát hiện khi dựng loader (2026-07-21):
  1. **Bản a và b phải chạy trên CÙNG MẪU.** `epu_global` chỉ từ 1997; complete-case sẽ cắt panel về 1997+ trong khi bản (a) chạy 1990+. Nếu không ép cùng mẫu thì "hệ số GPR yếu đi khi thêm control" có thể chỉ là **đổi mẫu**, không phải battery ăn mất.
  2. **Control phải ĐỒNG THƯỚC ĐO với shock.** Shock LEVEL → EPU/WUI LEVEL; shock INNOVATION → EPU/WUI qua `shocks.innovation` cùng spec. So level-control với innovation-shock sẽ thổi phồng phần "riêng của GPR".
  3. **WUI publish theo QUÝ.** Join vào grid tháng để lại NaN 2/3 hàng và complete-case xóa 2/3 panel *trong im lặng*; forward-fill quý→tháng vi phạm #10. Nên `build_monthly_panel(battery=True)` cố ý **không** lấy WUI — runner phải xử lý tường minh ở tần suất của nó. Battery chạy thiếu WUI thì **ghi vào report**, không lặng lẽ bỏ.
- [ ] **1b. Cascade tier3 end-to-end, nước pilot Ba Lan hoặc Chile** (nhỏ, mở, dữ liệu công khai, ngoài lộ trình bán — không đốt out-of-sample của TH/ID/PH). Nhãn **PLUMBING** đầu report: mục tiêu là ba tầng ghép được, Shapley tổng 100%, căn thời gian đúng — không phải kết quả. → **bộ β/θ/λ đầu tiên**.
  - Phần GPR đã mở khóa: `build_monthly_panel(country="POL")`. **Còn thiếu chuỗi lợi suất thị trường pilot** (WIG / IPSA) — không có trên FRED, cần chốt nguồn. Đây là blocker thật của 1b, không phải code.
- [ ] **1c. Registry:** E1c/gold-set/lưới → `phase: refinement, non-blocking`; thêm `vn_market_series_missing`; thêm `pilot_market_series_missing`. **Mục "shock mặc định = LEVEL" tách ra thành quyết định §6.4 — chưa ghi vào registry cho tới khi chốt.**
  - Kèm theo: sửa `GATE_ELIGIBLE_SHOCK_TYPES` ở `scripts/run_tier2.py:76`. Hiện hard-code `{"innovation"}` → **mọi run LEVEL tự đóng dấu `INELIGIBLE`**, tức Phase 1a sẽ tự bác chính output của nó. Sửa cổng và sửa registry phải **cùng commit**, nếu không hai nguồn chân lý chỏi nhau.

**⛔ Cổng P1:** bảng γ tồn tại (cả hai bản a/b, **cùng mẫu**); cascade chạy hết không lỗi tích hợp; độ lớn effect thật được ghi — đầu vào cho mọi câu hỏi power sau này.

---

## 3. PHASE 2 — "Tin vào thì đo được gì?" — chân B (≈4–5 tuần)

Làm theo ECB, không sáng tạo hạ tầng. Phần riêng: **rubric cường độ ±1.0**.

- [ ] **2a.** Chốt 2 quyết định §6: 2 nguồn đầu; người chấm mẫu thứ hai.
- [ ] **2b.** P0: collector 2 nguồn + `statement_scorer` (encoder lọc → LLM, temp 0.1, JSON strict, trường `channel`) + bảng DB + card template thuần. Cổng: 20 phát ngôn thật, ≥16 điểm hợp lý.
- [ ] **2c.** Backfill (Trump 2015+, Fed/WH) + human audit 500 mẫu × 2 người → Krippendorff α ≥ 0.6.
- [ ] **2d.** `s_gpr.py` + `ladder.py` V1 + trigger rules (J đuôi, chuyển bậc, phân vị 90, im lặng kéo dài ở bậc cao).

### 3.1. ⚠️ CỔNG CONTAMINATION (mới v1.1 — bắt buộc, chạy trong 2c)

**Vấn đề:** backtest/chấm điểm lịch sử bằng LLM chịu look-ahead bias khi giai đoạn chấm chồng lấn cửa sổ huấn luyện — model có thể "chấm" một phát ngôn 2018 bằng hồi ức về kết cục của nó, và rò rỉ hậu-sự-kiện trong pre-training thổi phồng hiệu năng đo được (Glasserman–Lin 2023; Sarkar–Vafa 2024). Human audit KHÔNG bắt được — người chấm cũng biết lịch sử; α cao ≠ không nhiễm. Các cách chữa đơn giản đã bị kiểm chứng là không đủ: masking tên có tác dụng với headline nhưng LLM nhìn xuyên anonymization trong văn bản dài; lệnh prompt "chỉ dùng thông tin trước ngày X" vẫn rò rỉ; snapshot model theo mốc thời gian an toàn nhưng đắt.

**Quy tắc chốt:**
1. Prompt scorer ghi tường minh: chấm **văn bản phát ngôn**, không chấm hậu quả; không tham chiếu sự kiện sau `published_at`.
2. **Kiểm định pre/post-cutoff:** so phân phối điểm + hành vi scorer trên phát ngôn trước vs sau training cutoff của model chấm. Lệch hệ thống (vd `commitment` trước cutoff cao bất thường ở các đe dọa về sau thành hiện thực) → cờ contamination, ghi report.
3. **Mọi claim dự báo của chân B — gồm KĐ8 — chỉ kiểm trên dữ liệu SAU training cutoff của model chấm.** Backfill trước cutoff chỉ dùng cho mô tả, hiệu chuẩn phân vị, và analogue — trần claim `measurement`/`association`, ghi rõ trong mọi report.
4. `model_version` + cutoff date của scorer vào metadata mọi bảng điểm.

**⚠️ Điểm yếu của quy tắc 2 (ghi ra để không tự lừa):** so phân phối điểm trước vs sau cutoff **lẫn contamination với thế giới thật đổi** — giọng điệu địa chính trị 2015–2020 vốn khác 2024–2026, nên lệch phân phối là kết quả mặc định chứ không phải bằng chứng nhiễm. Thiết kế có sức phân biệt hơn: **giữ văn bản cố định, chỉ đổi cái model được biết**. Chấm cùng một phát ngôn hai lần — lần hai với prompt tiết lộ kết cục thực tế; độ lệch điểm đo **trần của kênh contamination**. Gần 0 → kết cục không lay được điểm, rò rỉ pre-training khó gây hại. Lớn → điểm nhạy với hiểu biết kết cục, và quy tắc 3 là bắt buộc chứ không phải phòng xa.

### 3.1b. ⛔ VA CHẠM: cổng contamination × split khóa cứng (mới v1.2)

Chưa văn bản nào bắt cái này. §3.1.3 nói claim dự báo chân B chỉ kiểm **sau training cutoff của scorer**. GPT-4o-mini cutoff ≈ 10/2023 → post-cutoff = **2024 trở đi**. Nhưng `config/backtest.yaml` khóa: Pseudo-OOS **2024–2025**, Final holdout **2026-H1**.

**Hệ quả:** cửa sổ duy nhất sạch để test dự báo chân B **chính là** pseudo-OOS + holdout. Chân B **không còn development window nào**. Và KĐ8 trên track tháng còn ~24 quan sát — không đủ power cho bất cứ kết luận nào.

Đây là ràng buộc số học, không phải chi tiết thủ tục. Ba lối ra, **phải chọn trước khi 2c chạy** (§6.5):

| | Lối ra | Đánh đổi |
|---|---|---|
| (i) | KĐ8 đánh ở tần suất **ngày/tuần** thay vì tháng | 2024–2025 cho ~500 quan sát thay vì 24. Nhưng chân B daily cần collector chạy dày hơn |
| (ii) | Tuyên bố 2024–2025 là **development window của chân B**, claim dự báo chân B hoãn tới khi 2026-H2+ tích lũy đủ | Trung thực nhất, chậm nhất. Trần claim chân B = `measurement`/`association` trong v1 |
| (iii) | Dùng scorer có cutoff **sớm hơn** để 2021–2023 thành post-cutoff sạch | Phải tìm model đủ tốt mà cutoff đủ cũ; đánh đổi chất lượng chấm lấy sạch thời gian |

Khuyến nghị: **(i) + (ii)** — chạy KĐ8 ở daily/weekly để có power, đồng thời ghi trần claim chân B ở `predictive, chưa xác nhận holdout` cho v1. Ghi vào `g0_governance.md` **trước** khi 2c chạy.

### 3.2. KĐ8 viết lại (mới v1.1)

Cũ: "S-GPR có dẫn trước GPR không". Mới: **"S-GPR có thêm thông tin ngoài battery GPR + EPU + WUI không"** — đo incremental đúng nguyên tắc #6, trên cửa sổ post-cutoff theo §3.1.3. Nhiều đội đã có chỉ số; giá trị của mình phải đo so với của họ, không so với zero.

**⛔ Cổng P2:** Measurement Card thật < 3 phút từ phát ngôn thật; α ≥ 0.6; cổng contamination §3.1 đã chạy và ghi report.

---

## 4. PHASE 3 — "Nhận định ra sao?" — ghép sản phẩm (≈4 tuần)

- [ ] **3a.** `analogue.py`: kho episode chân A 1985+, k-NN, loại ±30 ngày, n<5 im lặng, luôn liệt kê episode, `available_at ≤ t`.
- [ ] **3b.** Composer LLM + **guard P1** (mọi số khớp payload — chặn cứng; tiền lệ lỗi "1.8× vs 2.77×" đã xảy ra trong chính repo) → **Model Brief đầu tiên**: γ Phase 1 + analogue + đo lường Phase 2.
- [ ] **3c.** Serving tối giản: FastAPI + Kafka → BeaverX agents; feed card + trang episode.
- [ ] **3d.** Track record harness — chấm CRPS/Brier từ brief đầu tiên, lịch sử công khai.
- [ ] **3e.** Nối VNINDEX → tier3 VN (lợi suất tích lũy k≥3 ngày vì biên độ 7%) → **Country Transmission VN v0**.

**⛔ Cổng P3:** một brief đủ 4 tầng claim; 0 số bịa / 200 card; VN có β/θ/λ.

---

## 5. PHASE 4 — Refinement (song song/sau, KHÔNG chặn launch)

- Gold set → E1c-exo → lưới SCA (chạy bằng `arch`); power study tại effect thật đo từ Phase 1.
- **Khối phản hồi chính sách VN — spec đổi (mới v1.1):** nhận dạng kiểu GSS trong docs/11 §5.6 cần thị trường phái sinh lãi suất quanh cửa sổ công bố — **VN không có**. Thay bằng công thức Aruoba–Drechsel: NLP trên văn bản chuẩn bị/công bố quyết định chính sách để bắt information set, ML dự đoán thay đổi lãi suất có điều kiện trên information set đó, phần dư = cú sốc chính sách; phương pháp này cho IRF nhất quán đồng thuận lý thuyết và cú sốc không nhiễm information effect. Chỉ cần văn bản có timestamp (thông cáo SBV, nghị quyết CP) — cộng hưởng trực tiếp với V-phase corpus tiếng Việt. `surprise.py` viết theo spec này.
- V-phase corpus tiếng Việt (nuôi cả λ lẫn khối chính sách); nguồn B5–B8 + GDELT; mở rộng nước (TH/ID/PH — mỗi nước qua cổng Granger block-exo trước).

---

## 6. QUYẾT ĐỊNH CẦN BẠN CHỐT

§6.1–6.3 chặn **Phase 2**. §6.4 chặn **Phase 1a + 1c** (gấp hơn). §6.5 chặn **2c**. §6.4 và §6.5 ghi song song ở `g0_governance.md` §7 — đó là bản có ô ký chốt.

1. **2 nguồn đầu:** đề xuất Trump + MOFA CN (trục Mỹ–Trung/thương mại — kênh chi phối VN). Đổi MOFA → Fed nếu ưu tiên trục lãi suất.
   **✅ CHỐT 2026-08-02 (user ủy quyền): Trump (Truth Social/Twitter Archive, B4) + MOFA CN (B5)** — theo đề xuất; trục Mỹ–Trung/thương mại là kênh chi phối VN.
2. **Người chấm mẫu thứ hai** (500 mẫu, độc lập) — không có thì không claim được `measurement`.
   **⏳ VẪN MỞ** — cần một CON NGƯỜI thật, không ủy quyền cho máy được. Đây là blocker Phase-2 duy nhất còn lại về phía nhân sự; scorer/module đã sẵn.
3. Xác nhận: bỏ tín hiệu giao dịch (coi như chốt trừ khi bạn đảo) — `config/backtest.yaml` đánh dấu ngủ đông, ghi chú split 4 tầng vẫn hiệu lực cho track E.
   **✅ CHỐT 2026-08-02: bỏ tín hiệu giao dịch.** Không sửa `config/backtest.yaml` (bị test khóa; split 4 tầng vẫn hiệu lực cho track E) — trạng thái ngủ đông ghi ở đây + `g0` §2 là đủ.

### 6.4. SHOCK mặc định — LEVEL, hay để làm trục? (mới v1.2, **chặn 1a + 1c**)

v1.1 §2 mục 1c ghi "shock mặc định = LEVEL" trong một ô checkbox, không có lập luận. Nó đụng vào ba chỗ đã khóa:

- **CLAUDE.md #9** nói thẳng đưa level vào hồi quy rồi gọi hệ số là "tác động của cú sốc" là **sai khái niệm**.
- **`scripts/run_tier2.py:76`** hard-code `GATE_ELIGIBLE_SHOCK_TYPES = {"innovation"}` → run LEVEL tự đóng dấu `INELIGIBLE`.
- **E0 tự nói** level là *ngoại lệ có chủ đích*: "áp cho spec CỦA TA, không áp khi tái lập spec người khác." v1.1 nâng ngoại lệ replication thành mặc định của nhà.

**Khuyến nghị: đừng chọn một — cho SHOCK làm TRỤC BÁO CÁO.** Bảng γ Phase 1a chạy cả `{LEVEL, INNOVATION, LEVEL+JUMP}`, báo cáo hết, không chọn. Lý do:

- Chi phí 3× trên LP rẻ; đây là bảng **mô tả**, không phải curve suy diễn.
- Gỡ blocker mà **không HARK** — E1→E1b→E1c đã kết luận `UNRESOLVED`; chọn một bây giờ là chốt bằng thẩm quyền chứ không bằng bằng chứng.
- `SCA-01.primary_cell.shock` **vẫn để UNRESOLVED**, chờ E1c-exo. Curve suy diễn và bảng mô tả là hai việc khác nhau; docs/12 vốn đã cho SHOCK là chiều lưới.
- Nếu ba thước đo cho cùng một câu chuyện → kết luận bền, mạnh hơn nhiều so với chọn trước một cái.

Nếu bạn vẫn muốn LEVEL làm mặc định nhà: phải sửa **CLAUDE.md #9 kèm trong cùng commit** và sửa cổng máy, không để hai văn bản chỏi nhau.

### 6.5. Chân B mất development window (§3.1b) — chọn (i)/(ii)/(iii)

Chặn 2c. Xem bảng §3.1b. Khuyến nghị (i)+(ii).

### 6.6. "Họ kiểm định" của bảng γ là gì? (mới v1.2, **chặn M10 → 1a**)

Sau khi sup-t nuốt chiều horizon (§1.3), chỉ còn hiệu chỉnh giữa **outcome**. Nhưng hiệu chỉnh trên họ nào thì thay đổi kết luận:

| | Họ | Hệ quả |
|---|---|---|
| A | **Một họ = một outcome** (không hiệu chỉnh chéo outcome) | Lỏng nhất. Bào chữa được nếu mỗi outcome là một câu hỏi riêng đã đăng ký trước |
| B | **Một họ = một nhóm outcome** (asset_price / real_macro / physical) — khớp `SCA-01.report_axis_outcome` | Holm trong nhóm: 4 / 3 / 1. Nhất quán với trục báo cáo đã pre-register |
| C | **Một họ = toàn bảng γ** (8 outcome) | Chặt nhất, khó tìm được gì sống sót |

**Khuyến nghị: B.** `SCA-01.report_axis_outcome` đã chia ba nhóm đó **trước khi nhìn kết quả** và lý do chia là kinh tế (giá tài sản phản ứng theo phút, vĩ mô thực theo quý) chứ không phải để dễ qua ngưỡng. Dùng lại ranh giới đã pre-register là cách duy nhất không tự chọn họ sau khi thấy p-value.

**Chốt: B** · **Người:** user (ủy quyền, phiên 2026-08-02) · **Ngày:** 2026-08-02 · Họ = `multiplicity.PREREGISTERED_OUTCOME_FAMILIES` (4/3/1, lấy nguyên văn từ `SCA-01.report_axis_outcome`); Holm trong họ, ghi chú conservative khi outcome tương quan mạnh; kiểm tại **focal horizons đã pre-register** ({1,2,6} tháng), không quét horizon (sup-t đã lo chiều đó).

---

## 7. VIỆC KHÔNG LÀM (chốt)

Không thước đo shock mới · không chẩn đoán E1x mới · không tự chế bootstrap/hiệu chỉnh (`arch` hoặc không gì) · không tín hiệu giao dịch · không chạm holdout ngày ngoài 1 lần đã định, track tháng đã tuyên bố chưa có holdout · không để LLM sinh số, chấm gate, chọn spec · **không claim dự báo từ dữ liệu chấm trước cutoff của scorer** (§3.1.3).

---

## 8. ĐỊNH NGHĨA HOÀN THIỆN v1

Một phát ngôn thật lúc 14:07 → Measurement Card 14:10. Cuối tháng → Model Brief với γ thật (sống sót qua battery), phân phối thật, analogue kiểm chứng được. VN có β/θ/λ riêng. Track record công khai chấm được ≥1 chu kỳ. Cổng contamination đã chạy. Mọi thứ khác là nâng cấp.

**Tuần này:** 1a-0 (M8+M9+M10 — nền inference, không chờ ai) → 1a · bạn chốt §6.1–6.2 và **§6.4** (§6.4 chặn 1a/1c).

---

## 9. NHẬT KÝ THI CÔNG

**2026-07-21 — M0 + mở khóa 1b** (`data_files.py`, `tests/econ/test_real_macro_battery.py`, 108 test pass):
- `load_real_macro_monthly` / `transform_real_macro` — IP, CPI, kỳ vọng lạm phát. `ip = 100·Δln(INDPRO)` **đúng transform E0 đã validate**; lệch transform là mất luôn giá trị cổng E0 (hệ số 1a không so được với replication đã PASS). `infl_exp` đi **sai phân** chứ không phải mức (#9 — khảo sát dai dẳng như us10y).
- `load_benchmark_monthly` / `transform_benchmark` — EPU US + Global qua FRED, `log1p` cùng quy ước GPR. WUI phải tải tay về `data/wui_global.csv` (như `gold_events.csv`), thiếu thì bỏ qua chứ không bịa chuỗi thay thế.
- `load_gpr_monthly(country=)` + `build_monthly_panel(country=)` — mở khóa Phase 1b. Trước đó `keep = ["month","GPR","GPRC_VNM"]` hard-code VNM.
- Test khóa máy cho **nguyên tắc #8**: `test_panel_country_switch_changes_only_lambda_column` — đổi nước chỉ được đổi cột λ, oil/dxy/vix/us10y/GPR_INNOV phải trùng khít giữa hai nước.
- ⚠️ Hai bẫy chặn được lúc viết, đã ghi vào §2 1a: WUI quý → xóa 2/3 panel trong im lặng; `epu_global` 1997+ → bản a/b khác mẫu.

**2026-07-21 — M8 + M9** (`local_projection.py`, `tests/econ/test_lp_inference.py`, 121 test pass):
- `inference="lag_augmented"` (MO-PM 2021) — tự thêm lag của **cả y lẫn shock**, dùng **HC1 thay HAC**. Mặc định vẫn là `"hac"` nên mọi report đã sinh không đổi.
  - **Điều kiện then chốt, dễ làm sai:** phải có lag của **SHOCK**, không chỉ lag của y. Thiếu nó thì regressor chưa được partial-out thành innovation và cơ sở bỏ HAC sụp đổ. `tier2_global_macro` hiện chỉ thêm lag của y (`macro_lags`) — nên **đừng tự ghép tay**, để `run_local_projection` tự thêm.
  - **Liên quan §6.4:** lag augmentation chính là thứ làm `shock=LEVEL` biện minh được — nó partial-out phần đã dự báo được của level ngay trong hồi quy, nên hệ số đọc được là phản ứng với phần *bất ngờ*. Đây là lý lẽ kỹ thuật ủng hộ lựa chọn A ở §6.4.
- `simultaneous=True` — dải sup-t (MO-PM 2019), ước lượng Ω bằng **hàm ảnh hưởng**, không bootstrap. Đường chéo của ma trận đó **chính là** HC1, nên SE pointwise và dải sup-t đến từ cùng một nguồn; `test_supt_diagonal_matches_hc1` khóa điều đó — nếu lệch thì report chứa hai bộ sai số chuẩn khác nhau mà không ai thấy bằng mắt. `seed` cố định để con số tái lập được (#4).
- `method="quantile"` — τ bất kỳ. `simultaneous=True` + quantile → **NotImplementedError** thay vì trả dải sai: hàm ảnh hưởng của QuantReg cần ước lượng sparsity tại τ, dùng công thức OLS ở đó sẽ cho dải sai mà không phát hiện được. Đường đúng là bootstrap, để M10.
- 💡 **Phát hiện làm nhỏ M10:** sup-t đã xử lý xong chiều horizon (×25, chiều bội lớn nhất). M10 chỉ còn hiệu chỉnh giữa outcome — xem §1.3.

**2026-08-02 — M10 + NỐI M8/M9 vào cascade** (`multiplicity.py`, `local_projection.py`, `tier2_global_macro.py`, `tier3_country.py`, 2 file test mới):

- **M10 xong ở phần KHÔNG chờ chữ ký.** `econometrics/multiplicity.py`: `holm()` (step-down, FWER dưới phụ thuộc **bất kỳ** — không giả định gì, không cần bootstrap) + `holm_by_family()`. `PREREGISTERED_OUTCOME_FAMILIES` = đúng ba nhóm `SCA-01.report_axis_outcome` (4/3/1), để **sẵn** cho lựa chọn B nhưng **KHÔNG phải mặc định**: `family` là tham số bắt buộc. Chọn họ sau khi nhìn p-value chính là HARKing mà registry sinh ra để chặn, nên chữ ký §6.6 vẫn là thứ mở khóa, không phải code.
  - Không dùng `arch`/SPA/StepM: chúng dựng cho so nhiều **chiến lược** với một benchmark và cần bootstrap ma trận lỗi. Ở đây m=3..8 và cái cần là FWER không giả định phụ thuộc. Holm conservative khi outcome tương quan mạnh (oil/dxy/vix/us10y chắc chắn có) — **đánh đổi đã biết, ghi vào report**, không đổi sang thủ tục lỏng hơn sau khi thấy p-value.
  - Test khóa: họ phải **phân hoạch** + **phủ hết** (bỏ im lặng một outcome = làm nhẹ FWER mà report không ghi); B phải lỏng hơn C, nếu không thì §6.6 không phải một quyết định.

- **⛔ Phát hiện chặn 1a mà v1.2 §1.1 chưa ghi: M8/M9 KHÔNG với tới được từ cascade.** `estimate_tier2`/`estimate_tier3` gọi `run_local_projection` mà không truyền `inference`/`simultaneous`/`method`/`tau`/`lags`, và `estimate_tier2` lọc cột đầu ra bằng danh sách cứng nên nuốt luôn cột sup-t. Tức là bảng γ 1a chỉ chạy được bằng **đúng cái inference mà `SCA-01.lp_inference` nói là sai** — M8/M9 tồn tại ở mức hàm nguyên thủy nhưng chết ở mức deliverable. **Đã nối**, mặc định giữ nguyên `hac`/OLS/không sup-t nên report cũ không đổi.
  - Kèm cổng: `inference="lag_augmented"` + `macro_lags>0` → **raise**. Lag augmentation tự thêm lag của y (=M); giữ `macro_lags` sinh cột lag **trùng khít**, `pinv` không báo lỗi mà chia đôi hệ số giữa hai cột giống hệt nhau và SE mất nghĩa — hỏng im lặng, đúng loại lỗi khó thấy nhất trong report.

- **Hai lỗ im lặng trong khối sup-t, sửa luôn:**
  1. `simultaneous=True` + `inference="hac"` **chạy được** và trả `beta ± c·se_HAC` — hằng số `c` lấy từ ma trận hiệp phương sai EHW, độ rộng lấy từ SE HAC. Đúng cái lỗi "hai bộ SE trong một report" mà `test_supt_diagonal_matches_hc1` sinh ra để chặn, chỉ khác là nó lọt vì hai nguồn nằm ở hai dòng code. Giờ **raise** (docs/15 §5 mục 4 — nhưng nó là lỗi đúng/sai, không phải "1 dòng guard").
  2. `simultaneous=True` + `return_all=True` **tính psi xong rồi vứt**: nhánh `return_all` return trước khối sup-t. Đó chính là đường tầng 3 đi. Giờ trả dải cho **mọi** hệ số, mỗi hệ số một `supt_c` **riêng** — β/θ/λ có ma trận tương quan qua horizon khác nhau, dùng chung một hằng số là áp đặc tính hệ số này lên hệ số kia.

**2026-08-02 (chiều) — M4 phần MODULE: chân B hết stub trên đường LLM** (`statement_scorer.py`, `s_gpr.py`, `ladder.py`, `config/ladder_v1.yaml`, 40 test mới, 182 pass):

- `scoring/statement_scorer.py` — pipeline 2 tầng ECB (encoder tiêm vào, ngưỡng 0.6 → LLM temp 0.1, **JSON strict**: sai key/miền/kiểu là từ chối, không sửa hộ — LLM sinh số ngoài schema bị chặn từ parse). Prompt = rubric docs/00 §2.3 + **quy tắc contamination §3.1.1 viết thẳng vào prompt**; `training_cutoff` là tham số **bắt buộc** (§3.1.4). Versioning 5 trục (model/rubric/prompt/temperature/content-hash) vào từng hàng điểm; cache theo hash — đổi trục nào điểm cũ tự vô hiệu. Actor lấy từ **metadata nguồn**, LLM chỉ fallback (docs/00 §2.1). Guard #5: nguồn daily mà `published_at` đúng 00:00:00 → raise (cột date bị ép kiểu). Client OpenAI lười-import; test toàn fake, không mạng.
- `indices/s_gpr.py` — công thức §2.5 nguyên văn: hai chiều S-GPR/S-CONC **không net**; `w(role)` = `DEFAULT_ROLE_WEIGHTS_INIT` (đúng nghĩa INIT, #7 — role lạ raise chứ không gán ngầm); chuẩn hóa nhịp đăng nguồn; global **bắt buộc** trade_weights phủ hết pair. `expanding_percentile` **strict `<`** — định nghĩa `<=` trên chuỗi zero-inflated (JUMP) cho ngày im ắng percentile ~100, trigger nổ mỗi ngày; test khóa.
- `econometrics/ladder.py` + `config/ladder_v1.yaml` — V1 rule-based, ngưỡng **trong config version-hóa** (đổi ngưỡng = version mới), `config_version` theo từng hàng. NaN = không thỏa (thiếu bằng chứng thì không leo bậc). Chưa có GDELT: S4 vẫn bắt qua JUMP chân A (`mode: any`), **S2 không bắt được** — ghi trong config thay vì hạ ngưỡng. S1/S3 chưa có ngưỡng trong docs/00 §4.1 — chờ chốt, không tự bịa. `ladder_transitions` = trigger "chuyển bậc" cho tầng 4.
- Test tích hợp `test_chain_b_pipeline.py`: tái hiện ví dụ docs/15 §2 (Trump 14:07) — phát ngôn → điểm → S-GPR 7d (=0.782 tính tay) → percentile → S4 + trigger up; mọi số trong payload truy về hàm+input.
- ⚠️ Phát hiện ghi `docs/15` §6.2b: **hai taxonomy kênh chỏi nhau** (docs/00 6 kênh vs docs/14+15 "4 kênh"); mapping 6→4 chỉ điền cặp hiển nhiên, còn lại `None` chờ chốt.

**2026-08-02 (tối) — KÝ 4 QUYẾT ĐỊNH + M1: BẢNG γ ĐẦU TIÊN TỒN TẠI** (`shock_axis.py`, `run_t2_full.py`, registry `decisions`, 193 test):

- **Chữ ký** (user ủy quyền theo đúng khuyến nghị đã ghi sẵn, không thêm quyết định mới): §6.4/`g0` §7.1 → **A** · §6.6 → **B** · `g0` §7.2 → **(i)+(ii)** · §6.1 → **Trump + MOFA CN** · §6.3 → **bỏ tín hiệu giao dịch**. Ghi `decisions:` trong registry + khóa máy (`test_signed_decisions_locked`) — rút lại chữ ký cũng phải đi qua commit có chủ đích. §6.2 (người chấm thứ hai) **vẫn mở** — cần con người.
- **`econometrics/shock_axis.py`** — cổng máy của quyết định A: `gate_shock_eligibility(measure, inference)`. LEVEL/LEVEL+JUMP **chỉ eligible với `lag_augmented`**; đó là điều kiện làm A không phá #9 (lag augmentation partial-out phần dự báo được ngay trong hồi quy → hệ số đọc được là phản ứng với phần *bất ngờ*). `run_tier2.GATE_ELIGIBLE_SHOCK_TYPES` giờ **sinh ra từ cổng** thay vì gõ tay — vẫn `{"innovation"}` vì runner đó chạy `hac`, nên report cũ không đổi.
- **`data_files`: trục SHOCK ở track tháng** — `build_monthly_shock_axis()` + `build_monthly_panel(shock_axis=True, components=True)`. Thêm GPRA/GPRT → `GPR_ACT`/`GPR_THREAT` (tách kênh thô giai đoạn 1, không cần chân B). JUMP tháng dùng cửa sổ **120 tháng** (min_periods 60): chuyển 250-phiên-daily thành 12 tháng là vô nghĩa — q95 trên 12 điểm gần như là max.
- **`scripts/run_t2_full.py` — Phase 1a chạy xong.** → `docs/reports/T2_full_f2579b30928f.md`. 3 thước đo × 3 kênh × 8 outcome × 2 bản battery × h=0..24 = **3600 hàng γ**, + 6000 hàng phân vị. Battery **đồng thước đo** với shock (ràng buộc §2 1a #2: EPU đi qua chính `build_monthly_shock_axis`, không so LEVEL-control với INNOVATION-shock).

  **⛔ Chi phí mẫu, phải biết trước khi đọc:** một mẫu duy nhất 2007-02 → 2026-06, **n=231 tháng**. LEVEL+JUMP ăn 120 tháng warmup, EPU global chỉ từ 1997 → giao là 2007. Đây là giá của việc bắt bản a/b **và** ba thước đo so được với nhau; trộn mẫu thì "hệ số yếu đi khi thêm control" có thể chỉ là đổi mẫu.

  **Kết quả (chưa human review):** 432 kiểm định focal, 34 có p thô <0.10, **15 sống sót Holm** (bản b: 9). Sống sót tập trung ở **vĩ mô thực + kênh vật lý**; **giá tài sản 0/4 ở cả ba thước đo**. Ô đồng thuận cả ba thước đo: **GPR_ACT → IP, h=2, dấu âm** (LEVEL β=−0.77 p=0.017 · INNOVATION β=−0.74 p=0.017 · LEVEL+JUMP β=−0.11 p=0.031), sống sót battery. Đó là **cùng hiện tượng E0 replication** (C-I 2022: GPR→IP giảm h=1,2) nhưng trên mẫu khác, suy diễn khác, và giờ biết là **ACT chứ không phải THREAT**.
- **Lỗ im lặng thứ ba đã bịt:** QuantReg (IRLS) không hội tụ thì statsmodels chỉ `warn` rồi **trả hệ số vòng lặp cuối** — số chạy thẳng vào bảng, warning bay lên stderr rồi mất. `run_local_projection` giờ bắt lại thành cột `converged`; **386/6000** hàng phân vị rơi vào đó, bảng in `‡` thay vì số.
- **1c registry:** SCA-01 thêm `phase: refinement, blocking_launch: false` (blockers giữ nguyên — hạ ưu tiên KHÔNG phải gỡ cổng); thêm `data_blockers` (gold_events, wui_global, vn/pilot market series).

**2026-08-03 — AI-GPR xuất hiện (`docs/16`); phản biện §2.1 + spec kép + loader** (`run_e2_component_check.py`, `shocks.delta_decomposition`, `shock_axis`, `data_files.load_ai_gpr_daily`, 216 test):

- **`docs/16` §2.1 tự đính chính sau khi kiểm bằng dữ liệu của dự án.** Doc lập luận: bài AI-GPR thấy hệ số phần *persistent* lớn gấp đôi phần *shock*, nên lag-augmented LP (và `INNOVATION`) chỉ bắt được "nửa yếu". E2 (`docs/reports/E2_component_decomposition_e73a0a307fc3.md`) tách rõ hai chuyện:
  - **Cơ chế ĐÚNG, đã tái lập:** dưới lag augmentation, `corr(β_LEVEL, β_INNOVATION) = 0.9985` — LEVEL bị residual hóa thành đúng phần bất ngờ (FWL), hai cái gần như là một.
  - **Kết luận định lượng KHÔNG đứng:** hai hệ số nằm trên hai regressor có `Var(fitted)/Var(resid) ≈ 0.11` nên **không so được ở dạng thô**. Chuẩn hóa (β×sd) thì thứ tự **đảo** ở ô chính, và **22/45 ô (48.9%)** đảo chiều kết luận. Cùng tai nạn thang đo mà registry đã ghi cho `LEVEL+JUMP`.
  - **Hệ quả:** câu "dùng INNOVATION nên G2a mới yếu" không đứng — trong `T2_full`, LEVEL cũng cho **0/4 giá tài sản** y hệt, vì dưới lag-aug hai cái là một.
  - ⚠️ E2 chạy GPRD **tháng**, bài chạy AI-GPR **tuần** (dai hơn → R² cao hơn → có thể không đảo). E2 bác **cách đọc bảng khi chưa chuẩn hóa**, không bác số của bài.
- **Spec kép §2.2 sống sót nguyên vẹn — nó là lối ra đúng**, vì giải tán luôn câu hỏi "thành phần nào mạnh hơn". `shocks.delta_decomposition`: `Δ LEVEL = ANTICIPATED + SURPRISE`, trong đó **SURPRISE ≡ `innovation()` đã có** (vì `Ê[Δlevel] = Ê[level] − level₋₁`), nên ANTICIPATED lấy bằng hiệu → hai thành phần cộng lại bằng **đúng** Δ LEVEL theo đồng nhất thức, không thể lệch do hai đường ước lượng. Phân rã trên **sai phân** chứ không trên mức (`persistent_ar` = Ê[LEVEL] gần nghiệm đơn vị — đưa vào hồi quy là quay lại đúng vấn đề #9).
- **Cổng NHÃN** (`shock_axis.check_component_labelling`): spec kép không phá #9 nhờ *cách gọi tên*, không nhờ công thức. Gọi β_ANTICIPATED là "cú sốc" → raise. Guard P1 cho **nhãn** thay vì cho **số**.
- **`load_ai_gpr_daily()`** theo khuôn file tải tay: thiếu file → lỗi kèm hướng dẫn + lý do không tự fetch (#4); thiếu cột → raise (thiếu threats/acts mà bỏ qua thì mọi tách ACT/THREAT sau đó chạy trên dữ liệu rỗng). `AI_GPR_COLUMNS` là schema **giả định**, `describe_ai_gpr_file()` để đối chiếu lần tải đầu.
- **Governance:** `DEC-2026-08-03-dual-component` amend `DEC-2026-08-02-shock-axis` (trục SHOCK chính → robustness), **giữ** điều kiện `lag_augmented`. `primary_cell.shock` **vẫn UNRESOLVED** — chốt nó bằng spec kép là chốt bằng *thiết kế* chứ không bằng E1c-exo; khóa bằng test. `docs/16` §9.1 ghi thủ tục; v1.0 của doc đó nói nhầm "ba chữ ký" và "không đổi".

**2026-08-03 (tối) — M5 + M6: TẦNG 4 CÓ THÂN** (`analogue.py`, `reporting/{guard,composer}.py`, 263 test):

- **M5 `econometrics/analogue.py`** — k-NN cosine trên descriptor pre-register (docs/11 §6). Bốn ràng buộc của §6 đều dựng thành **cơ chế**, không phải lời hứa trong docstring:
  1. `n<5` → `InsufficientAnalogues` (im lặng, cổng P3) — hạ ngưỡng để có số là biến "không biết" thành "biết mơ hồ";
  2. IQR đổi dấu → `dispersed=True`, `describe()` nói "phân tán, không kết luận" và **không** đưa trung vị ra một mình;
  3. `episode_table()` luôn liệt kê được — tính kiểm chứng là điểm bán hàng chính;
  4. `available_at ≤ t` **kể cả trong retrieval**: ứng viên phải nằm trước `as_of` **và** đã diễn biến xong tới `as_of`. Lấy episode cách 3 ngày rồi đọc kết cục h=30 của nó là look-ahead trá hình — test khóa riêng.
  - z-score/percentile trong descriptor dùng **expanding**, không phải toàn mẫu: chuẩn hóa toàn mẫu làm descriptor 1990 mang thông tin 2026 và "giống nhau" thành giống theo tương lai.
  - Claim ceiling `association`, in trong chính câu `describe()`.
- **M6 `reporting/guard.py`** — Guard P1 thành **module dùng chung chạy ở RUNTIME**, không còn là test rời chép lại logic ở mỗi script. `NarrativeBuilder.render()` là **cửa duy nhất** lấy text ra ⇒ quên gọi guard là không thể. Ba thứ guard **không** làm (ghi rõ để không tạo an toàn giả): không kiểm số đúng/sai, không hiểu ngữ nghĩa, không bắt số bị bỏ sót.
- **M6 `reporting/composer.py`** — Measurement Card + Model Brief, **ba lớp bảo vệ bắt ba loại lỗi khác nhau**: Guard P1 bắt **số** bịa · `assert_claim_ceiling` bắt **từ ngữ** vượt mức nhận dạng (không số nào sai — "IP dự kiến giảm" là nhảy `measurement`→`prediction` chỉ bằng một động từ) · `check_component_labelling` bắt việc gọi ANTICIPATED là cú sốc.
- **Ba lỗi thật do guard chặn ngay khi viết composer** — đều là loại đáng chặn:
  1. `sample_note` là **văn xuôi tự do mang số** → đổi thành trường số `n_obs`. Số trong câu văn không đối chiếu được với payload; đó chính là thứ P1 sinh ra để cấm.
  2. `batch_analogues` trả **chuỗi** lý do bỏ qua → đổi thành **dict có cấu trúc** `{outcome, horizon, n_found, n_required}`, và `InsufficientAnalogues` mang theo số. Composer tự đặt câu từ các trường đó.
  3. Cổng claim bắt đúng **câu miễn trừ bắt buộc** của card ("KHÔNG phải dự báo") → thêm xử lý phủ định.
  - Guard cũng phải học không bắt nhầm: giờ gỡ giờ `14:07` và ngày `01/08`, nhưng pattern ngày yêu cầu tháng ≤12 nên tỉ lệ thật như `23/72` **vẫn bị kiểm**.

**Chưa làm, theo thứ tự:** ⛔ **tải dữ liệu AI-GPR + xác minh ghim vintage được** (chặn cả Phase 1 còn lại của `docs/16` §9) · human review bảng γ + E2 · §6.2 người chấm thứ hai → 2c chân B · **M7 track record** (giờ làm được, M6 xong) · 1b cascade tier3 (chờ chuỗi thị trường pilot) · 3c serving (chờ đường nối BeaverX).