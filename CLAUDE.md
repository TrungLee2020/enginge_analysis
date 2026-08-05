# CLAUDE.md — GPR Global Engine

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> File này là ngữ cảnh chính cho Claude Code. Đọc trước khi làm bất cứ việc gì.
> Tài liệu thiết kế đầy đủ nằm trong `docs/`. Khi có mâu thuẫn, `docs/00_engine_design.md` là nguồn chân lý.
> Công thức: `docs/07_formulas_reference_v2.md` (v1 đã archive).

## Dự án là gì

Xây **GPR Global Engine**: hệ thống lượng tử hóa rủi ro địa chính trị từ tin tức/phát ngôn/sự kiện quốc tế thành các chỉ số định lượng, đo tác động lên thị trường tài chính (đầu tiên: VN-Index), và sinh tín hiệu cho hệ multi-agent BeaverX.

Kiến trúc **1 engine lõi (country-agnostic) + n bộ tham số quốc gia**. Xây phần GLOBAL trước (dữ liệu công khai, chi phí ≈ 0), tham số Việt Nam ước lượng sau.

## Nguyên tắc bất biến (KHÔNG vi phạm)

1. **Research tách khỏi Production.** Công thức tự phát minh (S-GPR, Escalation Ladder, Surprise Index, exposure) được thử trong `src/gpr_engine/econometrics` + notebooks TRƯỚC. Chỉ đưa vào service (ingest/scoring/indices production) sau khi pass cổng kiểm định. Không code cứng ý tưởng chưa test vào đường production.
2. **Không xây lại cái đã có.** GPR/GPRC/AI-GPR do Caldara-Iacoviello publish — chỉ INGEST, không tự tính lại từ báo chí quốc tế. Giá trị tự build nằm ở chân B (phát ngôn) và chân C (sự kiện) và fusion.
3. **Data split khóa cứng, final holdout chạm 1 lần.** (Sửa theo `docs/08` §4.8 — thay `oos_start: 2023` cũ, hợp lệ vì chưa backtest nào từng chạy.) Development 2015–2020 / Validation 2021–2023 / Pseudo-OOS 2024–2025 / **Final holdout 2026-H1 — chạm ĐÚNG 1 LẦN, sau đó KHÔNG sửa model theo kết quả của nó**. Config ở `config/backtest.yaml`, không sửa. Kết quả xấu trên holdout = báo cáo kết quả xấu, không phải lý do tinh chỉnh.
4. **Versioning bắt buộc.** Mọi bảng điểm số có `model_version` + `rubric_version`. Mọi kết quả nghiên cứu kèm `data_version` + git commit.
5. **`published_at` chính xác đến phút** với mọi nguồn daily (cần cho event study actor-weighting và lead-lag). Không bao giờ chỉ lưu ngày với nguồn realtime.
6. **Mỗi lớp dữ liệu mới phải chứng minh incremental IC.** A → A+B → A+B+C → +fusion. Lớp nào không tăng IC out-of-sample thì đóng băng, không ép vào production.
7. **Không hard-code trọng số người phát ngôn.** `w(role)` khởi tạo bằng thứ bậc, nhưng giá trị cuối phải ước lượng từ event study (speaker fixed-effects).
8. **Truyền dẫn theo cascade 3 tầng, KHÔNG map thẳng `GPR → r_VN`.** Shock đi qua tầng vĩ mô toàn cầu (Oil/DXY/VIX/US10Y) trung gian. **Tầng 1–2 = ENGINE generic** (Global Macro Impact, ước lượng 1 lần, country-agnostic); **Tầng 3 = PARAMS riêng từng nước** (β, θ, λ là hệ số tự do ước lượng từ dữ liệu, mỗi nước một `config/params/<country>.yaml`, KHÔNG điền tay). Tầng 3 tách **BA** hệ số, không phải hai: `β` global-direct (global shock đánh thẳng, không qua macro) · `θ` indirect (qua kênh vĩ mô) · `λ` domestic-direct (`GPR^{c,⊥}` đã orthogonalize). `GPR^{c,⊥}` là phần RIÊNG của nước c — KHÔNG phải tác động trực tiếp của global shock; gộp β với λ là lỗi (`docs/08` §4.2). Indirect effect tính bằng **tích chập** `Σ_M Σ_s γ(s)·θ(h−s)`, KHÔNG nhân hai hệ số cùng horizon (`docs/08` §4.1). Xem `docs/06`, `docs/07_formulas_reference_v2.md`.

9. **Shock = innovation, KHÔNG phải level.** `ln(1+GPR)` chỉ là MỨC — gộp tin mới + tin lặp + phần đã dự báo + regime. Đưa level vào hồi quy rồi gọi hệ số là "tác động của cú sốc" là sai khái niệm (`docs/08` §4.4). Mọi hồi quy shock dùng `INNOVATION = LEVEL − E_{t-1}[LEVEL]` (hoặc GPA_SURPRISE, JUMP). Kỳ vọng `E_{t-1}` fit rolling, chỉ dùng dữ liệu quá khứ. **Hệ quả:** report `docs/reports/G2a_global_macro.md` chạy trên level → kết luận "GPRD coincident, không leading" VÔ HIỆU, phải chạy lại.

10. **KHÔNG forward-fill monthly → daily.** Tạo persistence giả, lead-lag giả, SE sai (`docs/08` §4.7). Tách 3 pipeline: daily financial / monthly macro / event-intraday. **Hệ quả cứng: daily backtest VN KHÔNG được dùng GPRC_VNM** (nó là monthly). Daily country shock phải từ AI-GPR daily, bilateral daily, hoặc corpus báo Việt (V-phase). GPRC_VNM chỉ vào track monthly.

11. **`available_at`, không phải `date`.** Backtest chỉ dùng dữ liệu khi `available_at <= decision_time`. Dùng `date` làm proxy = look-ahead bias. GPR daily publish trễ ~1 ngày; GPRC monthly của tháng M chỉ biết sau khi tháng M kết thúc. Mọi loader point-in-time đi qua `load_series(..., as_of=...)`.

12. **Chỉ claim đúng mức nhận dạng.** `measurement ≺ association ≺ prediction ≺ structural response ≺ causal effect`. Reduced-form LP → gọi "transmission decomposition"/"predictive", **KHÔNG gọi "causal"** cho tới khi có structural ID (LP-IV/proxy-SVAR, G2.5 optional). Ma trận đầy đủ: `docs/07_formulas_reference_v2.md` §6.4. Variance decomposition dùng Shapley/LMG/FEVD, KHÔNG dùng `θ²Var(M)/Var(r)` (bỏ covariance, tổng có thể >100%).

## Phân biệt 2 mục tiêu (đặt kỳ vọng đúng)

- **Mục tiêu A — Chỉ số/phân tích** (như một GPR index hiển thị & giải thích được): DỄ, gần như chắc chắn đạt. Đánh giá bằng human-audit, convergent validity, narrative check.
- **Mục tiêu B — Tín hiệu giao dịch** (sinh alpha): KHÓ, là giả thuyết phải kiểm định. Đánh giá bằng IC/Sharpe out-of-sample. Không đảm bảo trước.
- Nếu chỉ đạt A: vẫn có sản phẩm giá trị (chỉ số rủi ro địa chính trị realtime — điểm khác biệt khi pitch). Đừng ép B bằng cách overfit.

## Stack (khớp hạ tầng BeaverX)

Python 3.11+, PostgreSQL, Kafka, Redis, FastAPI. Econometrics: statsmodels, linearmodels, arch, pandas, numpy. LLM scoring: OpenAI SDK (GPT-4o-mini cho backfill) + vLLM/Qwen3-14B (production nếu pass V2). Backtest: vectorbt hoặc tự viết.

## Trạng thái hiện tại (cập nhật 2026-08-05)

### 🐛 6 bug thật vá trong pipeline serving (rà lại sau khi ship) + ✅ AI-GPR daily xác minh trên file thật

**Rà lại `pipeline/news_pipeline.py` + `service/*.py` sau khi ship (2026-08-05), tìm và vá 6 bug thật** (không phải giả thuyết — tái hiện trước khi vá, có test khóa lại):
- `published_at` tz-naive làm crash (Statement cho phép naive, phần còn lại pipeline là UTC tz-aware) — chuẩn hóa tại ranh giới (`_as_utc`), KHÔNG đổi hợp đồng `Statement` (phá test cũ).
- `ext_series`/`statement_scores` cho phép nhiều `data_version`/`model_version` cùng ngày/tin — không lọc thì `JUMP`/S-GPR rolling đếm trùng. Sửa bằng `DISTINCT ON` lấy bản mới nhất.
- `process_news_item_live` ghi đè `ladder_state` bằng 0 giả khi tính hỏng (vd role lạ) — thêm cờ `ladder_computed`, chỉ ghi DB khi tính thành công thật.
- `speaker_role` lạ, chain-A GPRD cũ (`chain_a_stale` flag mới), Kafka publish fire-and-forget (thêm `flush()` + `on_delivery`, raise rõ khi không xác nhận được).
- 328 test pass. Xem lịch sử commit trên branch để chi tiết từng bug.

**AI-GPR — chỉ số tổng hợp daily + monthly (docs/16) — ⛔ blocker cũ đã gỡ cho phần này.** Tải cả 2 file thật (2026-08-05): daily (vintage `13b8e8b48d41`, 1960-01-01..2026-07-31) + monthly (vintage `92b9ba3bd38f`, 1960-01-01..2026-07-01) — **cùng schema hệt nhau**, chỉ khác tần suất. Lộ ra **schema giả định trước đó sai hoàn toàn** (`AIGPR`/`AIGPRT`/`AIGPRA` giả định ↔ `GPR_AI`/`THREATS_GPR_AI`/`ACTS_GPR_AI` thật, cột ngày `Date` không phải `date`) — đã sửa `AI_GPR_COLUMNS` + thêm `load_ai_gpr_monthly()` (dùng chung `_load_ai_gpr()` với bản daily) + test khớp file thật.

**⚠️ docs/16 §3 tự đính chính lần 2 — tiền đề "Country index daily" SAI.** Trang download thật liệt kê `ai_gpr_country_monthly.csv`/`ai_gpr_bilateral_monthly.csv` — **monthly**, không phải daily như v1.1 khẳng định (đây là 3 file "Country Decompositions" KHÁC với chỉ số tổng hợp daily/monthly đã ingest ở trên). Kết luận "gỡ ràng buộc #10 cho VN daily track" **rút lại** — #10 vẫn cấm, `vn_market_series_missing` KHÔNG phải blocker duy nhất còn lại. Điểm ĐÚNG: Oil GPR theo vùng **thật sự có ở daily** (8 vùng, không phải 13 như bảng cũ ghi — xác nhận sai trên cả 2 file) — ứng viên thật cho channel routing kênh energy ở γ. Chưa tải: 3 file "Country Decompositions" (country×vai trò, country×8-loại-sự-kiện, bilateral) — cần trước khi làm gì tiếp với chúng.

320 test pass (2 test mới cho `load_ai_gpr_monthly`).

**Domain `matteoiacoviello.com` bị chặn ở egress policy của sandbox Claude Code** (xác nhận qua `curl $HTTPS_PROXY/__agentproxy/status`, không phải trang chặn bot) — file AI-GPR bắt buộc tải tay + upload vào phiên, không tự fetch được.

## Trạng thái trước đó (2026-08-04)

### 🏭 Pipeline serving đầu tiên — "1 tin vào → GPR + khuyến nghị vĩ mô → VN", đẩy Kafka

Module mới `pipeline/` + `service/` (không sửa logic kinh tế lượng đã có, chỉ ghép nối):
`pipeline/news_pipeline.py` (`process_news_item`, thuần + inject I/O — test bằng fake,
`process_news_item_live` nối Postgres/file γ thật) → chấm (`scoring.statement_scorer`)
→ S-GPR + Escalation Ladder (`indices.s_gpr` + `econometrics.ladder`) → γ tầng 2
(`pipeline/gamma_lookup.py`) → VN tầng 3 định tính (`pipeline/vn_exposure.py`) →
3 đoạn văn bản qua `reporting/composer.py` (`compose_measurement_card` +
`compose_model_brief` + **`compose_vn_note` mới**, tầng `vn_note` claim=`association`).
I/O: `service/store.py` (Postgres, schema `sql/002_schema_serving.sql`:
`statements`/`statement_scores`/`ladder_state`/`news_assessment`) +
`service/kafka_io.py` (`confluent-kafka`, publisher injectable). Entrypoint thật:
`scripts/run_news_service.py` (đọc/ghi Kafka qua `bootstrap.servers` — hoạt động
như nhau dù broker chạy KRaft hay ZooKeeper, client không biết chế độ nào).
`scoring/statement_scorer.py::openai_chat_client` thêm `base_url`/`api_key` — trỏ
được sang endpoint OpenAI-compatible khác, model chọn qua env `GPR_LLM_MODEL`.

**Hai giới hạn THẬT, cố ý không che (đọc trước khi tin output):**
- Bảng γ tầng 2 hiện có (`docs/reports/data/t2_full_holm_*.csv`) tách theo
  `channel ∈ {pooled, act, threat}` (biến thể GPRD dùng làm shock) — **không**
  tách theo kênh truyền dẫn energy/trade/financial/military. `gamma_lookup.
  commitment_to_gamma_channel` là PROXY (announced_action→act,
  rhetoric/conditional→threat), không phải cùng một trục dữ liệu — ghi rõ
  trong `sample_caveat` của mọi Model Brief pipeline sinh ra.
- VN (tầng 3) **chưa định lượng**: `config/params/vn.yaml` chưa có mục
  `fitted:`, `build_monthly_panel()` chưa có cột lợi suất VN-Index thật. Pipeline
  chỉ nêu kênh phơi nhiễm + hướng định tính (đúng nguyên tắc skill
  gpr-macro-assessment: không tham số ước lượng → không claim định lượng).
  Analogue lịch sử theo từng tin (`econometrics/analogue.py`) cũng chưa nối —
  cần panel tháng dựng từ FRED, quá nặng để chạy mỗi tin; để trống có chủ đích.
- 306 test pass (18 test mới ở `tests/pipeline/`). Không có Postgres/Kafka
  sống trong sandbox để test end-to-end thật — cùng giới hạn với `ingest/*.py`
  vốn cũng chưa từng có test DB thật.

## Trạng thái trước đó (2026-08-03)

### 📄 `docs/16` — AI-GPR (Iacoviello & Tong 2026) đổi hướng một phần kế hoạch

Tác giả gốc của GPR publish bản LLM của chính chỉ số đó + dữ liệu công khai. Ba khối thành **ingest thay vì build** (LLM scoring tin tức, kênh energy, country sub-index). Đọc `docs/16` trước khi làm gì liên quan chân A.

- **⛔ Blocker mới, chặn cả `docs/16` §9 Phase 1: chưa ai tải dữ liệu AI-GPR.** `load_ai_gpr_daily()` đã có nhưng `AI_GPR_COLUMNS` là schema **giả định** — lần tải đầu phải chạy `describe_ai_gpr_file()` đối chiếu. Cố ý **không tự fetch**: trang cập nhật định kỳ, fetch ngầm làm report cũ mất tái lập (#4). Registry: `data_blockers.ai_gpr_data_unverified`.
- **`docs/16` §2.1 đã tự đính chính** sau khi kiểm bằng dữ liệu dự án (`docs/reports/E2_component_decomposition_e73a0a307fc3.md`). Doc lập luận persistent > shock nên `INNOVATION` là "nửa yếu" → **cơ chế đúng** (`corr(β_LEVEL, β_INNOVATION)=0.9985` dưới lag-aug — FWL), **kết luận định lượng sai**: hệ số thô của hai thành phần có `Var` lệch ~10 lần nên không so được; chuẩn hóa thì **48.9% ô đảo chiều**. Cùng tai nạn thang đo với `LEVEL+JUMP`.
- **Spec kép (`docs/16` §2.2) — code xong, chờ dữ liệu.** `shocks.delta_decomposition`: `Δ LEVEL = ANTICIPATED + SURPRISE`, **SURPRISE ≡ `innovation()`** nên hai thành phần cộng lại bằng *đúng* Δ LEVEL (đồng nhất thức, test khóa). Phân rã trên **sai phân**, không trên mức. So sánh hai hệ số **bắt buộc chuẩn hóa** (`standardized_contribution`).
- **`DEC-2026-08-03-dual-component`** amend `DEC-2026-08-02-shock-axis`: trục SHOCK chính → robustness; **giữ nguyên** điều kiện `lag_augmented`. `SCA-01.primary_cell.shock` **vẫn UNRESOLVED** — chốt bằng spec kép là chốt bằng *thiết kế* chứ không bằng E1c-exo (khóa bằng test).
- **Tầng 4 có thân (2026-08-03):** `econometrics/analogue.py` (M5) + `reporting/{guard,composer}.py` (M6). **Guard P1 giờ chạy RUNTIME**, không còn là test rời chép lại logic ở mỗi script — `NarrativeBuilder.render()` là cửa duy nhất lấy text ⇒ quên gọi guard là không thể. Composer có **ba lớp bắt ba loại lỗi khác nhau**: Guard P1 bắt **số** bịa · `assert_claim_ceiling` bắt **từ ngữ** vượt mức nhận dạng (không số nào sai) · `check_component_labelling` bắt gọi ANTICIPATED là cú sốc.
- 263 test pass.

## Trạng thái trước đó (2026-08-02)

**`docs/15` là bản đọc-trước cho hướng global** (4 tầng: ingest → LLM đo → công thức truyền dẫn → nhận định). §5 = chữ ký ĐÃ KÝ, §6 = khoảng trống code, §7 = đọc bảng γ.

### ⛳ Bảng γ đầu tiên ĐÃ TỒN TẠI — `docs/reports/T2_full_f2579b30928f.md`

Phase 1a chạy xong 2026-08-02 (`scripts/run_t2_full.py`). Mẫu **231 tháng** (2007-02→2026-06), 3600 hàng γ + 6000 hàng phân vị. **Chờ human review** (mục cuối report).
- Ô đồng thuận cả ba thước đo: **GPR_ACT → IP, h=2, âm**, sống sót battery EPU — cùng hiện tượng E0 replication nhưng mẫu/suy diễn khác, và tách được ACT≠THREAT.
- **Giá tài sản 0/4** ở cả ba thước đo (ngược G2a cũ level-based — cái đó đã vô hiệu). Human review quyết: thông tin thật hay mất power.
- **KHÔNG đọc "LEVEL+JUMP thắng 6 ô" là chốt ô chính** — `primary_cell.shock` vẫn UNRESOLVED, trọng số LEVEL+JUMP là tai nạn thang đo (registry `level_plus_jump_composition`).
- Chi phí mẫu 231 là CÓ CHỦ ĐÍCH: LEVEL+JUMP ăn 120 tháng warmup + EPU global từ 1997. Một mẫu duy nhất là điều kiện để bản a/b và ba thước đo so được (docs/14 §2 1a).

### ✅ 4 quyết định governance đã ký (2026-08-02), khóa máy trong registry `decisions:`

`DEC-2026-08-02-shock-axis` (g0 §7.1=**A**, SHOCK là trục báo cáo) · `-holm-family` (docs/14 §6.6=**B**, họ = nhóm outcome pre-register) · `-chanb-window` (g0 §7.2=**(i)+(ii)**) · `-sources-trading` (Trump+MOFA CN; bỏ tín hiệu giao dịch). Sửa/rút phải cập nhật `LOCKED_DECISION_IDS` cùng commit.
**Còn mở:** docs/14 §6.2 người chấm mẫu thứ hai — cần con người, không ủy quyền máy được.

- **M10 done (2026-08-02):** `econometrics/multiplicity.py` — `holm()` + `holm_by_family()`. FWER dưới phụ thuộc **bất kỳ**, không bootstrap, KHÔNG dùng `arch`/SPA/StepM (chúng dựng cho so nhiều *chiến lược*, không phải 3–8 outcome). `family` **cố ý không có mặc định**: chọn họ sau khi thấy p-value là HARKing. `PREREGISTERED_OUTCOME_FAMILIES` (4/3/1) để sẵn cho lựa chọn B của `docs/14` §6.6 — dùng khi ký.
- **M8/M9 giờ mới thật sự dùng được (2026-08-02):** `estimate_tier2`/`estimate_tier3` trước đó **không truyền** `inference`/`simultaneous`/`method`/`tau`/`lags` xuống `run_local_projection` → bảng γ 1a chỉ chạy được bằng đúng cái inference mà `SCA-01.lp_inference` nói là sai. Đã nối; **mặc định vẫn `hac`/OLS/không sup-t**, report cũ không đổi.
- **Hai lỗ im lặng sup-t đã bịt:** (1) `simultaneous=True` + `inference="hac"` từng trả `beta ± c·se_HAC` — trộn Ω của EHW với SE của HAC → giờ **raise**; (2) `simultaneous=True` + `return_all=True` tính hàm ảnh hưởng xong rồi **vứt** (đường tầng 3 đi) → giờ trả dải cho mọi hệ số, mỗi hệ số một `supt_c` riêng.
- **`estimate_tier2(inference="lag_augmented")` ép `macro_lags=0`** (raise nếu >0): lag augmentation tự thêm lag của y, giữ `macro_lags` sinh cột **trùng khít** → `pinv` không báo lỗi mà chia đôi hệ số, SE mất nghĩa.
- **Chân B hết stub trên đường LLM (2026-08-02):** `scoring/statement_scorer.py` (encoder→LLM temp 0.1, JSON strict, contamination trong prompt, `training_cutoff` bắt buộc, cache 5 trục version) · `indices/s_gpr.py` (công thức docs/00 §2.5, 2 chiều không net, `w(role)`=INIT #7, `expanding_percentile` **strict `<`** vì zero-inflation) · `econometrics/ladder.py` + `config/ladder_v1.yaml` (rule-based, ngưỡng version-hóa; S1/S3 chưa có ngưỡng — chờ user; chưa GDELT nên S2 không bắt được, S4 bắt qua JUMP chân A). Test fake LLM, không mạng. **Taxonomy kênh chỏi nhau** docs/00 (6) vs docs/14/15 (4) — mapping 6→4 chỉ điền cặp hiển nhiên, còn lại None chờ chốt (docs/15 §6.2b).
- **Lỗ im lặng thứ ba (2026-08-02):** QuantReg (IRLS) không hội tụ thì statsmodels chỉ `warn` rồi **trả hệ số vòng lặp cuối** — số chạy thẳng vào report, warning bay lên stderr rồi mất. `run_local_projection` giờ trả cột `converged`; bảng in `‡` thay vì số (386/6000 hàng phân vị của T2-full rơi vào đó).
- 196 test pass.
- **Chưa làm:** human review bảng γ · §6.2 người chấm thứ hai → 2c chân B · 1b tier3 (chờ chuỗi thị trường pilot WIG/IPSA) · M5–M7 tầng 4 (analogue/composer/track record). Xem `docs/15` §6.

## Trạng thái trước đó (2026-07-21)

**Hướng sản phẩm giờ do `docs/14` v1.2 chi phối** (docs/13 hạ xuống refinement, không chặn). Đọc `docs/14` trước khi làm tiếp; §9 là nhật ký thi công, §6 là các quyết định đang chờ user.

- **M0 done (2026-07-21):** `data_files.py` thêm outcome vĩ mô thực (`load_real_macro_monthly`/`transform_real_macro` — IP/CPI/kỳ vọng lạm phát) + benchmark battery (`load_benchmark_monthly`/`transform_benchmark` — EPU US/Global). Cascade trước đó chỉ có KÊNH tài chính, chưa chạm outcome vĩ mô. `ip = 100·Δln(INDPRO)` **đúng transform E0** — đừng đổi, lệch là mất giá trị cổng E0.
- **Panel monthly đổi được nước (2026-07-21):** `build_monthly_panel(country="POL")`, mở khóa Phase 1b. Đổi nước **chỉ được đổi cột λ** — tầng 1–2 generic (#8), khóa bằng `test_panel_country_switch_changes_only_lambda_column`.
- **M8 + M9 done (2026-07-21):** `local_projection.py` thêm `inference="lag_augmented"` (MO-PM 2021: lag của **cả y lẫn shock** + HC1 thay HAC), `simultaneous=True` (dải sup-t MO-PM 2019, Ω từ hàm ảnh hưởng, `seed` cố định), `method="quantile"`. **Mặc định vẫn `"hac"`** — report cũ không đổi.
- **⚠️ `docs/14` v1.1 §1.1 từng liệt kê sai 3 thứ là "đã có"**: LP lag-augmented/sup-t, `arch` SPA/StepM, quantile. v1.2 trả về mục thiếu; M8/M9 giờ đã xong, **còn M10** (bội giữa outcome).
- **3 quyết định chờ user:** `g0` §7.1 SHOCK mặc định LEVEL hay làm trục báo cáo (chặn 1a/1c, khuyến nghị "làm trục") · `g0` §7.2 chân B mất development window do cutoff scorer × split (chặn 2c) · `docs/14` §6.6 định nghĩa họ kiểm định cho Holm (chặn M10, khuyến nghị dùng nhóm outcome đã pre-register). **Registry chưa sửa cho tới khi chốt.**

## Trạng thái trước đó (2026-07-19)

**Bối cảnh:** review ngoài (`docs/08`) chỉ ra 8 lỗi 🔴 → sửa xong ở Phase F. Công thức chân lý: `docs/07_formulas_reference_v2.md` (v2.1, v1 archived). Thứ tự build: `docs/10` §4 (Phase F→D), giờ **product plan `docs/11` v2.1 chi phối hướng sản phẩm** và `docs/12` (specification curve) là protocol pre-registered cho suy diễn tầng 2. Đọc 11 + 12 trước khi làm tiếp econometrics.

- **G1 + Phase F + D1–D3 + E1 done.** Ingest ×3, schema `ext_series` (available_at/data_version…), `load_series(as_of=)` point-in-time, `backtest.yaml` split 4 tầng khóa máy — tất cả xong. ~50 test pass.
- **G2.0 (D2) done:** `econometrics/shocks.py` — `LEVEL/PERSISTENT/INNOVATION/JUMP` + `gpa_surprise_v1`, rolling no-leakage. PERSISTENT = AR(p), **p chọn bằng BIC trong trần parsimony p=5** (KHÔNG AIC — AIC/BIC đuổi biên với daily; robustness đã chạy). Order pre-registered **GPRD=5, GPRD_ACT=5, GPRD_THREAT=2**, khóa ở `config/hypothesis_registry.yaml`.
- **G0 (D1) done:** `config/hypothesis_registry.yaml` + `docs/g0_governance.md` + `tests/test_registry_locked.py` (khóa máy giống config-lock). Pre-register KĐ1/3/5/12.
- **G2a rerun (D3) done, CHỜ HUMAN REVIEW:** `docs/reports/G2a_innovation_*_ar5-5-2.md`. GPRD innovation → macro: VIX kênh mạnh nhất (13/31 h) nhưng **dấu âm ở h dài — phản trực giác, cần soi**. Verdict = PENDING HUMAN REVIEW (máy chấm 1/2/3/5; user quyết 4/6). Mục human review còn trống.
- **E1 done:** `docs/reports/E1_shock_diagnosis_*.md`. Bằng chứng cứng: cú sốc Hormuz (GPRD→500.8 ngày 2026-03-02) NẰM TRONG mẫu G2a mà γ(oil)≈0. **AR(5) nén INNOVATION xuống 2.77× ngày thường trong khi JUMP giữ percentile 99.9** → JUMP nên là shock chính (docs/11 §5.2 KĐ-N1).

- **E1b archived/superseded:** ngoài lỗi episode nội sinh của docs/13, code cũ còn gắn nhãn `LEVEL+JUMP` cho `INNOVATION+JUMP`. Contract đã khóa lại thành `LEVEL+JUMP := LEVEL + JUMP`; report E1b cũ chỉ là artifact lịch sử, không dùng chốt ô chính.

- **`build_monthly_panel()` implemented** (2026-07-19): track monthly, grid đầu-tháng thật (KHÔNG forward-fill, #10). GPR tháng M được canh information-time vào bucket M+1. Cột: `GPR_INNOV` (β), `GPRC_VNM_ORTH_INNOV` (λ), macro tổng hợp tháng. Rolling orthogonalization/vintage là Phase 2; test mới chưa được chạy trong phiên sửa này.
- **E0 replication headline PASS** (2026-07-19): `scripts/run_e0_replication.py` — tái lập C-I 2022 (GPR→IP giảm h=1,2 p<0.10, đáy β=−0.37 h=2). **E0 alignment diagnostic PASS** tại `docs/reports/E0_alignment_diagnostic_e73a0a307fc3_c93a877.md` (raw h=2 → aligned h=1), nên blocker timing M+1 đã gỡ.
- **docs/13 self-review + E1c** (2026-07-19): thiết kế AUC + gold set giữ nguyên, nhưng bản endo cũ bị vô hiệu bởi bug `LEVEL+JUMP`. Phải chạy lại endo sau contract fix; exo vẫn chờ gold set. **ô chính SCA-01 = UNRESOLVED**.

**⚠️ Nợ đường tới hạn (docs/13 §5.1 — đường găng MỚI):**
- **`data/gold_events.csv`** chưa có → chặn E1c-exo → chặn chốt ô chính → chặn lưới. **KHÔNG phải việc code**: cần 2 người dựng tay, KHÔNG tra GPRD (docs/13 §2.2, cổng G-Gold). Claude tự dựng = vi phạm chính nguyên tắc ngoại sinh.
- **Lưới SCA-01 `blockers=[E1c_endo_rerun, gold_events_csv, E1c_exo, primary_cell_shock_resolved]`** — chưa được chạy.
- Còn: protocol_commit docs/12 (chờ commit). Lỗi Romano-Wolf đã sửa; holdout đã ghi g0 §2 (tách track ngày/tháng).
- **E0 aligned diagnostic** (Caldara-Iacoviello, docs/11 §5.8) — PASS; không còn chặn lưới.
- **Entry SCA-01 vào registry** (docs/12 §10) + Guard-P1 test cho report generator.
- **Quyết định USER (docs/11 §13):** holdout A/B/C cho 2026-H1 (Hormuz làm nó thành regime đơn lẻ) — phải ghi `g0_governance.md` TRƯỚC khi chạm holdout / chạy lưới; nới #6 cho chân B; bỏ tín hiệu giao dịch.
- **Lỗi tham chiếu docs/12:** nói "thay thế Romano-Wolf ở doc 11 §8" nhưng doc 11 KHÔNG có Romano-Wolf — cần user đính chính.
- Nợ cũ: cập nhật `docs/05_build_order.md` + `docs/06` cho khớp v2.

## Dữ liệu đã có sẵn (trong `data/` khi user cung cấp)

- `data_gpr_daily_recent.xls`: GPRD/GPRD_ACT/GPRD_THREAT daily, 1985 → 2026-06-29. DÙNG ĐƯỢC NGAY.
- `data_gpr_export_202607.xls` (bản 44 nước, ĐÃ CÓ): 1518 dòng × 115 cột, monthly 1900 → 2026-06. Chứa 44 cột `GPRC_*` (recent 1985+) + 44 cột `GPRHC_*` (historical 1900+), gồm cả `GPRC_VNM` và `GPRHC_VNM`. Cột dictionary: `var_name`/`var_label`.

### Lưu ý phân phối GPRC_VNM (quan trọng cho econometrics)
- GPRC_VNM: mean ≈ 0.05, std ≈ 0.05, **lệch phải mạnh** (đa số tháng ~0, thỉnh thoảng spike). Đặc tính chung của country-GPR nước nhỏ.
- **BẮT BUỘC dùng log(1+GPR) hoặc chuẩn hóa** khi đưa vào hồi quy — không dùng giá trị thô, nếu không vài spike sẽ chi phối toàn bộ ước lượng.
- Narrative check đã pass: GPRHC_VNM đỉnh 1968-02 (Tết Mậu Thân), 1972-04/05 (Easter Offensive); GPRC_VNM giai đoạn 2018+ đỉnh rơi vào 2026-03/04/05 và 2025-04 (căng thẳng thuế quan Mỹ-Việt).

## Lệnh hay dùng

Môi trường: `.venv/` ở repo root (layout WSL/Linux — interpreter là **`.venv/bin/python`**, KHÔNG phải `python` trần của hệ thống; `python` trần thiếu matplotlib/statsmodels và sẽ crash). `gpr_engine` cài editable (import thẳng từ `src/`).

```bash
.venv/bin/python -m pytest                       # toàn bộ (~50 test, ~45s)
.venv/bin/python -m pytest tests/econ/test_shocks.py            # 1 file
.venv/bin/python -m pytest tests/econ/test_shocks.py::test_innovation_no_lookahead -x  # 1 test, dừng khi fail
.venv/bin/python -m ruff check .                 # lint (có ~7 lỗi E702/E401 sẵn trong notebook/script — không phải do bạn)
```

**Phase 1a — bảng γ tầng 2 track THÁNG (deliverable chính):**

```bash
.venv/bin/python scripts/run_t2_full.py                 # đầy đủ (~5.5 phút)
.venv/bin/python scripts/run_t2_full.py --no-quantile   # bỏ nhánh phân vị (~1 phút)
```

Trục SHOCK 3 mức × 3 kênh × 8 outcome × 2 bản battery. Spec KHÓA trong file (`INFERENCE`, `FOCAL_HORIZONS`, `TAUS`) — sửa là sửa quyết định đã ký, phải đồng bộ registry + test cùng commit.

**Research runner tầng 2 (G2a daily, offline — không cần PostgreSQL):**

```bash
python scripts/run_tier2.py                            # mặc định shock=innovation hợp lệ
python scripts/run_tier2.py --shock-method zscore      # LEVEL đối chứng -> report INELIGIBLE (#9)
python scripts/run_tier2.py --refresh --horizon 20     # --refresh = kéo lại FRED, bỏ cache
.venv/bin/python scripts/run_e1_diagnosis.py                     # E1: chẩn đoán spec shock quanh Hormuz 2026-02 (docs/11 §10)
```

Report versioned vào `docs/reports/` — **không bao giờ ghi đè** (`FileExistsError`). Tên mã hóa spec: innovation kèm order-tag (`..._ar5-5-2.md`). Đổi spec → xóa artifact cũ trước khi chạy lại.

**Guard số (P1, docs/11 §1 / docs/12 §5.4):** mọi số trong narrative report PHẢI tính từ dict `stats`, KHÔNG hard-code. Bug đã xảy ra thật (E1 ghi "1.8×" trong khi payload = 2.77×). Thêm số vào report thì thêm trường vào `stats` rồi tham chiếu, không gõ tay.

Đọc GPR từ `data/*.xls` + macro từ FRED, cache ở `data/cache/`. Xuất report versioned vào `docs/reports/` — **không bao giờ ghi đè**.

**Ingest vào PostgreSQL** (cần `--dsn`, đây là đường production):

```bash
psql "$DSN" -f sql/001_schema_core.sql
psql "$DSN" -f sql/002_schema_serving.sql   # statements/statement_scores/ladder_state/news_assessment
python -m gpr_engine.ingest.gpr_daily   --path data/data_gpr_daily_recent.xls --dsn "$DSN"
python -m gpr_engine.ingest.gpr_monthly --path data/data_gpr_export_202607.xls --dsn "$DSN"
python -m gpr_engine.ingest.market_data --dsn "$DSN" --source fred
```

**Chạy pipeline serving thật** (sau khi đã ingest ở trên — cần γ đã có ở `docs/reports/data/t2_full_holm_*.csv`, tức đã chạy `run_t2_full.py` ít nhất một lần):

```bash
export GPR_DB_DSN=... OPENAI_API_KEY=... GPR_TRAINING_CUTOFF=2026-01-01 GPR_KAFKA_BOOTSTRAP=host:9092
python scripts/run_news_service.py
```

`tests/test_config_locked.py` khóa `config/backtest.yaml` bằng máy: sửa mốc split mà không cập nhật `LOCKED_SPLIT` trong **cùng commit** → test đỏ. Đó là tính năng (nguyên tắc #3), không phải lỗi.

## Bản đồ code

**6 module còn là stub `raise NotImplementedError` ngay khi import** — chưa viết, không phải hỏng. Import chúng là crash. Còn stub: `econometrics/{surprise, tvp_var}`, `indices/{builder, divergence}`, `backtest/*` (2). Mọi thứ khác đã thực thi. (docs/11 §4 §7 có bảng module đầy đủ + việc cần làm cho từng cái, gồm cả module mới chưa tồn tại: `econometrics/analogue.py`, `scoring/{policy_scorer,track_record}.py`.)

Cascade 3 tầng (nguyên tắc #8) ánh xạ thẳng vào cây thư mục — đây là trục kiến trúc chính:

- `econometrics/shocks.py` — **G2.0, input của cascade**: LEVEL≠SHOCK. `innovation()` (AR(p), p từ `select_ar_order` BIC/trần-5), `jump()`, `gpa_surprise_v1()`. Mọi hồi quy shock LẤY TỪ ĐÂY, không đưa level vào (#9). Order pre-registered trong registry — đổi phải cập nhật `tests/test_registry_locked.py`.
- `econometrics/tier2_global_macro.py` — **tầng 1–2, ENGINE generic**: shock → Oil/DXY/VIX/US10Y. Ước lượng 1 lần, country-agnostic. Truyền thẳng `inference`/`lags`/`simultaneous`/`method`/`tau`/`seed` xuống LP (mặc định = bản cũ). ⚠️ `lag_augmented` **ép `macro_lags=0`** — giữ cả hai là lag trùng khít, X'X suy biến, SE vô nghĩa mà không có lỗi nào bắn ra.
- `econometrics/tier3_country.py` — **tầng 3, PARAMS từng nước**: tách BA hệ số `β` (global-direct) / `θ` (indirect, tính bằng **tích chập** qua horizon) / `λ` (domestic-direct, từ `GPR^{c,⊥}` đã orthogonalize). Hệ số đọc từ `config/params/<country>.yaml`, không điền tay. Đóng góp kênh dùng Shapley/LMG. `simultaneous=True` cho dải sup-t **theo từng hệ số**; cột lag augmentation gắn `role="lag_augmentation"` (nuisance, không đọc như β/θ/λ).
- `econometrics/local_projection.py` — LP dùng chung cho cả hai tầng. Hai chế độ suy diễn: `inference="hac"` (mặc định, bản cũ) và `inference="lag_augmented"` (MO-PM 2021 — **tự thêm lag của cả y lẫn shock**, HC1 thay HAC; thiếu lag của SHOCK là sụp cơ sở bỏ HAC, nên đừng tự ghép tay qua `controls`). `simultaneous=True` cho dải sup-t: đọc "IRF vượt 0 ở h=7" từ dải pointwise trên 25 horizon là đọc sai — ~2,5 điểm nằm ngoài ngay cả khi model đúng. **`simultaneous` CHỈ hợp lệ với `lag_augmented`** (Ω là EHW; ghép với SE HAC = hai bộ sai số chuẩn trong một dải) — raise. Với `return_all=True` trả `supt_c` **riêng cho từng hệ số**. `method="quantile"` cho τ; sup-t + quantile raise `NotImplementedError` (cần bootstrap).
- `econometrics/shock_axis.py` — **cổng máy của `DEC-2026-08-02-shock-axis`**: `gate_shock_eligibility(measure, inference)`. LEVEL/LEVEL+JUMP **chỉ eligible với `lag_augmented`** — đó là điều kiện làm quyết định A không phá #9. Nới cổng cho `hac` = rút lại chữ ký; `test_shock_axis_gate_matches_signed_decision` bắt. Còn chứa **cổng NHÃN** của spec kép (`check_component_labelling`): gọi `β_ANTICIPATED` là "cú sốc" → raise. Đó là Guard P1 cho **nhãn** thay vì cho **số** — spec kép không phá #9 nhờ cách gọi tên, không nhờ công thức.
- `econometrics/shocks.delta_decomposition` — **spec kép `docs/16` §2.2**: `Δ LEVEL = ANTICIPATED + SURPRISE`. **SURPRISE ≡ `innovation()`** (vì `Ê[Δlevel] = Ê[level] − level₋₁`) nên ANTICIPATED lấy bằng hiệu → hai thành phần cộng lại bằng *đúng* Δ LEVEL, không thể lệch do hai đường ước lượng. Phân rã trên **sai phân**, KHÔNG dùng `persistent_ar` (= Ê[LEVEL], gần nghiệm đơn vị → quay lại vấn đề #9). So hai hệ số **bắt buộc** qua `standardized_contribution` — `Var(ANT)/Var(SUR)≈0.1` nên hệ số thô không so được (E2: 48.9% ô đảo chiều).
- `econometrics/multiplicity.py` — **M10, bội giữa OUTCOME**: `holm()` + `holm_by_family()`. Chiều **horizon đã do sup-t xử lý** — phạt lại ở đây là mất hết power. Một hàng = một kiểm định = một (outcome, shock) trên CẢ đường IRF, **không phải** một (outcome, shock, horizon); truyền cả 25 horizon vào là phạt chiều horizon lần thứ hai. `family` bắt buộc khai báo (governance §6.6 chưa ký); họ phải phân hoạch + phủ hết, thiếu là raise.

Chân B (đường LLM, docs/15 tầng 2 — phân công: **LLM đo và diễn đạt, công thức truyền dẫn**):

- `scoring/statement_scorer.py` — **cửa duy nhất LLM chạm vào số liệu**: encoder lọc (callable tiêm vào, ngưỡng 0.6) → LLM chấm `{v ±1.0, commitment, specificity, channel, target}` JSON strict — sai key/miền là `ScoreParseError`, không sửa hộ. `training_cutoff` bắt buộc (contamination docs/14 §3.1). Client LLM tiêm vào (`LLMClient`), test dùng fake — **không viết test gọi API thật**.
- `indices/s_gpr.py` — công thức docs/00 §2.5 sau khi LLM đã chấm. S-GPR/S-CONC **giữ riêng, không net**. `w(role)` là INIT (#7) — role lạ raise. `expanding_percentile` **strict `<`**: chuỗi zero-inflated (JUMP) mà dùng `<=` thì ngày im ắng ra p~100, trigger nổ mỗi ngày.
- `econometrics/ladder.py` — máy trạng thái S0–S4, ngưỡng ở `config/ladder_v1.yaml` (đổi ngưỡng = file version mới, không sửa tại chỗ). Input là cột percentile do caller tính không-lookahead. NaN = không thỏa. S1/S3 chưa có ngưỡng (docs/00 §4.1 chưa cho) — thêm là phải hỏi user.
Tầng 4 (nhận định — ghép γ + tiền lệ + đo lường, gắn nhãn claim):

- `econometrics/analogue.py` — **M5, k-NN tiền lệ**. Bốn ràng buộc docs/11 §6 là **cơ chế**: `n<5` → raise (im lặng, cổng P3 — hạ ngưỡng để có số là biến "không biết" thành "biết mơ hồ") · IQR đổi dấu → "phân tán, không kết luận", KHÔNG đưa trung vị ra một mình · `episode_table()` luôn liệt kê được · `available_at ≤ t` **kể cả trong retrieval** (ứng viên phải nằm trước `as_of` VÀ đã diễn biến xong tới đó — lấy episode cách 3 ngày rồi đọc kết cục h=30 là look-ahead trá hình). Descriptor dùng **expanding**, không chuẩn hóa toàn mẫu. Claim ceiling `association`. ⚠️ Thiết kế này **không có tiền lệ trong literature GPR** (docs/11 §6 tự ghi) — độ chắc chắn thấp hơn §5.2/§5.3.
- `reporting/guard.py` — **Guard P1 dùng chung, chạy RUNTIME**. `NarrativeBuilder.render()` là **cửa duy nhất** lấy text ⇒ quên guard là không thể. Ba thứ nó KHÔNG làm (đọc trước khi tin): không kiểm số đúng/sai · không hiểu ngữ nghĩa ("tăng 5%" khi payload nói giảm vẫn lọt) · không bắt số bị bỏ sót. **Đừng đưa số vào văn xuôi tự do** — dùng trường số trong payload, guard sẽ chặn đúng cách làm sai này.
- `reporting/composer.py` — card + brief + **`compose_vn_note`** (mới 2026-08-04). `assert_claim_ceiling` chặn **từ ngữ** vượt trần tầng (docs/15 §4): card claim `measurement` nên "IP dự kiến giảm" bị chặn — không số nào sai, chỉ một động từ nhảy mức nhận dạng. `vn_note` dùng chung trần `association` với `analogue`.

Serving — "1 tin vào → 1 kết quả ra" (mới 2026-08-04, xem mục Trạng thái hiện tại):

- `pipeline/news_pipeline.py` — orchestrator. `process_news_item` THUẦN (mọi I/O tiêm callable — `history_provider`/`jump_series_provider`/`gamma_loader`, test bằng fake, không Postgres/Kafka thật). `process_news_item_live` nối callable thật vào `service/store.py` + file γ mới nhất. Guard P1/trần claim có thể chặn `measurement_card` (ví dụ `rationale` LLM chứa số lạ) — bắt bằng try/except, suy giảm có kiểm soát (`measurement_card=None` + `measurement_card_error`), KHÔNG làm sập cả pipeline vì một dòng văn bản.
- `pipeline/gamma_lookup.py` — đọc bảng γ đã công bố lọc theo `channel` (`pooled`/`act`/`threat` — ⚠️ đây LÀ biến thể GPRD dùng làm shock, KHÔNG PHẢI kênh truyền dẫn energy/trade/financial/military). `commitment_to_gamma_channel` là proxy tường minh, không phải cùng trục dữ liệu.
- `pipeline/vn_exposure.py` — tra bảng thuần (từ `vietnam-params.md`), KHÔNG LLM, KHÔNG hồi quy. `has_quant_params` luôn `False` cho tới khi `config/params/vn.yaml` có mục `fitted:`.
- `service/store.py` — I/O Postgres (schema `sql/002_schema_serving.sql`), cùng pattern `create_engine`+`text()` UPSERT của `ingest/gpr_daily.py`. Không có test DB thật (giống toàn bộ `ingest/*.py`).
- `service/kafka_io.py` — `KafkaResultPublisher` (publish_fn tiêm vào) + `run_consumer_loop` (`confluent-kafka`). Chỉ dùng `bootstrap.servers` — hoạt động như nhau dù broker KRaft hay ZooKeeper.
- `scripts/run_news_service.py` — entrypoint sống, cấu hình 100% qua biến môi trường (`GPR_DB_DSN`, `GPR_KAFKA_BOOTSTRAP`, `GPR_LLM_MODEL`...), xem docstring đầu file cho danh sách đầy đủ.

- `econometrics/panel_var.py` — **block-exogenous VAR + Granger test khối** (docs/11 §5.5): nền hình thức cho #8. `granger_block_test(H0: Z↛X)` — không bác bỏ → kiến trúc engine+params hợp lệ cho nước c. Kiểm định GIẢ ĐỊNH, không phải IRF. VN thật cần r^c (VN-Index) + p (chính sách) chờ đường nối BeaverX.

**Outcome vĩ mô thực (docs/14 M0):** `data_files.load_real_macro_monthly` + `transform_real_macro` → `ip`/`cpi`/`infl_exp`. Vào track THÁNG qua `build_monthly_panel(real_macro=True)`. `ip = 100·Δln(INDPRO)` khớp E0; `infl_exp` đi **sai phân** (mức khảo sát dai dẳng, #9). INDPRO/CPI **revise hồi tố** → ghi `real_macro_vintage()` vào metadata report; backtest point-in-time phải qua ALFRED vintage, bản FRED là vintage mới nhất.

**Benchmark battery (docs/14 §2 1a-b):** `load_benchmark_monthly` + `transform_benchmark` → `epu_us`/`epu_global`, log1p cùng quy ước GPR. `build_monthly_panel(battery=True)`. Ba cái bẫy đã ghi trong docstring, đọc trước khi dùng: (1) control phải **đồng thước đo** với shock; (2) `epu_global` 1997+ → bản a/b phải **cùng mẫu**; (3) WUI theo **quý**, cố ý không vào panel — join vào grid tháng sẽ xóa 2/3 panel trong im lặng, ffill thì vi phạm #10. WUI tải tay về `data/wui_global.csv`.

Cước vận tải biển (docs/11 §5.3): `data_files.load_freight_monthly` (FRED PPI deep sea freight `PCU483111483111`, 1990+ monthly) + `transform_freight` (Δln). Vào track THÁNG qua `build_monthly_panel(freight=True)` (mặc định False) — nguồn monthly nên KHÔNG vào daily (#10). ⚠️ PPI khảo sát DÍNH → đo truyền dẫn chi phí, KHÔNG đo tắc nghẽn Hormuz/Malacca (xem cảnh báo trong docstring). `freight_vintage()` cho metadata vì PPI có hiệu chỉnh hồi tố.

- `econometrics/sca_engine.py` — **động cơ Specification Curve (docs/12 §3)**: `run_sca` (moving-block bootstrap dưới null + T1/T2/T3), agnostic với spec (nhận callable). **Null ĐÚNG SSN2020 bước 2**: moving-block CHỈ trên outcome_col (phá liên kết, giữ autocorr) — resample cả hàng cùng nhau là SAI (mất power). ℓ hiệu chỉnh trên mô phỏng: **tháng=18, ngày=40** (không phải 12/60 — `run_sca_calibration.py` thấy size phình/mất power). size+power verified trên mô phỏng trước khi tin dữ liệu thật.

**Governance (khóa máy):** `config/hypothesis_registry.yaml` pre-register giả thuyết + AR order + trial log; `config/backtest.yaml` khóa split. Cả hai có test khóa (`tests/test_registry_locked.py`, `tests/test_config_locked.py`): sửa giá trị đã khóa mà không cập nhật hằng số `LOCKED_*` trong cùng commit → test đỏ. Policy văn bản ở `docs/g0_governance.md`.

**Hai đường nạp dữ liệu song song, cố ý:**

- `dataset.py` — đường **production**, đọc `ext_series` từ PostgreSQL, point-in-time qua `load_series(..., as_of=...)`.
- `data_files.py` — đường **research offline**, đọc file + FRED. Dùng lại đúng transform của `dataset.py` (`log1p_gpr`, `transform_global_macro`) — khác I/O, **không lặp lại quy ước biến đổi**. Thêm transform mới thì sửa ở `dataset.py`, không fork sang đây.

Quy ước transform (docs/07 §0), sai là hỏng ước lượng: `LEVEL = log1p(GPR)` cho cả daily/monthly; shock chính là **INNOVATION = LEVEL − E[LEVEL|quá khứ]** (`shocks.innovation`, #9). `JUMP` tính trên chuỗi raw rolling để giữ thông tin đuôi; `LEVEL+JUMP := LEVEL + JUMP`, tuyệt đối không dùng `INNOVATION + JUMP`. Sau D+1, cuối tuần dùng mean cho LEVEL/INNOVATION, max cho JUMP; composite = mean(LEVEL)+max(JUMP). Chế độ `--shock-method zscore|log1p` của `run_tier2` chỉ là LEVEL đối chứng và bị gắn INELIGIBLE. Oil/DXY → `Δln`; VIX → giữ level; US10Y → sai phân.

Gate là **người quyết, không phải máy**: `run_tier2.gate_checklist` xuất verdict + mục Human review; run trên level tự gắn `INELIGIBLE` theo nguyên tắc #9.

## Cách làm việc trong repo này

- Đọc `docs/` theo thứ tự số trước khi code module tương ứng.
- Mỗi module có test đi kèm trong `tests/`. Viết test trước cho phần công thức (econometrics, indices).
- Notebook khám phá đặt trong `notebooks/`, không import ngược vào production code.
- Commit nhỏ, message rõ. Không refactor lan man ngoài scope task đang làm.
- Khi bí về thiết kế: hỏi lại, đừng tự quyết định kiến trúc lớn.
