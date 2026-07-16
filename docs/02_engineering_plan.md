# KẾ HOẠCH XÂY DỰNG HỆ THỐNG VN-GPR — ENGINEERING PLAN

**Phiên bản:** 1.2 — 07/2026 (GLOBAL-FIRST, 3 CHÂN) | Đi kèm: VN-GPR_research_plan.md v1.1 + **GPR_global_engine_design.md v1.0** (chi tiết hóa và thay thế bảng G-phase bên dưới bằng lộ trình G1–G7 ba chân: Media Attention / Primary Statements / Physical Events + Fusion)
**Thay đổi v1.1:** Đảo thứ tự thực thi — build engine lõi global trước (dữ liệu có sẵn, chi phí ≈ 0), phần corpus tiếng Việt (S1/S3/S4) hoãn xuống V-phase. Kiến trúc chuyển sang mô hình **1 engine + n bộ tham số quốc gia**: lõi country-agnostic, mỗi thị trường chỉ là 1 file params ước lượng lại; corpus ngôn ngữ bản địa là thành phần optional duy nhất phải xây riêng từng nước.
**Phạm vi:** Toàn bộ thành phần cần build để hiện thực hóa mô hình 5 lớp + backtest, tận dụng tối đa hạ tầng BeaverX sẵn có (Agno, Kafka, Redis, PostgreSQL, FastAPI, vLLM/Qwen3-14B, pipeline Vietstock RSS).

---

## 0. KIẾN TRÚC TỔNG THỂ

```
                        ┌─────────────────────────────────────────────┐
                        │                DATA LAYER                     │
  Báo VN (RSS/crawl) ──▶│ [S1] news-ingestor ──▶ raw_articles (PG)     │
  GPR global/country ──▶│ [S2] external-data-ingestor ──▶ ext_series  │
  Oil/DXY/VIX/VNIndex ─▶│      (daily cron)                            │
                        └──────────────┬──────────────────────────────┘
                                       ▼
                        ┌─────────────────────────────────────────────┐
                        │             SCORING LAYER                     │
                        │ [S3] pre-filter (keyword VN, rule-based)     │
                        │ [S4] llm-scorer (GPT-4o-mini / Qwen3 local)  │
                        │      ──▶ article_scores (PG)                 │
                        └──────────────┬──────────────────────────────┘
                                       ▼
                        ┌─────────────────────────────────────────────┐
                        │              INDEX LAYER                      │
                        │ [S5] index-builder (daily/monthly aggregate) │
                        │      VN-GPR, GPT/GPA, AW-GPR, BIGPR, ⊥      │
                        │      ──▶ gpr_indices (PG) + Kafka topic      │
                        └──────────────┬──────────────────────────────┘
                              ┌────────┴─────────┐
                              ▼                  ▼
              ┌──────────────────────┐  ┌──────────────────────────┐
              │  RESEARCH LAYER       │  │  SERVING LAYER            │
              │ [R1] econometrics     │  │ [S6] gpr-api (FastAPI)    │
              │ [R2] backtest-engine  │  │ [S7] BeaverX integration  │
              │ [R3] validation-tools │  │      (Kafka → agents)     │
              └──────────────────────┘  └──────────────────────────┘
```

Nguyên tắc: **Research layer (R1-R3) là repo Python thuần chạy offline** (notebook + script, không cần service hóa); **chỉ S1-S7 là production services**. Không service hóa cái gì trước khi pass cổng GO/NO-GO tương ứng.

---

## 1. DANH SÁCH THÀNH PHẦN CẦN BUILD

### [S1] news-ingestor — Thu thập báo tiếng Việt

**Tận dụng:** pipeline Vietstock RSS + BM25 sẵn có của BeaverX làm nền, mở rộng nguồn.

| Việc cần làm | Chi tiết |
|---|---|
| Mở rộng RSS realtime | Thêm VnExpress (mục Thế giới, Kinh doanh, Thời sự), CafeF, VnEconomy, Tuổi Trẻ, Thanh Niên, Báo Chính phủ |
| Crawler lịch sử (một lần) | Crawl archive theo sitemap/pagination từng nguồn, mục tiêu ≥ 2015. Đây là task nặng nhất của P2 — ước tính 1–3 triệu bài. Cần rate-limit lịch sự, proxy rotation nếu bị chặn |
| Chuẩn hóa | Dedup theo URL + simhash nội dung (tránh 1 tin đăng lại nhiều báo bị đếm trùng — đúng lỗi GDELT mắc phải); parse `published_at` chính xác đến phút (BẮT BUỘC — Lớp 2b cần intraday timestamp, không bổ sung sau được) |
| Lưu trữ | Bảng `raw_articles`, partition theo tháng |

```sql
CREATE TABLE raw_articles (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(50),          -- vnexpress, cafef, ...
  url TEXT UNIQUE,
  title TEXT, body TEXT,
  published_at TIMESTAMPTZ,    -- chính xác đến phút
  crawled_at TIMESTAMPTZ,
  simhash BIGINT,              -- dedup
  section VARCHAR(50)          -- the-gioi, kinh-doanh, thoi-su
) PARTITION BY RANGE (published_at);
```

### [S2] external-data-ingestor — Dữ liệu ngoài (cron daily)

| Nguồn | Series | Cách lấy |
|---|---|---|
| GPR daily global | GPRD, GPRD_ACT, GPRD_THREAT | File xls từ matteoiacoviello.com — cron tải thủ công/scheduled qua máy có quyền truy cập (domain bị chặn khỏi sandbox, cần chạy từ server BeaverX) |
| GPR country monthly | GPRC_USA, GPRC_CHN, GPRC_RUS, GPRC_VNM | Cùng nguồn, file country-specific 44 nước |
| Thị trường | Brent, DXY, VIX, VN-Index, VN30, USD/VND | Nguồn data sẵn có trong BeaverX + yfinance/FRED cho phần thiếu |
| A6/KĐ7 (giai đoạn sau) | Cước container (SCFI), giá đất hiếm, ETF electronics | Chỉ build khi đến kiểm định 7 |

Bảng `ext_series (series_id, date, value)` — dạng long, đơn giản nhất.

### [S3] pre-filter — Lọc sơ bộ keyword tiếng Việt (rule-based)

Mục đích duy nhất: **giảm chi phí LLM** (kiến trúc 2 lớp đúng theo paper AI-GPR). Không cần thông minh — cần recall cao (thà lọt nhiều bài không liên quan còn hơn bỏ sót).

- Từ điển v1 (~100–150 cụm): chiến tranh, xung đột, căng thẳng, trừng phạt, thuế quan, áp thuế, cấm vận, quân sự, tập trận, tên lửa, hạt nhân, đe dọa, leo thang, Biển Đông, eo biển, đàm phán thương mại, Fed, lãi suất Mỹ, OPEC... + tên nước/lãnh đạo lớn.
- Danh sách loại trừ (giảm nhiễu, học từ GPR gốc): phim, game, thể thao, kỷ niệm/lịch sử ("nhân dịp 50 năm..."), cáo phó.
- Đo lường: chạy pilot trên 10,000 bài đã gán nhãn tay 1 phần → báo cáo recall của filter. Mục tiêu recall ≥ 95%, tỷ lệ pass ước tính 10–20% tổng bài.
- Implement: 1 module Python thuần (regex + Aho-Corasick cho tốc độ), chạy như consumer Kafka hoặc batch.

### [S4] llm-scorer — Chấm điểm bài báo (thành phần lõi)

**Model chiến lược 2 giai đoạn:**
- Giai đoạn nghiên cứu/backfill lịch sử: GPT-4o-mini (đúng model paper AI-GPR đã validate), temperature=0, structured output (JSON mode).
- Giai đoạn production: đánh giá Qwen3-14B-AWQ self-host (đã có vLLM serving trong BeaverX) qua kiểm định V2 — nếu tương quan ≥ 0.85 với GPT-4o-mini thì chuyển production sang Qwen, chi phí biên ≈ 0. (Paper gốc xác nhận Llama 3.1 8B open-weight đạt tương quan >0.85 — Qwen3-14B nhiều khả năng đạt.)

**Output schema (đúng research plan Lớp 1):**
```json
{
  "score": 0.0-1.0,
  "type": "THREAT|ACT|NONE",
  "actor": "US|CN|RU|VN|...|null",
  "target": "VN|US|...|null",
  "channel": "trade|military|sanction|diplomacy|energy|null",
  "origin": "global|regional|domestic",
  "speaker": {"name": "...", "role": "us_president|fed_chair|vn_pm|..."} 
}
```

**Việc cần làm:**
1. Viết rubric tiếng Việt v1 (adapt từ prompt gốc trong paper AI-GPR — lấy nguyên scoring rubric của họ làm khung, dịch + thêm ngữ cảnh VN: Biển Đông, thuế quan, quan hệ Việt-Mỹ-Trung).
2. Batch runner: dùng OpenAI Batch API cho backfill lịch sử (rẻ hơn 50%), async runner qua Kafka cho realtime.
3. Bảng `article_scores` (FK về raw_articles, thêm cột `model_version`, `rubric_version` — bắt buộc để re-score được khi đổi rubric mà không mất bản cũ).
4. Ước tính chi phí backfill: giả sử 2M bài × 15% pass filter = 300K bài × ~$0.0001 ≈ **$30–60** (không đáng kể — đúng như paper gốc: 4.6M bài hết $450).

### [S5] index-builder — Tính chỉ số (daily cron sau khi scorer chạy xong)

Tính toàn bộ họ chỉ số theo công thức Lớp 2/2b/3/4a:

| Chỉ số | Công thức | Ghi chú |
|---|---|---|
| VN-GPR (daily/monthly) | 100 × Σs_i / N_t | N_t = tổng bài pass qua ingestor (không phải pass filter) |
| VN-GPT / VN-GPA | tách theo `type` | |
| VN-GPR_domestic / _external | tách theo `origin` | |
| BIGPR_{a→VN}, BIGPR_{VN→world} | tách theo actor/target | |
| AW-GPR | Σ(w_a·s_i)/N_t | w_a từ bảng `actor_weights` — do R1 ước lượng offline, S5 chỉ apply |
| VN-GPR⊥ | residual sau hồi quy lên GPR global/US/CN + Oil | hệ số hồi quy cũng do R1 ước lượng, S5 apply rolling |

- Rebase mean=100 trên cửa sổ 2015–2019.
- Output: bảng `gpr_indices (index_name, freq, date, value, version)` + publish Kafka topic `gpr.indices.daily`.

### [R1] econometrics — Repo nghiên cứu (offline, Python)

Không phải service. Cấu trúc repo:
```
vn-gpr-research/
  ├── data/          # snapshot từ PG, immutable theo version
  ├── notebooks/     # exploration, narrative check V3
  ├── src/
  │   ├── orthogonalize.py     # Lớp 4a
  │   ├── local_projection.py  # Jordà LP, HAC/Newey-West SE
  │   ├── tvp_var.py           # TVP-VAR connectedness (khung Cao & Vo)
  │   ├── actor_weights.py     # speaker fixed-effects → bảng w_a
  │   └── event_study.py       # cửa sổ intraday quanh published_at
  ├── tests/         # kiểm định C2: KĐ1–KĐ7, mỗi cái 1 module
  └── reports/       # kết quả versioned, cả biến thể fail
```
- Thư viện: statsmodels (LP, VAR), linearmodels (panel FE), arch (volatility); TVP-VAR connectedness có thể port từ package R `ConnectednessApproach` hoặc implement theo Antonakakis-Gabauer.
- Quy tắc sắt: mọi kết quả báo cáo phải kèm `data_version + code_commit`; OOS window (2023–2026) khóa cứng trong config, CI reject mọi thay đổi file config đó sau khi đã chạy lần đầu.

### [R2] backtest-engine — Backtest tín hiệu giao dịch

- Tận dụng evaluation pipeline sẵn có của BeaverX nếu phù hợp; nếu không, dùng vectorbt hoặc tự viết (thị trường VN cần xử lý riêng: biên độ ±7%, T+2.5, lô 100).
- 3 chiến lược theo C3 research plan (risk-off filter, sector rotation, GPT-sizing), mỗi chiến lược ≤ 3 tham số tự do.
- Walk-forward engine: tune 3 năm → test 1 năm → trượt; output chuẩn: Sharpe, MDD, hit rate, IC (5/20/60 ngày), turnover, sau phí (giả định phí 0.15% + slippage 0.1%).
- Báo cáo tự động sinh (markdown/HTML) cho mỗi run — kể cả run fail.

### [R3] validation-tools — Công cụ kiểm định V1–V4

- **Human audit (V1):** không cần build UI phức tạp — xuất Google Sheet/CSV 500–1000 bài (title + body + cột chấm điểm trống) cho 2 người Việt chấm độc lập; script tính inter-rater agreement và human-machine correlation. 1 ngày công build.
- **Model robustness (V2):** script re-score 10% mẫu bằng Qwen3-14B local, tính tương quan.
- **Narrative check (V3):** notebook vẽ chuỗi + đánh dấu 8 sự kiện mốc (HD-981 5/2014, trade war 2018, COVID 3/2020, Nga-Ukraine 2/2022, thuế quan 4/2025, đàm phán 2025-26...), review bằng mắt cùng team.
- **Convergent validity (V4):** script tương quan VN-GPR monthly vs GPRC_VNM, kiểm tra nằm trong vùng 0.5–0.8.

### [S6] gpr-api — Serving (FastAPI, chỉ build sau khi pass C2)

```
GET /v1/indices?name=VN-GPR&freq=daily&from=...&to=...
GET /v1/indices/latest              # tất cả chỉ số, giá trị mới nhất + z-score
GET /v1/articles/top?date=...       # top bài đóng góp điểm cao nhất (explainability)
GET /v1/regime                      # percentile hiện tại vs rolling 1Y, flag risk-on/off
```
Endpoint `/articles/top` quan trọng cho trust: khi agent/người dùng hỏi "tại sao hôm nay GPR cao", trả về được 5 bài gốc.

### [S7] BeaverX integration

- Kafka topic `gpr.indices.daily` → Market Agent & Quant Agent subscribe.
- Thêm 2 tool vào hệ 39+ tools: `get_geopolitical_risk(date_range)` và `explain_gpr_spike(date)`.
- Redis cache giá trị latest cho low-latency agent calls.
- Nếu KĐ5 (lead-lag) pass: thêm alert rule — global GPRD spike > ngưỡng mà VN-GPR chưa phản ánh → publish event `gpr.leading_signal` cho Quant Agent.

---

## 2. LỘ TRÌNH THỰC THI — GLOBAL-FIRST (v1.1)

**Cấu trúc engine + params:**
```
gpr-core-engine/                 # build 1 lần, country-agnostic
  ├── src/                       # R1 econometrics + R2 backtest (dùng chung mọi nước)
  ├── params/
  │   └── vn.yaml                # hệ số β^VN, θ^VN + config thị trường (biên độ ±7%, T+2.5, lô 100)
  └── corpus/                    # optional, chỉ nước nào cần domestic signal
      └── vn/                    # V-phase: rubric + scores từ báo tiếng Việt
```

### Phase GLOBAL (G1–G4): engine lõi, chỉ dùng dữ liệu có sẵn

| Sprint | Tuần | Build gì | Cổng nghiệm thu |
|---|---|---|---|
| **G1** | 1 | S2 ingestor: load GPRD daily + GPRC (US/CN/RU/VNM + toàn bộ 44 nước, lưu hết — thêm nước sau khỏi ingest lại), Oil/DXY/VIX, VN-Index/VN30/USD-VND vào PG. Khám phá dữ liệu đầu tiên: vẽ chuỗi, đánh dấu sự kiện mốc | Toàn bộ series trong PG, notebook khám phá review cùng nhau |
| **G2** | 2–5 | R1 trên input global: (a) Local Projection r^VN_{t+h} lên GPRD/GPRC các nguồn, tách GPT/GPA; (b) TVP-VAR connectedness; (c) KĐ1 (explanatory), KĐ3 (threats vs acts), **KĐ5 (lead-lag GPRD→VN-Index — giá trị thương mại cao nhất, chạy được ngay không cần corpus VN)**. GPRC_VNM dùng làm proxy tạm cho thành phần VN | KĐ1 pass trên proxy → tiếp G3; fail → dừng, đánh giá lại trước khi tốn thêm công |
| **G3** | 6–8 | R2 backtest 3 chiến lược global-only: risk-off theo GPRD percentile, sector rotation theo GPRC_USA/CHN, sizing theo GPT. Walk-forward, OOS 2023–2026 khóa cứng | IC > 0.03 & Sharpe beat benchmark → G4 |
| **G4** | 9–10 | S6 API rút gọn + S7: Kafka topic, 2 tools cho agents, alert leading-signal (nếu KĐ5 pass) | Tín hiệu global chạy thật trong Quant Agent |

### Phase VIETNAM (V1–V3): corpus tiếng Việt — chỉ khởi động sau khi G-phase chứng minh giá trị

| Sprint | Nội dung | Điều kiện khởi động |
|---|---|---|
| **V1** | S1 crawler (RSS mở rộng + khảo sát archive lịch sử); rubric tiếng Việt v1; S3 pre-filter; S4 pilot 5,000 bài; human audit | G-phase đã production; quyết định đầu tư dựa trên baseline IC của G3 |
| **V2** | Backfill lịch sử; S5 tính VN-GPR/AW-GPR/BIGPR; validation V2–V4; orthogonalization 4a | V1 pass audit |
| **V3** | KĐ2/6/7; kiểm định trung tâm: **VN-GPR⊥ có tăng IC/R² vượt trên mô hình global-only của G3 không** — con số này quyết định corpus có đáng tiền không, và là headline khi pitch ("thêm tín hiệu nội địa tăng IC từ X→Y") | V2 pass |

**Mốc mở rộng thị trường mới (Thái Lan, Indonesia...):** copy `params/vn.yaml` → ước lượng lại trên dữ liệu nước đó (GPRC 44 nước đã có sẵn trong PG từ G1) — ~1–2 tuần/nước, không cần code mới, corpus bản địa là optional.

**Nhân lực:** G-phase: bạn + 1 engineer part-time (chỉ G1, G4 cần engineering; G2–G3 là research thuần) ≈ 10 tuần. V-phase: 1 engineer full-time ≈ 2–3 tháng, chỉ commit sau khi có baseline G3.

### Lộ trình cũ (v1.0, VN-first) — giữ để tham chiếu

| Sprint | Tuần | Build gì | Cổng nghiệm thu |
|---|---|---|---|
| **SP0** | 1–2 | S2 (ingestor GPR/market data); tải + load GPRC_VNM làm baseline; khảo sát archive từng báo (độ sâu crawl được, cấu trúc sitemap) | Có chuỗi GPRC_VNM + GPRD trong PG; báo cáo khảo sát nguồn |
| **SP1** | 3–5 | S3 (pre-filter + từ điển v1); rubric tiếng Việt v1 + S4 pilot trên 5,000 bài; R3 human-audit tooling; chạy V1 | **V1 pass** (corr ≥ 0.80) — nếu fail: sửa rubric, lặp lại, không đi tiếp |
| **SP2** | 6–9 | S1 crawler lịch sử (song song từ SP1); S4 backfill toàn bộ corpus (Batch API); S5 index-builder; chạy V2, V3, V4 | **V2–V4 pass**; chuỗi VN-GPR daily ≥ 2015 hoàn chỉnh |
| **SP3** | 10–13 | R1: orthogonalization, LP, TVP-VAR, actor_weights; chạy KĐ1–KĐ7 | **KĐ1 + KĐ4 pass** → được claim explanatory power; KĐ5/6/7 báo cáo kết quả dù pass hay fail |
| **SP4** | 14–16 | R2 backtest-engine + 3 chiến lược, walk-forward | **IC > 0.03 & Sharpe beat benchmark OOS** → được đưa vào Quant Agent |
| **SP5** | 17–18 | S6 API + S7 integration + realtime scoring loop (RSS → filter → scorer → index, latency mục tiêu < 15 phút từ lúc bài đăng) | Demo end-to-end trong BeaverX; alert leading-signal nếu KĐ5 pass |
| **SP6** | sau | Nguồn mở rộng (GDELT/Polymarket/X) — mỗi nguồn 1 sprint riêng, phải chứng minh incremental IC | |

---

## 3. QUYẾT ĐỊNH KỸ THUẬT ĐÃ CHỐT & LÝ DO

1. **PG + Kafka + Redis, không thêm hạ tầng mới** — mọi thành phần map thẳng vào stack BeaverX hiện có, giảm chi phí vận hành.
2. **Research tách khỏi production** — R1/R2/R3 là repo offline có version, S5 chỉ "apply" hệ số đã ước lượng. Tránh bug kinh điển: logic nghiên cứu lẫn vào serving, không tái lập được kết quả.
3. **`model_version` + `rubric_version` trên mọi bản ghi score** — rubric tiếng Việt chắc chắn sẽ sửa vài lần sau V1; không có version thì mỗi lần sửa là mất toàn bộ lịch sử so sánh.
4. **`published_at` chính xác đến phút ngay từ đầu** — Lớp 2b (actor weights bằng event study intraday) và KĐ5 (lead-lag) chết nếu chỉ có ngày.
5. **Backfill bằng GPT-4o-mini, production cân nhắc Qwen local** — backfill là one-off ($30–60, không đáng tối ưu), production là chi phí chạy mãi (Qwen local ≈ 0 nếu V2 pass).
6. **OOS window khóa cứng bằng CI** — kỷ luật chống data snooping phải enforce bằng máy, không bằng lời hứa.

## 4. RỦI RO THỰC THI (khác với rủi ro nghiên cứu ở research plan Phần E)

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Crawler lịch sử bị chặn / archive không đủ sâu | Cao | Khảo sát ngay SP0 trước khi cam kết timeline; fallback: splice với GPRC_VNM cho giai đoạn cũ |
| Chất lượng `published_at` từ archive cũ (chỉ có ngày) | Trung bình | Chấp nhận: actor weights chỉ ước lượng trên dữ liệu từ khi có RSS realtime (2024+); lịch sử cũ chỉ dùng cho index daily |
| Rubric tiếng Việt fail V1 nhiều vòng | Trung bình | Budget 2 vòng sửa trong SP1; nếu vẫn fail → giảm scope xuống binary classification trước, scoring liên tục sau |
| Domain matteoiacoviello.com cần tải thủ công định kỳ | Thấp | Cron trên server BeaverX (không qua sandbox); tần suất monthly là đủ |
| Tải LLM realtime giờ cao điểm tin tức | Thấp | Queue qua Kafka sẵn có; SLA 15 phút là thoải mái |
