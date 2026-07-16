# GPR GLOBAL ENGINE — THIẾT KẾ CHI TIẾT (3 CHÂN)

**Phiên bản:** 1.0 — 07/2026
**Quan hệ tài liệu:** Chi tiết hóa và THAY THẾ phần G-phase trong VN-GPR_engineering_plan.md v1.1. Research plan v1.1 giữ nguyên vai trò nền tảng phương pháp luận.
**Nguyên tắc:** Chân A ingest (không build lại cái đã có) → chứng minh giá trị nhanh. Chân B/C build dần, mỗi chân phải chứng minh **incremental IC** so với hệ chỉ có các chân trước, nếu không thì loại.

---

## 0. KIẾN TRÚC TỔNG THỂ

```
CHÂN A: MEDIA ATTENTION (ingest)          CHÂN B: PRIMARY STATEMENTS (build)   CHÂN C: PHYSICAL EVENTS (ingest+LLM)
GPRD daily 1985+ · GPRC 44 nước 1900+     S-GPR từ phát ngôn sơ cấp            GDELT 1979+ (CAMEO/Goldstein)
AI-GPR (khi public data)                  UNGDC 1946+ · BIS speeches 1997+     LLM-reconstruction cho pre-1979
                                          WH/MOFA/Kremlin daily 2000s+          và cross-check
        │                                         │                                    │
        └────────────────────┬────────────────────┴────────────────────┬───────────────┘
                             ▼                                         ▼
              FUSION LAYER                                DIVERGENCE SIGNALS
              • Escalation Ladder (trạng thái cặp nước)   • B↑A− : early warning (lời trước tin)
              • Surprise Index (shock chưa price-in)      • A↑C− : media hype (fade)
                             │                            • C↑A− : underpriced risk
                             ▼
              ECONOMETRICS + BACKTEST (R1/R2, dùng chung)
                             ▼
              SERVING: gpr-api + Kafka → BeaverX agents
```

Ba chân đo ba khái niệm khác nhau: **chú ý** (báo chí viết gì) — **ý định** (chủ thể quyền lực nói gì) — **hành động** (điều gì thực sự xảy ra). Divergence giữa chúng là thông tin không tồn tại trong bất kỳ chỉ số đơn lẻ nào.

---

## 1. CHÂN A — MEDIA ATTENTION (ingest, tuần 1)

| Series | Nguồn | Tần suất | Từ |
|---|---|---|---|
| GPRD, GPRD_ACT, GPRD_THREAT | matteoiacoviello.com (file daily) | daily | 1985 |
| GPRC × 44 nước (lưu hết) | file country-specific | monthly | 1900/1985 |
| GPT/GPA global | file export chính | monthly | 1900 |
| Oil (Brent), DXY, VIX, US10Y | FRED/yfinance | daily | — |
| VN-Index, VN30, USD/VND, thanh khoản HOSE | nguồn BeaverX sẵn có | daily | — |

Bảng: `ext_series` — schema đầy đủ ở `sql/001_schema_core.sql` (từ 2026-07-16 có thêm `available_at/revised_at/source_version/data_version/quality_flag` chống leakage — review `08` §4.7, CLAUDE.md #11; dòng cũ `(series_id, date, value, loaded_at)` lỗi thời). Cron tải file GPR monthly từ server BeaverX (domain không qua được sandbox). Ghi chú citation bắt buộc khi dùng: "Data downloaded from https://www.matteoiacoviello.com/gpr.htm on <ngày tải>".

**Chân A một mình đã đủ chạy toàn bộ econometrics + backtest đợt đầu** (KĐ1/3/5 + 3 chiến lược) — đây là con đường ra kết quả trong 6–8 tuần như roadmap v1.1. Chân B/C là nâng cấp có cổng kiểm soát.

---

## 2. CHÂN B — S-GPR: CHỈ SỐ TỪ PHÁT NGÔN SƠ CẤP (build, thành phần chính phải tự xây)

### 2.1. Khác biệt khái niệm với GPR (lý do tồn tại)

GPR đo qua bộ lọc biên tập của báo chí; S-GPR đo trực tiếp lời của chủ thể quyền lực. Ba giá trị: (1) không méo theo chu kỳ chú ý truyền thông; (2) actor/role được biết chắc chắn từ metadata nguồn (không phải đoán từ bài báo) — nền tảng sạch cho actor-weighting; (3) giả thuyết kiểm định được: S-GPR dẫn trước GPR khi ngôn từ leo thang trước khi báo chí coi là tin lớn.

### 2.2. Danh mục nguồn (theo thứ tự ưu tiên build)

**Nhịp chậm (annual/quarterly) — baseline căng thẳng:**
| # | Nguồn | Phạm vi | Truy cập | Ghi chú |
|---|---|---|---|---|
| B1 | UN General Debate Corpus (UNGDC) | 1946–nay, mọi thành viên LHQ, ~10k diễn văn | Dataset public (Harvard Dataverse / GitHub bản complete 2025) | Mỗi nước 1 diễn văn/năm = posture chính thức. Đã có paper hướng dẫn dùng LLM đo lường trên chính corpus này |
| B2 | BIS central bank speeches | 1997–nay, kèm metadata speaker/tổ chức/vị trí | bis.org, dataset đã chuẩn hóa cho NLP | Chân tài chính: Fed/ECB/PBOC/BOJ |

**Nhịp nhanh (daily) — tín hiệu vận hành:**
| # | Nguồn | Phạm vi | Truy cập |
|---|---|---|---|
| B3 | White House (statements, remarks, EO) + American Presidency Project | 1929–nay (APP), realtime (WH) | Scrape/RSS; APP có archive học thuật |
| B4 | Trump statements (Twitter Archive + Truth Social) | 2009–nay | Trump Twitter Archive (public dump), scrape Truth Social |
| B5 | MOFA Trung Quốc (họp báo hàng ngày, có bản tiếng Anh) | ~2000s–nay | Scrape fmprc.gov.cn |
| B6 | Kremlin (en.kremlin.ru transcripts) | ~2000–nay | Scrape |
| B7 | USTR + Commerce (thông báo thuế quan, export controls) | 2000s–nay | Scrape/RSS |
| B8 | Fed speeches/testimony (bổ sung realtime cho B2) | realtime | federalreserve.gov RSS |

V1 chỉ cần B1–B5 (đủ phủ trục Mỹ–Trung + tài chính). B6–B8 thêm sau.

### 2.3. Rubric chấm điểm phát ngôn (thang có dấu, khác GPR)

Điểm phát ngôn `v ∈ [−1.0, +1.0]` — có chiều hòa giải, vì phát ngôn ngoại giao mang cả hai hướng (GPR chỉ đo một chiều rủi ro):

| v | Bậc | Mô tả | Ví dụ |
|---|---|---|---|
| −1.0…−0.6 | Hòa giải mạnh | Ký kết, nhượng bộ, dỡ trừng phạt, cam kết hòa bình | "agreed to lift tariffs" |
| −0.5…−0.1 | Hòa dịu | Đề nghị đàm phán, ngôn từ tích cực, giảm leo thang | "constructive dialogue" |
| 0 | Trung lập | Thủ tục, không hàm ý quan hệ | |
| +0.1…+0.3 | Bất mãn | Phàn nàn, quan ngại, triệu đại sứ | "expressed deep concern" |
| +0.4…+0.6 | Cảnh báo/Đe dọa có điều kiện | "sẽ đáp trả nếu", đe dọa thuế/trừng phạt chưa thi hành | "will impose tariffs if" |
| +0.7…+0.8 | Tối hậu thư/Đe dọa quân sự | Thời hạn cụ thể, đe dọa vũ lực, cắt quan hệ | "all options on the table" + deadline |
| +0.9…+1.0 | Tuyên bố hành động | Công bố thi hành: áp thuế có hiệu lực, động binh, phong tỏa | "effective immediately" |

Kèm mỗi phát ngôn: `{v, actor_country, actor_person, actor_role, target_country, channel, commitment: rhetoric|conditional|announced_action, specificity: 0-1}`. Trường `commitment` là bản đối xứng của GPT/GPA ở tầng phát ngôn; `specificity` (có con số/thời hạn cụ thể không) — phát ngôn cụ thể đáng tin hơn khoa trương.

### 2.4. Prompt chấm điểm (draft v0, tiếng Anh vì nguồn B là tiếng Anh)

```
You are scoring official statements for geopolitical escalation intensity.
Input: one official statement (speech excerpt, press release, or post),
with metadata: {source, date, speaker, speaker_role}.

Score v in [-1.0, +1.0]:
  negative = de-escalatory/conciliatory, 0 = neutral/procedural,
  positive = escalatory. Use the anchor scale: [bảng 2.3 nhúng vào đây]

Rules:
- Score the STATEMENT's content, not the underlying situation.
- A specific threat with conditions/deadlines scores higher than vague bluster.
- Reporting/quoting another party's threat is NOT the speaker escalating.
- Historical commemoration, condolences, culture/sports → v = 0.
Return strict JSON:
{"v": float, "actor_country": ISO3|null, "target_country": ISO3|null,
 "channel": "trade|military|sanction|diplomacy|energy|tech|null",
 "commitment": "rhetoric|conditional|announced_action",
 "specificity": float, "rationale": "<= 25 words"}
Temperature 0.
```

Hiệu chỉnh qua đúng quy trình V1 (human audit 500 mẫu, 2 người chấm) như rubric VN — dùng chung tooling R3.

### 2.5. Tổng hợp thành chỉ số

```
S-GPR_{a→b, t} = Σ_i w(role_i) · max(v_i, 0) · specificity_i   (chiều leo thang, theo cặp)
S-CONC_{a→b, t} = Σ_i w(role_i) · max(−v_i, 0)                  (chiều hòa giải, giữ riêng)
S-GPR_global_t = Σ_pairs trade_weight_pair · S-GPR_pair,t
```
- Không trộn hai chiều thành một số (net) — leo thang và hòa giải tác động bất đối xứng lên thị trường, giữ riêng để hệ số tự do.
- `w(role)`: khởi tạo bằng thứ bậc đơn giản (nguyên thủ 1.0, bộ trưởng 0.6, phát ngôn viên 0.4, thống đốc NHTW 0.8 cho kênh tài chính) → thay bằng trọng số ước lượng từ event study (speaker fixed-effects, như Lớp 2b research plan) khi đủ dữ liệu intraday.
- Chuẩn hóa theo số phát ngôn của nguồn trong kỳ (mỗi nguồn có nhịp đăng khác nhau).

### 2.6. Khối lượng & chi phí

UNGDC ~10k văn bản (chấm theo đoạn ~80–150k đoạn) + BIS ~20k speeches + daily sources backfill ~200–400k items → tổng ước ~500–700k lượt chấm × $0.0001–0.0003 (văn bản dài hơn bài báo) ≈ **$100–250 một lần backfill**. Realtime: vài trăm phát ngôn/ngày, không đáng kể; production chuyển Qwen3-14B nếu pass V2.

---

## 3. CHÂN C — PHYSICAL EVENTS (ingest GDELT + LLM reconstruction)

### 3.1. GDELT (1979+)

- Truy cập: BigQuery (`gdelt-bq.gdeltv2.events`), export aggregate về PG — KHÔNG kéo raw event về (firehose, vô nghĩa với mục tiêu).
- Aggregate duy nhất cần: theo `(actor1_country, actor2_country, month)`:
  - `n_events` theo QuadClass (1 verbal coop / 2 material coop / 3 verbal conflict / 4 material conflict)
  - `goldstein_sum`, `goldstein_min` (sự kiện tệ nhất tháng)
  - `avg_tone`
- Chống đếm trùng (điểm yếu đã biết của GDELT): dùng `NumMentions` làm trọng số thay vì đếm event; hoặc chỉ đếm event có `NumSources ≥ 3`.
- Phạm vi cặp v1: US↔CN, US↔RU, US↔IR, CN↔TW, RU↔UA, US↔VN, CN↔VN, + Middle East cluster. Lưu query dạng tham số để thêm cặp không tốn công.

### 3.2. LLM Historical Reconstruction (pre-1979 và cross-check)

Theo đúng protocol đã publish (arXiv 2507.04833 — dùng LLM biên soạn sự kiện song phương, phân loại CAMEO, chấm Goldstein −10/+10):
1. Prompt LLM (có web search) liệt kê sự kiện song phương theo cặp nước × năm, 6 nhóm quan hệ (kinh tế, ngoại giao, an ninh, pháp lý/lãnh thổ, đa phương, khác), xử lý kế thừa quốc gia (USSR→RUS).
2. Chấm Goldstein từng sự kiện.
3. **Kiểm soát hallucination (bắt buộc):** (a) giai đoạn 1979+ phải khớp GDELT ở mức tháng-cặp (tương quan chuỗi ≥ 0.6 mới chấp nhận phần pre-1979); (b) mỗi sự kiện phải kèm ≥ 2 nguồn kiểm chứng được; (c) sample audit tay 100 sự kiện.
- Vai trò: kéo dài chuỗi acts về trước 1979 cho nghiên cứu dài hạn + bộ kiểm tra chéo độc lập cho cả GDELT lẫn GPA.

---

## 3.bis. TRANSMISSION CASCADE — 3 TẦNG (tách tổng khỏi riêng nước)

> Chi tiết đầy đủ: `docs/06_transmission_cascade_update.md`. Công thức: `docs/07_formulas_reference_v2.md` §3–5.
>
> ### ⚠️ ĐÍNH CHÍNH (2026-07-16, sau review `08` / phản hồi `09`)
> Kiến trúc 3 tầng của mục này vẫn ĐÚNG, nhưng 3 chi tiết công thức bên dưới đã bị thay — khi mâu thuẫn, **`07_formulas_reference_v2.md` (v2.1) là nguồn chân lý**:
> 1. **Tầng 3 có BA hệ số, không phải hai**: `β` global-direct + `θ` indirect + `λ` domestic-direct. Sơ đồ dưới ghi `r^c = θ·macro + λ·GPR^{c,⊥}` là dạng v1 đã bỏ (thiếu β — review §4.2; bản gốc `01` Lớp 4b vốn có đủ β).
> 2. **Mediation `Σ γ_{M,j}·θ^c_M` (nhân cùng horizon) SAI** → tích chập: `Indirect(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ^c_M(h−s)` (review §4.1). Gọi là "transmission decomposition", KHÔNG "causal mediation" khi chưa có structural ID.
> 3. **Mọi shock là INNOVATION, không phải level** `ln(1+GPR)` (review §4.4, CLAUDE.md #9).

Ba chân (A/B/C) sinh **shock vector** ở TẦNG 1. Từ shock tới thị trường đích KHÔNG map thẳng
một hệ số β — mà đi qua một tầng vĩ mô toàn cầu trung gian. Ba tầng nối tiếp (mediation):

```
TẦNG 1  SHOCK           GPR / S-GPR / GPT / GPA / Surprise / Ladder   (ba chân)
   │
   ▼
TẦNG 2  GLOBAL MACRO    Oil, DXY, VIX, US10Y   ← generic ENGINE, ước lượng 1 lần
   │                    = "Global Macro Impact" (deliverable độc lập, bán cho mọi nước)
   ▼
TẦNG 3  MARKET ĐÍCH     r^c = β^c·(GPR^{j,innov} GLOBAL-DIRECT) + θ^c·(macro INDIRECT)
                            + λ^c·(GPR^{c,⊥,innov} DOMESTIC-DIRECT) + controls
                        = PARAMS riêng từng nước (β/θ/λ), hệ số tự do ước lượng từ dữ liệu
```

**Tại sao tách:** shock Trung Đông (qua kênh dầu) và shock Mỹ-Trung (qua kênh tỷ giá/risk-off) đánh VN
theo cơ chế khác nhau; gộp vào một β là sai nhân-quả. Tách tầng 2 (tổng, generic) khỏi tầng 3 (riêng
nước, params tự do) cho: (1) hệ số đúng theo kênh; (2) hai deliverable — **Global Macro Impact** (1→2,
generic) + **Country Transmission** (2→3, mỗi nước một `config/params/<country>.yaml`).

**Transmission decomposition (KĐ12 — reduced-form, KHÔNG gọi "causal" khi chưa có structural ID):**
`Total^global_j(h) = β_j(h) + Indirect_j(h)` với `Indirect_j(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ^c_M(h−s)`
(tích chập — công thức `07v2` §5.2); phần riêng nước: `Total^domestic = λ(h)`. Indirect≫(β+λ) →
nước chịu shock chủ yếu qua kênh vĩ mô toàn cầu (điển hình nền KT nhỏ mở); λ đáng kể → có rủi ro
riêng không qua global, biện minh cho corpus bản địa (V-phase). Là **KĐ12** trong research plan.

Nguyên tắc engine+params giữ nguyên: **tầng 1–2 = ENGINE** (country-agnostic), **tầng 3 = PARAMS**.

---

## 4. FUSION LAYER

### 4.1. Escalation Ladder (máy trạng thái cặp quốc gia)

5 trạng thái: `S0 bình thường → S1 khẩu chiến → S2 đe dọa → S3 chuẩn bị/động viên → S4 hành động`.

- **V1 rule-based (đủ dùng, minh bạch):** phân trạng thái theo ngưỡng đồng thời của 3 chân trong cửa sổ 30 ngày — ví dụ S2 khi S-GPR_pair > p75 VÀ GDELT QuadClass-3 > p75 nhưng QuadClass-4 bình thường; S4 khi QuadClass-4 material conflict > p90 hoặc GPA spike. Bảng ngưỡng nằm trong config version-hóa.
- **V2 (nếu V1 chứng minh giá trị):** HMM/regime-switching với emission là (S-GPR, GPT, GPA, Goldstein) — trạng thái ẩn học từ dữ liệu.
- Output: `ladder_state (pair, date, state, days_in_state)`.

### 4.2. Surprise Index

```
Surprise_t = GPA_t − Ê[GPA_t | GPT_{t−1..−k}, S-GPR_{t−1..−k}, LadderState_{t−1}]
```
- V1: hồi quy tuyến tính/gradient boosting nhẹ, rolling window, ước lượng chỉ trên dữ liệu quá khứ tại mọi thời điểm (không leakage).
- Giả thuyết kiểm định (từ literature: acts đã dự đoán trước thì price-in rồi): trong phương trình giá, `Surprise` phải có hệ số mạnh hơn `GPA` thô. Nếu đúng → thay GPA bằng Surprise trong tín hiệu giao dịch.

### 4.3. Divergence signals (3 biến, mỗi biến một giả thuyết)

| Tín hiệu | Định nghĩa (z-score chênh lệch) | Giả thuyết kiểm định |
|---|---|---|
| EARLY_WARN | z(S-GPR) − z(GPR) > ngưỡng | Dự báo GPR tăng trong 5–20 ngày tới; vị thế phòng thủ sớm |
| MEDIA_HYPE | z(GPR) − z(Goldstein conflict) > ngưỡng | Mean-reversion: rủi ro được thổi phồng, fade sau 10–30 ngày |
| SILENT_RISK | z(Goldstein conflict) − z(GPR) > ngưỡng | Thị trường chưa price-in; drift tiêu cực phía trước |

---

## 5. KIỂM ĐỊNH BỔ SUNG (nối vào C2 của research plan)

- **KĐ8 (S-GPR lead GPR):** Granger + event study — S-GPR có dẫn trước GPR ở horizon ngày–tuần không? Đây là raison d'être của chân B.
- **KĐ9 (Surprise > GPA):** hệ số Surprise vs GPA thô trong phương trình giá (VN-Index và cả S&P 500 làm đối chứng — engine là global, kiểm định được trên nhiều thị trường).
- **KĐ10 (Ladder-conditional):** hệ số threat phụ thuộc trạng thái thang — threat tại S3 tác động ≠ threat tại S0? (interaction term)
- **KĐ11 (Divergence signals):** mỗi tín hiệu chạy như một chiến lược riêng qua walk-forward; giữ lại tín hiệu nào có IC OOS > 0.
- **Nguyên tắc chung:** chân B, chân C, fusion — mỗi khối chỉ được vào production nếu **tăng IC so với hệ trước nó** (A → A+B → A+B+C → +fusion). Báo cáo bảng incremental IC từng bước.

---

## 6. SCHEMA BỔ SUNG (PostgreSQL)

```sql
CREATE TABLE statements (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(30),            -- ungdc, bis, whitehouse, mofa_cn, trump_archive...
  url TEXT, published_at TIMESTAMPTZ,   -- đến phút với nguồn daily
  speaker TEXT, speaker_role VARCHAR(40), speaker_country CHAR(3),
  text TEXT, lang CHAR(2)
);
CREATE TABLE statement_scores (
  statement_id BIGINT REFERENCES statements(id),
  v REAL, target_country CHAR(3), channel VARCHAR(20),
  commitment VARCHAR(20), specificity REAL,
  model_version VARCHAR(30), rubric_version VARCHAR(10),
  PRIMARY KEY (statement_id, model_version, rubric_version)
);
CREATE TABLE gdelt_pair_monthly (
  actor1 CHAR(3), actor2 CHAR(3), month DATE,
  n_q1 INT, n_q2 INT, n_q3 INT, n_q4 INT,
  goldstein_sum REAL, goldstein_min REAL, avg_tone REAL,
  PRIMARY KEY (actor1, actor2, month)
);
CREATE TABLE ladder_state (
  pair VARCHAR(7), date DATE, state SMALLINT, days_in_state INT,
  config_version VARCHAR(10), PRIMARY KEY (pair, date, config_version)
);
-- gpr_indices (đã có) dùng chung cho S-GPR, Surprise, divergence signals
```

---

## 7. LỘ TRÌNH G-PHASE MỞ RỘNG (thay bảng G1–G4 cũ)

| Sprint | Tuần | Nội dung | Cổng |
|---|---|---|---|
| **G1** | 1 | Chân A ingest đầy đủ + notebook khám phá | Series trong PG, review cùng nhau |
| **G2** | 2–5 | R1 econometrics trên chân A (LP, TVP-VAR, KĐ1/3/5, GPRC_VNM proxy) | KĐ1 pass → tiếp; fail → dừng đánh giá lại |
| **G3** | 6–8 | R2 backtest 3 chiến lược chân A, walk-forward | IC > 0.03 → serving; đây là **baseline** cho mọi chân sau |
| **G4** | 9–10 | Serving tối giản (S6/S7): API + Kafka + 2 tools cho agents | Tín hiệu chạy thật trong Quant Agent |
| **G5** | 11–15 | **Chân B**: ingest B1–B5, rubric + prompt v1, human audit, backfill, S-GPR indices; KĐ8 | KĐ8 pass HOẶC incremental IC > 0 → giữ; không → đóng băng chân B |
| **G6** | 16–19 | **Chân C**: GDELT aggregate + (optional) LLM reconstruction; Ladder v1 rule-based; Surprise Index; KĐ9/10 | Incremental IC > 0 từng khối |
| **G7** | 20–22 | Divergence signals + KĐ11; hợp nhất serving; báo cáo tổng incremental IC A→A+B→A+B+C→fusion | Bảng incremental IC — tài liệu pitch chính |
| **V-phase** | sau | Corpus tiếng Việt (như plan v1.1) — giờ có baseline mạnh hơn nhiều để so | |

Nhân lực: G1–G4 như cũ (bạn + 1 engineer part-time, ~10 tuần). G5–G7 thêm ~12 tuần, phần lớn là research + scraping nhẹ; tổng engine đầy đủ ~5–6 tháng nhưng **có sản phẩm chạy thật từ tuần 10** và mỗi bước sau đều có cổng dừng.

## 8. RỦI RO RIÊNG CỦA PHẦN MỞ RỘNG

| Rủi ro | Giảm thiểu |
|---|---|
| Scraping MOFA/Kremlin không ổn định, có thể bị chặn | Nguồn phụ, mất không chết hệ thống; ưu tiên archive tĩnh (UNGDC, BIS, APP) làm xương sống |
| Rubric có dấu (±) khó chấm nhất quán hơn rubric một chiều | Human audit riêng cho chân B; nếu agreement thấp → gộp bậc (7 bậc → 5 bậc) |
| Ladder v1 rule-based nhạy cảm ngưỡng | Ngưỡng trong config version-hóa; sensitivity analysis bắt buộc trong báo cáo |
| GDELT BigQuery cost | Aggregate query theo tháng, ước < $50/lần backfill; cache về PG |
| Phạm vi phình to (7 sprint) | Cổng incremental IC ở G5/G6/G7 — cho phép dừng ở bất kỳ đâu mà vẫn có sản phẩm hoàn chỉnh từ G4 |
