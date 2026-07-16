# 05 — BUILD ORDER (thứ tự thực thi cho Claude Code)

Tài liệu này là "cái gì làm trước, done nghĩa là gì". Đọc cùng `00_engine_design.md` (thiết kế) và `CLAUDE.md` (nguyên tắc).

Ký hiệu: 🟢 = code production | 🔬 = code research (offline, không service hóa) | ⛔ = cổng GO/NO-GO

> ## ⚠️ THỨ TỰ ĐÃ ĐỔI (2026-07-16, sau review `08` / phản hồi `09`)
>
> **Thứ tự trong file này LỖI THỜI. Nguồn chân lý: `09_review_response.md` §4.** Khác biệt chính:
>
> ```
> G0   Research Governance      ← MỚI, làm TRƯỚC mọi thứ (registry, holdout policy, claims matrix)
> G1   Ingest & Data Audit      ← +available_at/revised_at/quality_flag  [phần schema/ingest: DONE]
> G2.0 Feature foundation       ← MỚI: level/persistent/innovation/jump/surprise + tách 3 pipeline
> G2a  Global Macro             ← CHẠY LẠI với innovation; gate mới (bỏ "đúng dấu literature")
> G2b  Country reduced-form     ← TÁCH daily (GPRD only) / monthly (+GPRC_VNM)
> G2c  generic vs channel vs threat vs act-surprise
> G2.5 Structural ID (optional) ← track nghiên cứu, KHÔNG chặn G3/G4
> G3   Locked backtest          ← final holdout 2026-H1; Deflated Sharpe, SPA; benchmark non-GPR
> G4→G7  như cũ, có siết governance
> ```
>
> **Ba cổng trong file này đã bị thay:**
> - **G2a cũ** ("γ có ý nghĩa — literature xác nhận energy mạnh nhất") = confirmation bias, BỎ (review §4.6). Gate mới: pipeline đúng · IRF ổn định qua specification · CI báo đầy đủ · dấu/độ lớn CÓ giải thích kinh tế (không bắt buộc trùng kỳ vọng) · kết quả null vẫn lưu.
> - **G2b cũ** dùng GPRC_VNM cho track daily = vi phạm no-forward-fill (review §4.7). GPRC_VNM là monthly, **chỉ vào track monthly**.
> - **G3 cũ** ("IC OOS > 0.03 VÀ Sharpe beat benchmark") → "incremental IC > 0 vs baseline non-GPR, CI rõ, ổn định qua regime, dương sau phí" (review §4.8).
>
> **Và:** mọi `shock` trong G2 là **innovation**, không phải level (review §4.4). `docs/reports/G2a_global_macro.md` chạy trên level → kết luận VÔ HIỆU, phải chạy lại.

---

## G1 — INGEST CHÂN A (tuần 1) 🟢

**Mục tiêu:** mọi chuỗi dữ liệu global + thị trường vào PostgreSQL, có notebook khám phá.

### G1.1 — Schema
- [ ] Chạy `sql/001_schema_core.sql`: bảng `ext_series`, `gpr_indices`, `data_versions`.
- [ ] Bảng `ext_series (series_id TEXT, date DATE, value DOUBLE PRECISION, loaded_at TIMESTAMPTZ, PRIMARY KEY(series_id, date))`.

### G1.2 — Ingest GPR (file có sẵn)
- [ ] `ingest/gpr_daily.py`: đọc `data/data_gpr_daily_recent.xls`, load GPRD, GPRD_ACT, GPRD_THREAT vào `ext_series`. Range kỳ vọng 1985 → 2026-06-29.
- [ ] `ingest/gpr_monthly.py`: đọc file monthly 44 nước KHI user cung cấp. Parse mọi cột `GPRC_*` + GPT/GPA. **Guard:** nếu không thấy cột `GPRC_VNM` → log warning rõ ràng, không im lặng bỏ qua.
- [ ] Idempotent: chạy lại không nhân đôi (UPSERT theo PK).

### G1.3 — Ingest thị trường & kênh
- [ ] `ingest/market_data.py`: Oil (Brent), DXY, VIX, US10Y từ FRED/yfinance; VN-Index, VN30, USD/VND từ nguồn BeaverX (để config đường nối, chưa cần hardcode).
- [ ] Tất cả về `ext_series` dạng long.

### G1.4 — Notebook khám phá
- [ ] `notebooks/01_explore.ipynb`: vẽ GPRD + GPRC_VNM (khi có) + VN-Index trên timeline; đánh dấu sự kiện mốc (HD-981 2014-05, trade war 2018, COVID 2020-03, Nga-Ukraine 2022-02, thuế quan 2025-04); ma trận tương quan sơ bộ GPR vs VN-Index return.

**⛔ Cổng G1:** mọi series query được từ PG; notebook chạy hết; review chuỗi bằng mắt thấy hợp lý (đỉnh khớp sự kiện). Không pass → sửa ingest trước khi tiếp.

---

## G2 — ECONOMETRICS CHÂN A — CASCADE 3 TẦNG (tuần 2–5) 🔬

> **CẬP NHẬT (xem `docs/06_transmission_cascade_update.md`):** G2 cũ map thẳng `GPR → r_VN` (2 tầng)
> đã được thay bằng cascade 3 tầng để tách phần **tổng (global, generic)** khỏi phần **riêng
> từng quốc gia (params tự do)**. G2 nay chia làm **G2a (tầng 2 global macro)** + **G2b (tầng 3 country)**.
> Công thức đầy đủ: `docs/07_formulas_reference_v2.md` §3 (tầng 2), §4–5 (tầng 3, transmission decomposition).

**Mục tiêu:** đo tác động GPR qua 2 chặng — (1) GPR → biến vĩ mô toàn cầu (generic, bán được cho mọi
nước), (2) vĩ mô toàn cầu + shock riêng → VN-Index. Research code, chạy ra kết quả, chưa service hóa.

### G2.0 — Nền tảng dùng chung
- [ ] `econometrics/dataset.py`: load panel/timeseries từ PG, align tần suất, `load_global_macro()`
  → {oil, dxy, vix, us10y} đã transform (Δln cho giá, level VIX), xử lý weekend. **log(1+GPR) bắt buộc.**
- [ ] `econometrics/local_projection.py`: refactor thành **utility** `run_local_projection(y, shock, controls, horizons) -> IRF`
  (Jordà 2005, HAC/Newey-West SE bắt buộc). Là hàm nền cho cả tầng 2 và tầng 3, không còn là "model chính".

### G2a — TẦNG 2: GLOBAL MACRO RESPONSE (generic) 🔬
- [ ] `econometrics/tier2_global_macro.py`: LP `M_{t+h} = a + Σγ·shock + Σρ·M_lag + η` cho mỗi
  M ∈ {ΔlnOil, ΔlnDXY, VIX, ΔUS10Y}, h=0..30 ngày. Shock: GPRD, GPRD_ACT, GPRD_THREAT.
- [ ] Output: bảng γ (IRF) + đồ thị IRF từng biến vĩ mô → **deliverable "Global Macro Impact"** (không cần VN).
- [ ] (Sau, khi có S-GPR) chạy lại theo `channel`: energy → γ_oil cao; trade → γ_dxy/γ_vix cao.

**⛔ Cổng G2a:** γ có ý nghĩa (GPR shock thật sự đẩy dầu/đô/VIX — literature xác nhận energy mạnh nhất).
Ghi `docs/reports/G2a_global_macro.md`.

### G2b — TẦNG 3: COUNTRY TRANSMISSION (params riêng VN) 🔬
- [ ] `config/params/vn.yaml`: khai báo market_series, direct_shock (GPRC_VNM⊥), macro_channels, controls.
  **Không điền θ tay** — ước lượng từ tier3 rồi ghi lại.
- [ ] `econometrics/tier3_country.py`: phương trình §5.1 tách **INDIRECT** (θ·macro, qua tầng 2)
  và **DIRECT** (λ·GPRC_VNM⊥); orthogonalize GPRC_VNM khỏi global (§4.1); `mediation_analysis()`
  (Direct/Indirect/Total + bootstrap SE); variance decomposition đóng góp từng kênh.
- [ ] **KĐ1** explanatory: GPR có ý nghĩa trên VN-Index return? So GPRD vs GPRC_VNM⊥.
- [ ] **KĐ3** threats vs acts: hệ số GPT vs GPA; act mạnh & trễ hơn?
- [ ] **KĐ5** lead-lag global→VN: Granger + độ trễ GPRD spike → VN-Index. (Giá trị thương mại cao nhất.)
- [ ] **KĐ12** mediation: Indirect có ý nghĩa? Direct có ý nghĩa? (Indirect≫Direct kỳ vọng cho nền KT nhỏ mở.)

**⛔ Cổng G2b:** KĐ1 pass → tiếp G3. Fail → dừng, đánh giá lại. Ghi `docs/reports/G2b_country.md`.

### G2c — Panel VAR / TVP-VAR (bổ trợ, replicate published)
- [ ] `econometrics/panel_var.py`: panel VAR country FE (GPRC 44 nước) — Caldara-Conlisk-Iacoviello-Penn 2026.
- [ ] `econometrics/tvp_var.py`: TVP-VAR frequency connectedness (Antonakakis-Gabauer) — Cao & Vo 2025.

**⛔ Cổng G2 (tổng):** KĐ1 pass. G2a cho deliverable độc lập ngay cả khi G2b chưa pass.

---

## G3 — BACKTEST CHÂN A (tuần 6–8) 🔬

**Mục tiêu:** tín hiệu GPR có giao dịch được không (mục tiêu B). Đây là baseline IC cho MỌI chân sau.

### G3.1 — Engine backtest
- [ ] `backtest/engine.py`: walk-forward (tune 3 năm → test 1 năm → trượt); xử lý đặc thù HOSE (biên độ ±7%, T+2.5, lô 100, phí 0.15% + slippage 0.1%).
- [ ] Metrics: Sharpe, MaxDD, hit rate, IC (5/20/60 ngày forward return), turnover.

### G3.2 — 3 chiến lược (mỗi cái ≤ 3 tham số tự do)
- [ ] `backtest/strategies.py`:
  - `risk_off_filter`: giảm equity khi GPRD > percentile 90 rolling 1 năm.
  - `sector_rotation`: long phòng thủ / short xuất khẩu khi GPRC_USA hoặc GPRC_CHN spike.
  - `gpt_sizing`: giảm dần exposure theo mức GPT (threat kéo dài).
- [ ] Benchmark so sánh: buy-hold VN-Index; chiến lược dùng VIX/DXY đơn thuần.

### G3.3 — Báo cáo
- [ ] Sinh `docs/reports/G3_baseline.md` tự động: bảng metrics OOS mọi chiến lược + biến thể fail (không giấu).

**⛔ Cổng G3:** IC OOS > 0.03 VÀ Sharpe beat benchmark → G4 (đưa vào agent). Fail → GPR chỉ dùng risk-monitoring (mục tiêu A), không làm alpha; vẫn tiếp G4 nhưng với vai trò context, không phải signal.

---

## G4 — SERVING TỐI GIẢN (tuần 9–10) 🟢

- [ ] `sql/002_indices.sql` nếu cần thêm cột.
- [ ] `indices/builder.py`: cron tính chỉ số từ ext_series → `gpr_indices` + z-score, percentile rolling.
- [ ] `api/main.py` (FastAPI): `GET /v1/indices`, `/v1/indices/latest`, `/v1/regime`.
- [ ] Kafka producer: topic `gpr.indices.daily`.
- [ ] 2 tools cho BeaverX agents: `get_geopolitical_risk(date_range)`, `explain_gpr_spike(date)`.
- [ ] Nếu KĐ5 pass: alert rule `gpr.leading_signal` khi GPRD spike mà VN-Index chưa phản ánh.

**⛔ Cổng G4:** demo end-to-end trong BeaverX; Quant Agent nhận được tín hiệu. **Đây là sản phẩm chạy thật đầu tiên — dừng ở đây vẫn là hệ hoàn chỉnh.**

---

## G5 — CHÂN B: S-GPR (tuần 11–15) 🔬→🟢

Xem `docs/00_engine_design.md §2` cho thiết kế đầy đủ (nguồn, rubric, prompt, công thức tổng hợp).

- [ ] `ingest/statements/`: B1 UNGDC, B2 BIS speeches, B3 White House, B4 Trump archive, B5 MOFA-CN (v1 chỉ cần 5 nguồn này).
- [ ] `sql/003_statements.sql`: bảng `statements`, `statement_scores`.
- [ ] `scoring/statement_scorer.py`: prompt rubric §2.4, structured JSON output, GPT-4o-mini backfill + async realtime.
- [ ] Human audit 500 mẫu (tooling dùng chung V-phase R3): agreement + human-machine corr ≥ 0.80. Fail → gộp bậc 7→5.
- [ ] `indices/s_gpr.py`: S-GPR_{a→b}, S-CONC (giữ riêng chiều hòa giải), S-GPR_global.
- [ ] **KĐ8** S-GPR lead GPR (raison d'être của chân B).

**⛔ Cổng G5:** KĐ8 pass HOẶC incremental IC (A+B vs A) > 0 → giữ, service hóa. Không → đóng băng chân B, giữ code trong research.

---

## G6 — CHÂN C: EVENTS + FUSION cơ bản (tuần 16–19) 🔬

- [ ] `ingest/gdelt.py`: BigQuery aggregate theo (actor1, actor2, month), chống đếm trùng (NumSources ≥ 3). KHÔNG kéo raw firehose.
- [ ] `sql/004_events.sql`: `gdelt_pair_monthly`, `ladder_state`.
- [ ] (Optional) `scoring/history_reconstruct.py`: LLM reconstruction pre-1979, cross-check GDELT (corr ≥ 0.6) + audit 100 sự kiện.
- [ ] `econometrics/ladder.py`: Escalation Ladder v1 rule-based (ngưỡng trong config version-hóa) + sensitivity analysis.
- [ ] `econometrics/surprise.py`: Surprise Index = GPA − E[GPA | GPT, S-GPR, ladder], rolling, no leakage.
- [ ] **KĐ9** Surprise > GPA thô (test cả S&P 500 làm đối chứng); **KĐ10** ladder-conditional threat.

**⛔ Cổng G6:** incremental IC từng khối > 0.

---

## G7 — DIVERGENCE + HỢP NHẤT (tuần 20–22) 🔬→🟢

- [ ] `indices/divergence.py`: EARLY_WARN, MEDIA_HYPE, SILENT_RISK (design §4.3).
- [ ] **KĐ11** mỗi divergence signal qua walk-forward, giữ IC OOS > 0.
- [ ] Hợp nhất serving; sinh `docs/reports/incremental_IC.md` — bảng A→A+B→A+B+C→+fusion. **Đây là tài liệu pitch chính.**

---

## V-PHASE (sau, chỉ khi G-phase chứng minh giá trị)

Corpus tiếng Việt theo `docs/01_research_methodology.md` + `docs/02_engineering_plan.md`. Kiểm định trung tâm: VN-GPR⊥ tăng IC vượt baseline G3/G7 bao nhiêu. Không khởi động trước khi có baseline.

---

## Định nghĩa "DONE" chung cho mọi task
1. Có test (với công thức: test trước khi code).
2. Idempotent (ingest/build chạy lại không hỏng dữ liệu).
3. Kết quả nghiên cứu có `data_version` + git commit.
4. Không rò rỉ OOS window.
5. Không đưa công thức chưa-pass-cổng vào đường production.
