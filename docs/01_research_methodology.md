# KẾ HOẠCH NGHIÊN CỨU: LƯỢNG TỬ HÓA RỦI RO ĐỊA CHÍNH TRỊ CHO THỊ TRƯỜNG VIỆT NAM (VN-GPR)

**Phiên bản:** 1.1 — 07/2026
**Thay đổi v1.1:** (1) Lớp 1 thêm trường `origin` và `speaker`; (2) thêm Lớp 2b — chỉ số trọng số theo người phát ngôn (Actor-Weighted GPR); (3) Lớp 4 chuyển sang cấu trúc phân tầng với orthogonalization tách global/domestic; (4) thêm kiểm định lead-lag global→VN vào C2; (5) thêm Phần A6 — chiều ngược VN→thế giới như giả thuyết kiểm định.
**Mục tiêu:** Xây dựng chỉ số VN-GPR (LLM-based) từ báo chí tiếng Việt và mô hình đo tác động lên thị trường tài chính Việt Nam, với chuẩn kiểm định tương đương các mô hình đã validate trên S&P 500 — điều hiện chưa tồn tại cho thị trường Việt Nam.

---

## 0. ĐỊNH VỊ KHOẢNG TRỐNG NGHIÊN CỨU

Những gì thế giới đã có (làm nền tảng, không cần chứng minh lại):

| Thành phần | Nguồn | Trạng thái |
|---|---|---|
| GPR dictionary-based, 44 nước (có VN từ báo tiếng Anh) | Caldara & Iacoviello (2022, AER) | Published, audited |
| AI-GPR: LLM (GPT-4o-mini) chấm điểm 0.0–1.0 từng bài báo | Iacoviello & Tong (06/2026, working paper) | Published, human-validated (corr 0.88), false-discovery 12% vs 21% của keyword |
| Panel VAR + GPT/GPA + country FE trên inflation/GDP | Caldara, Conlisk, Iacoviello, Penn (2026, JIE) | Published |
| TVP-VAR connectedness: GPR/EPU 10 đối tác → VN-Index | Cao & Vo (2025, Heliyon) | Published; EPU giải thích 42.45% vs GPR 18.80% biến động |
| Daily AI-GPR → US excess stock returns 1960–2026 | Iacoviello & Tong (2026) | Published; hiệu ứng mạnh và có ý nghĩa thống kê, keyword-GPR yếu hơn ~1/3 |

**Khoảng trống (đóng góp gốc của nghiên cứu này):**
1. Chưa ai xây GPR bằng LLM trên **báo chí tiếng Việt** (mọi chỉ số VN hiện có đều từ báo tiếng Anh nhìn VN từ bên ngoài → mù với tín hiệu chính trị nội địa).
2. Chưa ai backtest tín hiệu GPR **daily** trên VN-Index/VND/nhóm cổ phiếu xuất khẩu theo chuẩn out-of-sample như đã làm với S&P 500.
3. Chưa ai tách GPT/GPA (threats vs acts) cho thị trường VN.
4. Chưa ai đo bilateral GPR (Mỹ→VN, TQ→VN) bằng trích xuất actor-target — kỹ thuật chỉ LLM làm được.

---

## PHẦN A — KIẾN TRÚC LƯỢNG TỬ HÓA (5 LỚP)

### Lớp 1: Bài báo → điểm số

```
s_i ∈ [0.0, 1.0] = f_LLM(text_i, rubric)
```

- Model: GPT-4o-mini (đúng model paper gốc dùng; đã có sẵn trong stack Vietstock enrichment), temperature = 0, zero-shot.
- Pre-filter bằng keyword tiếng Việt để giảm chi phí (chỉ đưa vào LLM các bài qua lọc sơ bộ), theo đúng kiến trúc 2 lớp của AI-GPR.
- Rubric chấm điểm (adapt từ paper gốc, cần dịch/hiệu chỉnh cho ngữ cảnh tiếng Việt):
  - 0.0 — không liên quan địa chính trị
  - 0.1–0.3 — nhắc đến gián tiếp, bình luận chung
  - 0.4–0.6 — căng thẳng cụ thể, đe dọa, đàm phán bế tắc (THREAT)
  - 0.7–1.0 — hành động thực tế: áp thuế có hiệu lực, xung đột, trừng phạt (ACT)
- Output có cấu trúc mỗi bài: `{score, type: THREAT|ACT|NONE, actor, target, channel: trade|military|sanction|diplomacy, origin: global|regional|domestic, speaker: {name, role}}`
  - `origin`: bài về sự kiện thế giới được báo VN đưa lại (`global` — vd Mỹ-Iran, Fed), sự kiện khu vực (`regional` — Biển Đông, ASEAN), hay thuần nội địa (`domestic` — nhân sự, chính sách trong nước). Trường này là nền tảng cho bước orthogonalization ở Lớp 4 — nếu không tách, VN-GPR sẽ bị "nhiễm" global GPR và model đếm trùng tín hiệu.
  - `speaker`: người/tổ chức phát ngôn chính trong bài (nếu có) và vai trò — vd `{Trump, US_president}`, `{Powell, Fed_chair}`, `{người phát ngôn BNG, VN_gov}`. Dùng cho Lớp 2b.
- Chi phí tham chiếu: paper gốc xử lý 4.6 triệu bài ~ $450 (~$0.0001/bài). Corpus VN ước tính nhỏ hơn nhiều.

### Lớp 2: Điểm số → chỉ số thời gian

```
VN-GPR_t = 100 × Σ(s_i, i ∈ D_t) / N_t
```
- N_t = tổng số bài trong kỳ (chuẩn hóa theo lượng tin chung).
- Tần suất: daily (chuẩn cho backtest tài chính) + monthly (đối chiếu macro).
- Rebase mean = 100 trên cửa sổ chuẩn (ví dụ 2015–2019, giai đoạn "bình thường" trước COVID).

Biến thể:
- `VN-GPR_domestic`: chỉ tính bài về chính trị/chính sách nội địa VN.
- `VN-GPR_external`: bài về rủi ro từ bên ngoài ảnh hưởng VN (Mỹ-Trung, Biển Đông, thuế quan).
- `BIGPR_{a→VN}`: bilateral, a ∈ {US, CN, ...} — dùng trường actor/target từ Lớp 1.

### Lớp 2b: Chỉ số trọng số theo người phát ngôn (Actor-Weighted GPR)

Cơ sở thực nghiệm (đã published, không phải giả thuyết):
- Tweet của Trump gây phản ứng đo được trong 30 phút trên S&P 500 (giảm giá, tăng volume, tăng VIX futures), mạnh nhất với tweet chứa "tariff"/"products"; hiệu ứng lan sang cả thị trường Đức, Pháp và tỷ giá, và **tăng theo mức độ chú ý dành cho người đăng** (Filbien et al.; ScienceDirect 2021, 2024, 2025). Sự kiện 2/4/2025: S&P 500 −11% trong 2 ngày sau công bố thuế quan.
- Phát biểu của Fed Chair tạo tail risk lớn hơn hẳn thành viên FOMC thường; độ lớn phản ứng phụ thuộc **vị trí/chức vụ** của người phát biểu (Econometrics 2024). Industry đã sản phẩm hóa: Hawkometer chấm mọi phát ngôn quan chức 9 NHTW theo thang ±10, tổng hợp voter-weighted.

Công thức:
```
AW-GPR_t = 100 × Σ(w_{a_i} · s_i, i ∈ D_t) / N_t
```
- `w_a` = trọng số người phát ngôn a. QUAN TRỌNG: không gán tay (không hard-code "Trump = 5x") — ước lượng từ dữ liệu bằng speaker fixed-effects: hồi quy phản ứng thị trường (return/volatility cửa sổ ngắn quanh thời điểm bài đăng) lên s_i × dummy_speaker, hệ số ước lượng được chính là w_a.
- Cấu trúc trọng số 2 chiều: `w_a = f(role, attention_t)` — role (tổng thống Mỹ > bộ trưởng > nghị sĩ; Fed Chair > thống đốc thường) là thành phần chậm; attention (mức độ được nhắc lại trên truyền thông tại thời điểm t) là thành phần nhanh, vì bằng chứng cho thấy tác động tăng theo attention chứ không cố định theo người.
- Danh sách actor tối thiểu cần theo dõi cho VN: Tổng thống Mỹ, USTR, Fed Chair, lãnh đạo Trung Quốc, Bộ Thương mại TQ, người phát ngôn BNG hai nước, và phía VN: Tổng Bí thư, Thủ tướng, Thống đốc NHNN, Bộ Công Thương.
- Kiểm định đi kèm (bắt buộc trước khi dùng): AW-GPR phải beat VN-GPR không trọng số về sức giải thích OOS; nếu không beat → trọng số là noise, quay về bản không trọng số.

### Lớp 3: Tách threats/acts

```
VN-GPR_t = VN-GPT_t + VN-GPA_t
```
Bắt buộc tách vì literature đã chứng minh: threat tác động dai dẳng (thị trường re-price dần), act chỉ tác động khi bất ngờ (phần dự đoán trước đã vào giá).

### Lớp 4: Chỉ số → tác động thị trường/kinh tế (CẤU TRÚC PHÂN TẦNG)

Cơ sở: literature xác nhận shock toàn cầu chi phối nền kinh tế nhỏ mở — trong hệ G7-BRICS, Mỹ/Đức/Ấn/Nga là nguồn spillover chính; kênh truyền dẫn mạnh nhất là năng lượng (dầu > khí > than, spillover chủ yếu tần số cao/ngắn hạn); GPR đánh vào EM mạnh hơn qua kênh rút vốn đột ngột → mất giá tiền tệ. Báo VN phần lớn đưa lại tin thế giới → VN-GPR thô bị nhiễm global GPR, bắt buộc tách trước khi hồi quy.

**Bước 4a — Orthogonalization (tách thành phần toàn cầu khỏi VN-GPR):**
```
VN-GPR_t = f̂(GPR_US_t, GPR_CN_t, GPR_global_t, Oil_t) + VN-GPR⊥_t
```
Hồi quy VN-GPR thô lên các GPR nguồn; phần dư VN-GPR⊥ là tín hiệu "thuần Việt Nam". Đối chiếu chéo với trường `origin` từ Lớp 1 (chỉ số xây riêng từ bài `domestic` phải tương quan cao với VN-GPR⊥ — nếu không, một trong hai bước đang sai).

**Bước 4b — Phương trình phân tầng (track tài chính, daily):**
```
r_{t+h} = α_h + Σ_j β_{j,h}·GPR_{j,t}          (shock nguồn: US, CN, RU, MidEast)
         + θ_1·ΔOil_t + θ_2·ΔDXY_t + θ_3·VIX_t  (kênh truyền dẫn toàn cầu)
         + λ_h·VN-GPR⊥_t                        (rủi ro riêng VN)
         + Φ·X_t + ε,   h = 1..60 ngày (Local Projection Jordà)
```
- **Cấu trúc transmission (xem `docs/06`, `docs/07_formulas_reference_v2.md` §3–5):** phương trình này là **tầng 3** của cascade — `Σβ_j·GPR_j` là GLOBAL-DIRECT, `θ·(macro)` là INDIRECT (shock đã truyền qua tầng 2 global macro), `λ·VN-GPR⊥` là DOMESTIC-DIRECT. Tầng 2 (`γ_{M,j}`: GPR→Oil/DXY/VIX/US10Y) ước lượng riêng, generic. Tổng tác động phân rã bằng **tích chập** `Total^global_j(h) = β_j(h) + Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ_M(h−s)` (KĐ12 — sửa 2026-07-16, không nhân hai hệ số cùng horizon). Mọi shock trong phương trình là **innovation** (CLAUDE.md #9).
- Outcome: VN-Index excess return, VN30F1M, tỷ giá USD/VND, nhóm ngành xuất khẩu (dệt may, thủy sản, gỗ, điện tử) vs nhóm phòng thủ.
- Xử lý weekend sau publish lag D+1: gán vào ngày giao dịch kế tiếp; dùng mean cho LEVEL/INNOVATION và max cho JUMP. `LEVEL+JUMP = mean(LEVEL) + max(JUMP)` để không làm mượt tail event cuối tuần.
- Giả thuyết độ trễ phản ánh (leading indicator): global GPR spike tại t, báo VN phản ánh đầy đủ tại t+Δ (giờ→ngày). Nếu Δ > 0 đo được thì global GPR là tín hiệu dẫn trước cho phản ứng của retail VN (nhóm chủ yếu đọc tin tiếng Việt) — kiểm định chính thức tại C2-KĐ5.

**Track vĩ mô (monthly/quarterly):**
- TVP-VAR frequency connectedness (replicate khung Cao & Vo nhưng thay input bằng bộ chỉ số phân tầng) — cho phép độ nhạy thay đổi theo regime.
- Outcome: CPI, IIP, xuất khẩu, dòng vốn FII.

### Lớp 5: Hệ số exposure riêng VN (đóng góp gốc, chưa ai publish)

```
β_VN = β_panel × (1 + δ·Exposure_VN)
Exposure_VN = f(US_export_share, CN_input_dependency, tariff_differential, DXY_interaction, FTA_diversification)
```
Ước lượng δ bằng cách hồi quy residual của mô hình panel trên các biến exposure. Đây là phần rủi ro cao nhất — chỉ commit sau khi Lớp 1–4 pass backtest.

### A6. Chiều ngược VN → thế giới (giả thuyết kiểm định, không giả định)

VN không còn là "price taker" thuần túy — có 3 kênh mà shock từ VN có thể lan ra toàn cầu:
1. **Đất hiếm**: USGS ước tính VN có trữ lượng lớn thứ 2 thế giới (~22 triệu tấn, ~19% toàn cầu), trong bối cảnh TQ kiểm soát 85% chế biến và 92% sản xuất nam châm — shock chính sách đất hiếm VN chạm trực tiếp vào chuỗi công nghệ/quốc phòng toàn cầu. (Lưu ý: ước tính trữ lượng có tranh cãi, bản cập nhật USGS gần đây hạ xuống ~3.5 triệu tấn — bản thân sự bất định này cũng là một biến.)
2. **Nút chuỗi cung ứng điện tử**: Apple suppliers (Foxconn, Luxshare), nhà máy nam châm (Baotou INST, Star Group) đã dịch chuyển sang VN — gián đoạn tại VN (đình công, mất điện, chính sách) giờ có tác động lan chuỗi toàn cầu.
3. **Vị trí Biển Đông**: leo thang có VN tham gia trực tiếp → phí vận tải biển, bảo hiểm hàng hải toàn cầu.

Cách đưa vào model: bilateral index đo cả hai chiều `BIGPR_{VN→world}` (dùng trường actor/target — bài mà VN là actor chứ không phải target). Kiểm định: hồi quy biến toàn cầu (giá đất hiếm, cước vận tải container, cổ phiếu ngành điện tử toàn cầu) lên BIGPR_{VN→world}. Kỳ vọng thực tế: hệ số ≈ 0 với hầu hết biến, khác 0 với nhóm hẹp (đất hiếm, electronics supply chain) — nếu đúng vậy, model chính rút gọn về một chiều và chỉ giữ chiều ngược cho nhóm biến hẹp đó. Không mất gì nếu giả thuyết sai, có thêm một finding publishable nếu đúng.

---

## PHẦN B — DỮ LIỆU

### B1. Corpus báo chí tiếng Việt
| Nguồn | Vai trò | Độ sâu lịch sử cần |
|---|---|---|
| VnExpress, Tuổi Trẻ, Thanh Niên | Tin tổng hợp, chính trị | ≥ 2010 (mục tiêu), tối thiểu 2015 |
| CafeF, Vietstock, VnEconomy | Tài chính — đã có pipeline RSS/BM25 sẵn trong BeaverX | ≥ 2015 |
| Báo Chính phủ, Nhân Dân | Tín hiệu chính sách chính thống | ≥ 2015 |

Yêu cầu tối thiểu để backtest có ý nghĩa: **≥ 8–10 năm daily** (phải phủ ít nhất 3 sự kiện lớn: căng thẳng Biển Đông 2014/2019, trade war 2018–2019, COVID 2020, thuế quan 2025–2026). Nếu không crawl được lịch sử đủ sâu → dùng GPRC_VNM (báo tiếng Anh, có từ 1985) cho giai đoạn cũ và VN-GPR tự xây cho giai đoạn mới, có kiểm định tính liên tục (splice test).

### B2. Dữ liệu thị trường/vĩ mô
- VN-Index, VN30, giá cổ phiếu theo ngành (daily) — nguồn có sẵn trong BeaverX.
- USD/VND, lãi suất liên NH, CDS Việt Nam 5Y.
- CPI, IIP, xuất nhập khẩu theo tháng (GSO/TCTK).
- **Input cho tầng global (bắt buộc cho Lớp 4):** GPR daily global + GPRD_ACT/GPRD_THREAT (file daily đã có), GPRC của US/CN/RU (file country-specific), giá dầu Brent, DXY, VIX. Cho A6/KĐ7: chỉ số giá đất hiếm, cước container (Drewry/SCFI), ETF electronics toàn cầu.
- Benchmark đối chiếu: GPRC_VNM chính thức (file bạn đã có bản 44 nước trên máy), EPU các đối tác.

### B3. Nguồn mở rộng (Giai đoạn 2, KHÔNG đưa vào core)
Twitter/X, GDELT (đã có nghiên cứu cho quan hệ TQ–ĐNA/Biển Đông), Polymarket (forward-looking duy nhất) — chỉ thêm sau khi core model pass backtest, mỗi nguồn thêm vào phải chứng minh **incremental value** (tăng IC/Sharpe out-of-sample so với model chỉ có VN-GPR), nếu không thì loại.

---

## PHẦN C — KẾ HOẠCH VALIDATION & BACKTEST

### C1. Validation chỉ số (trước khi đụng đến thị trường)

**V1 — Human audit:** lấy mẫu ngẫu nhiên 500–1,000 bài đã chấm, 2 người Việt đánh giá độc lập theo cùng rubric. Đạt: tương quan người–máy ≥ 0.80 (paper gốc đạt 0.88 tiếng Anh; tiếng Việt chấp nhận thấp hơn chút), false-discovery ≤ 15%.

**V2 — Model robustness:** chấm lại 10% mẫu bằng model thứ hai (GPT-4o hoặc Qwen3-14B đang self-host — có ý nghĩa riêng: nếu Qwen đạt tương quan cao thì về sau chạy production bằng model tự host, chi phí ~0). Đạt: tương quan giữa các model ≥ 0.85 (chuẩn paper gốc).

**V3 — Narrative check:** vẽ chuỗi VN-GPR 10 năm, kiểm tra bằng mắt các đỉnh có khớp sự kiện đã biết: giàn khoan HD-981 (5/2014), trade war (2018–19), COVID (2020), Nga-Ukraine (2/2022), thuế quan 46% (4/2025), đàm phán song phương (2025–26). Đạt: mọi sự kiện lớn đều tạo đỉnh nhận diện được; các đỉnh "lạ" phải giải thích được khi đọc lại bài gốc.

**V4 — Convergent validity:** tương quan với GPRC_VNM chính thức (monthly). Kỳ vọng: 0.5–0.8. Quá cao (>0.9) → không có thông tin mới so với chỉ số có sẵn, mất giá trị nghiên cứu. Quá thấp (<0.3) → nghi ngờ đo sai khái niệm. Vùng 0.5–0.8 là lý tưởng: cùng khái niệm nhưng có tín hiệu nội địa bổ sung.

### C2. Backtest thống kê (chuẩn academic)

- **Split (sửa 2026-07-16 theo review `08` §4.8 — bản "IS 2015–2022 / OOS 2023–2026" cũ đã bỏ):** 4 tầng khóa cứng trong `config/backtest.yaml`: Development 2015–2020 (ước lượng, tự do thử) / Validation 2021–2023 (chọn model/feature) / Pseudo-OOS 2024–2025 (walk-forward) / **Final holdout 2026-H1 — chạm ĐÚNG 1 LẦN, không sửa model theo kết quả của nó**. Lý do bỏ split cũ: một cửa sổ OOS đơn dùng đi dùng lại cho chọn feature/chân/model thì đã thành in-sample trên thực tế. Final holdout chứa giai đoạn thuế quan 2026 — stress test tự nhiên.
- **Kiểm định 1 (tính giải thích):** ΔVN-GPR có ý nghĩa thống kê trong hồi quy VN-Index excess return? Benchmark: paper AI-GPR cho thấy hiệu ứng có ý nghĩa vững trên US returns; keyword-based yếu hơn ~1/3. Mục tiêu: VN-GPR (LLM) phải beat GPRC_VNM (keyword) trên cùng kỳ dữ liệu VN — đây là phép so sánh "giống như đã chứng minh trên S&P 500" mà đề bài yêu cầu.
- **Kiểm định 2 (Granger/lead-lag):** VN-GPR có dẫn trước biến động VN-Index không, hay chỉ đồng thời? Nếu chỉ đồng thời → vẫn có giá trị risk-monitoring, không có giá trị dự báo.
- **Kiểm định 3 (threats vs acts):** hệ số GPT vs GPA khác nhau có ý nghĩa không; act-bất-ngờ (residual sau khi kiểm soát GPT trước đó) tác động mạnh hơn act-đã-dự-đoán không.
- **Kiểm định 4 (connectedness):** replicate khung Cao & Vo với VN-GPR thay cho GPR nước ngoài — VN-GPR tự xây giải thích được bao nhiêu % biến động so với 18.80% của GPR ngoại? Nếu ≥ 25% → cải thiện rõ rệt, publishable.
- **Kiểm định 5 (lead-lag global→VN, giả thuyết "độ trễ phản ánh"):** đo Δ = độ trễ giữa spike của global GPR (daily, có sẵn realtime) và spike tương ứng của VN-GPR từ báo tiếng Việt. Nếu Δ > 0 ổn định (vài giờ–2 ngày) VÀ trong khoảng trễ đó VN-Index chưa phản ứng hết → global GPR là leading indicator khả dụng cho retail-driven market. Đây là kiểm định có giá trị thương mại cao nhất cho Quant Agent.
- **Kiểm định 6 (actor weights):** AW-GPR (Lớp 2b) beat VN-GPR không trọng số về R²/IC out-of-sample không? Đồng thời báo cáo bảng w_a ước lượng được — bản thân bảng này (ai phát ngôn thì thị trường VN phản ứng mạnh nhất) là một finding độc lập, publishable.
- **Kiểm định 7 (chiều ngược VN→thế giới, xem A6):** hồi quy giá đất hiếm/cước container/cổ phiếu electronics toàn cầu lên BIGPR_{VN→world}. Kỳ vọng null với đa số biến; khác 0 với nhóm hẹp.
- **Kiểm định 12 (transmission decomposition — sửa 2026-07-16 theo review `08` §4.1/4.2, công thức `07v2` §5.2):** phân rã tổng tác động GPR→VN-Index thành **ba** phần: Global-direct (β·GPR^{j,innov}), Indirect (**tích chập** `Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ_M(h−s)` — KHÔNG nhân hai hệ số cùng horizon), và Domestic-direct (λ·VN-GPR⊥ innovation); test ý nghĩa bằng bootstrap SE. Mọi shock là innovation, không phải level (CLAUDE.md #9). Gọi là "transmission decomposition"/"predictive", KHÔNG "causal mediation" khi chưa có structural ID (claims matrix `07v2` §6.4). Kỳ vọng Indirect ≫ (β+λ) (nền KT nhỏ mở chịu shock chủ yếu qua kênh vĩ mô toàn cầu). Nếu λ đáng kể → có rủi ro riêng VN không qua global, biện minh xây corpus tiếng Việt (V-phase). Gắn với cổng G2b.

### C3. Backtest tín hiệu giao dịch (chuẩn industry, cho BeaverX)

- **Chiến lược thử nghiệm:** (a) risk-off filter — giảm tỷ trọng equity khi VN-GPR vượt ngưỡng percentile 90 rolling 1 năm; (b) sector rotation — long phòng thủ/short xuất khẩu khi BIGPR_{US→VN} spike; (c) sizing theo GPT (đe dọa kéo dài → giảm dần exposure).
- **Metrics:** Sharpe, max drawdown, hit rate, Information Coefficient (IC) của tín hiệu với forward return 5/20/60 ngày, turnover và chi phí giao dịch (quan trọng với thanh khoản HOSE).
- **Chống overfit:** walk-forward (tune trên 3 năm, test 1 năm, trượt); không quá 3 tham số tự do cho mỗi chiến lược; báo cáo cả các biến thể thất bại, không chỉ biến thể đẹp nhất.
- **Benchmark so sánh:** buy-and-hold VN-Index; chiến lược tương tự dùng GPRC_VNM thay VN-GPR (để chứng minh giá trị của việc tự xây); chiến lược dùng VIX/DXY đơn thuần (để chứng minh GPR có thông tin vượt ngoài biến toàn cầu).

### C4. Tiêu chí GO/NO-GO giữa các giai đoạn

| Cổng | Điều kiện pass | Nếu fail |
|---|---|---|
| Sau V1–V4 | Cả 4 đạt ngưỡng | Sửa rubric/prompt, không đi tiếp |
| Sau C2 | Kiểm định 1 + 4 pass | Chỉ số chỉ dùng risk-monitoring, không claim dự báo |
| Sau C3 | IC > 0.03 và Sharpe cải thiện so với benchmark OOS | Không đưa vào Quant Agent làm tín hiệu; giữ làm context cho LLM agent |

---

## PHẦN D — LỘ TRÌNH THỰC THI

| Giai đoạn | Thời lượng | Deliverable |
|---|---|---|
| **P0 — Chuẩn bị** | 1–2 tuần | Lấy GPRC_VNM chính thức làm baseline; chốt danh sách nguồn báo; đánh giá độ sâu archive crawl được |
| **P1 — Pipeline chấm điểm** | 2–3 tuần | Rubric tiếng Việt v1; pre-filter keyword; chạy pilot 5,000 bài; human audit V1 |
| **P2 — Xây chỉ số lịch sử** | 3–4 tuần | Crawl + chấm toàn bộ corpus; chuỗi VN-GPR/GPT/GPA daily; validation V2–V4 |
| **P3 — Mô hình kinh tế lượng** | 3–4 tuần | Local projection daily + TVP-VAR monthly; kiểm định C2 |
| **P4 — Backtest giao dịch** | 2–3 tuần | 3 chiến lược, walk-forward, báo cáo C3 |
| **P5 — Tích hợp BeaverX** | 2 tuần | Service chấm real-time (RSS đã có sẵn), feed score vào Market/Quant Agent |
| **P6 — (Tùy chọn) Nguồn mở rộng** | sau P5 | GDELT/Polymarket/X — mỗi nguồn phải chứng minh incremental value |

Tổng: ~3–4 tháng cho core (P0–P5), phù hợp chạy song song với công việc hiện tại nếu 1 engineer + bạn review.

---

## PHẦN E — RỦI RO & GIỚI HẠN PHẢI KHAI BÁO TRƯỚC

1. **Kiểm duyệt báo chí VN:** báo trong nước có thể đưa tin muộn/nhẹ hơn về rủi ro nội địa → VN-GPR_domestic có thể bị nén (downward bias). Giải pháp: luôn chạy song song GPRC_VNM (nguồn ngoại) làm đối chứng; chênh lệch giữa hai chỉ số tự nó là một tín hiệu ("divergence indicator" — báo ngoại nói nhiều mà báo nội im lặng là thông tin).
2. **Độ sâu lịch sử hạn chế:** nếu chỉ crawl được từ 2015 → chuỗi 11 năm, đủ cho daily backtest nhưng mỏng cho kết luận macro monthly (chỉ ~130 quan sát). Khai báo rõ trong mọi kết quả.
3. **GPR đo attention, không đo thực tế:** literature đã chỉ ra tương quan giữa GPR và cường độ xung đột thực chỉ ρ = 0.28–0.50. Không claim chỉ số đo "rủi ro thật" — nó đo mức độ chú ý, và mức độ chú ý là thứ di chuyển giá tài sản.
4. **Nguy cơ nhìn thấy pattern không có (data mining):** thị trường VN nhỏ, nhiễu, retail-driven — hiệu ứng tìm thấy in-sample rất dễ biến mất OOS. Kỷ luật: mọi con số công bố phải là OOS.
5. **Rubric tiếng Việt chưa từng được validate:** đây vừa là rủi ro vừa là chính đóng góp nghiên cứu. Human audit V1 là bắt buộc, không được bỏ qua để tiết kiệm thời gian.

---

## PHẦN F — TIÊU CHUẨN "NGANG TẦM S&P 500" NGHĨA LÀ GÌ (định nghĩa đo được)

Mô hình được coi là đạt chuẩn tương đương các mô hình đã validate trên S&P 500 khi:
1. Hiệu ứng VN-GPR lên VN-Index return có ý nghĩa thống kê (p < 0.05) trên mẫu OOS — như AI-GPR đã đạt với US returns.
2. LLM-based index beat keyword-based index (GPRC_VNM) về sức giải thích trên cùng dữ liệu — tái lập kết quả "mạnh hơn ~1/3" của paper gốc trên thị trường mới.
3. Human-audit correlation ≥ 0.80 — tiệm cận chuẩn 0.88 của bản tiếng Anh.
4. Tín hiệu giao dịch có IC dương ổn định qua walk-forward, không phụ thuộc 1 giai đoạn duy nhất.

Đạt cả 4 → có trong tay: (a) chỉ số VN-GPR đầu tiên từ báo chí tiếng Việt, chuẩn academic, có thể publish; (b) tín hiệu production-ready cho BeaverX; (c) tài sản khác biệt hóa thật sự khi pitch — "chỉ số rủi ro địa chính trị realtime duy nhất cho thị trường Việt Nam".
