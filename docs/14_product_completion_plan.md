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
| M10 | **Kế hoạch bội.** `arch` chưa import ở đâu. ⚠️ **Phạm vi đã thu nhỏ nhiều nhờ M8** — xem §1.3 | định nghĩa "họ kiểm định" (§6.6) |
| M1 | Bảng γ thật (tier2 tháng đầy đủ chưa từng chạy) | M10 |
| M2 | Bộ β/θ/λ đầu tiên (tier3 chưa từng chạy dữ liệu thật) | nước pilot (không phải VN) |
| M3 | β/θ/λ cho VN | `VNINDEX` — đường nối BeaverX. Registry: thêm `vn_market_series_missing` |
| M4 | Chân B: collector + scorer + S-GPR + ladder | 2 quyết định §6 |
| M5 | Analogue retrieval | M1 |
| M6 | Composer + guard P1 + serving | M4, M5 |
| M7 | Track record harness (CRPS/Brier) | M6 |

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
2. **Người chấm mẫu thứ hai** (500 mẫu, độc lập) — không có thì không claim được `measurement`.
3. Xác nhận: bỏ tín hiệu giao dịch (coi như chốt trừ khi bạn đảo) — `config/backtest.yaml` đánh dấu ngủ đông, ghi chú split 4 tầng vẫn hiệu lực cho track E.

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

**Chốt:** _chưa điền_ · **Người:** _chưa điền_ · **Ngày:** _chưa điền_

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

**Chưa làm, theo thứ tự:** M10 (Holm giữa outcome — chờ §6.6) → 1a (chờ §6.4).