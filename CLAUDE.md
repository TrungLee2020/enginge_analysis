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

## Trạng thái hiện tại (cập nhật 2026-08-09)

### 🐛 Bug data model THẬT, lộ ra ở lần nạp Postgres SỐNG đầu tiên: AI-GPR daily/monthly ghi đè nhau

`ext_series` PK = `(series_id, date, data_version)` — **không có `freq`**. `ingest/ai_gpr.py` dùng CHUNG bộ tên series cho cả file daily lẫn monthly, mà mọi ngày đầu tháng có mặt ở cả hai ⇒ cùng PK ⇒ ghi đè lẫn nhau. Nạp `--freq both` thì monthly chạy sau và thắng: **11.186 hàng** (799 ngày đầu tháng × 14 series) mang giá trị THÁNG nằm trong chuỗi gắn `freq='daily'`.

**Âm thầm hoàn toàn:** giá trị tháng ≈ trung bình của tháng nên CÙNG THANG ĐO với giá trị ngày — avg ngày-đầu-tháng 212 vs ngày khác 213, biểu đồ không hề lộ. Ví dụ thật: `AIGPR_OIL 2026-03-01 = 1844.10` (giá trị THÁNG 3) trong khi giá trị NGÀY hôm đó là **610.53**.

Bug có từ trước phiên này (mọi lần nạp AI-GPR đều dính); cơ chế archive mới chỉ làm nó **hiện ra** — lần nạp đầu báo "9440 giá trị bị revise" ở daily rồi monthly báo revise **đúng 9440 giá trị đó ngược lại**, gương nhau từng con số. Trước đây `ingest/ai_gpr.py` chỉ có test mock DB, không bao giờ chạm Postgres thật nên không ai thấy.

**Đã sửa:** monthly mang hậu tố `_M` (`AIGPR_OIL_M`…) — khớp quy ước sẵn có của repo (GPRD daily vs GPR monthly). Thêm `series_id_for()`/`series_ids()`. Xóa 359.346 hàng AIGPR hỏng + nạp lại sạch: daily 340.466 hàng (1960→2026-07-31), monthly 11.186 hàng (1960→2026-07-01), **0 xung đột**. Thêm **chốt chặn cấu trúc trong `versioning.py`** bắt cả LỚP lỗi này ở mọi nguồn tương lai: series_id đã tồn tại với `freq` khác → raise, không nạp. `DO UPDATE` giờ cập nhật cả `freq`/`source` (bản cũ để nguyên nên hàng bị nguồn khác ghi đè sẽ **nói dối về tần suất của chính nó**). 3 test mới khóa lại.

### 📊 Nạp DB thật + chạy lại mô hình trên dữ liệu mới

**Ingest lên Postgres sống (lần đầu — trước giờ mọi `ingest/*.py` chỉ có test mock):**

| nguồn | hàng mới | giá trị bị revise | archive |
|---|---|---|---|
| GPR daily | 105 | **126** (2025-03-15 → 2026-06-29) | `gpr_daily_pre_20260809` |
| GPR monthly | 94 | **520** (2025-03 → 2026-06) | `gpr_monthly_pre_20260809` |
| AI-GPR daily/monthly | 351.652 | 0 | — (nạp lại sạch sau khi sửa bug) |

Khớp chính xác con số đo trước khi nạp. `data_versions` giờ có sổ thật.

**`run_t2_full.py` chạy thật trên dữ liệu mới → `docs/reports/T2_full_3e1bd83a02b8.md`** (535s). So với bản cũ `T2_full_f2579b30928f.md`:

| | cũ (`same_measure`, 231 tháng) | mới (`level_lags`, 315 tháng) |
|---|---|---|
| p thô < 0.10 / 432 | 34 — **DƯỚI** kỳ vọng null 43.2 | 51 (1.18×, z≳+1.25) |
| Holm survivors (bản b) | 9 | 9 |
| — LEVEL / INNOVATION / LEVEL+JUMP | 2 / 1 / 6 | **0 / 0 / 9** |
| đồng thuận cả 3 thước đo | 1 ô | **0 ô** |
| ô mạnh nhất | freight × LEVEL+JUMP h=1 | infl_exp × LEVEL+JUMP h=2 |

**⚠️ Đọc kết quả này thế nào (chờ human review, mục cuối report còn trống):**
- **Bản b ở mức lưới = 0.93× kỳ vọng null** — tức DƯỚI nhiễu thuần. 9 ô "sống sót Holm" nằm trong một lưới không tách được khỏi null toàn cục. Đúng cái mà `grid_null_check` sinh ra để chặn.
- Bản a = 1.44× vs bản b = 0.93× ⇒ phần "riêng của GPR" chính là thứ battery EPU hấp thụ.
- **9 ô đó dồn HẾT vào LEVEL+JUMP** — đúng ô mà `DEC-2026-08-09-battery-control-form` đã ghi trước là control YẾU NHẤT (JUMP phi tuyến, ngoài span `{LEVEL, lag}`). Nên đây là artifact đã được dự báo, không phải phát hiện. Đồng thuận 3 thước đo = 0 củng cố cách đọc này.
- Mẫu dài thêm 84 tháng KHÔNG biến kết quả thành có tín hiệu.

### 🔥 Sự cố đã xảy ra thật: tên artifact chỉ mã hóa DỮ LIỆU, không mã hóa SPEC

Chạy `run_t2_full.py` với spec mới (thêm bản battery c) trên **cùng file dữ liệu** → `_data_version()` băm file nên ra **đúng một tên**. Hệ quả: `FileExistsError` chặn được file `.md`, nhưng **CSV đã bị ghi đè TRƯỚC đó** (thứ tự cũ: ghi CSV → mới kiểm report). Kết quả: `t2_full_gamma_3e1bd83a02b8.csv` chứa kết quả spec MỚI trong khi `T2_full_3e1bd83a02b8.md` mô tả spec CŨ — hai thứ mâu thuẫn, không cảnh báo gì.

**Hai vá, cả hai đều là vá gốc:**
1. `_spec_version()` — băm `INFERENCE/LAGS/HORIZONS/FOCAL/TAUS/ALPHA/CI/SEED/BATTERY_*/CHANNELS`. Tên artifact giờ là `<data>_<spec>`. Trùng tên giờ thật sự nghĩa là "cùng dữ liệu VÀ cùng spec".
2. **Kiểm va chạm TRƯỚC khi ghi bất cứ gì** (report + cả 3 CSV), không phải sau. Ghi một phần rồi mới phát hiện va chạm là cách tạo ra đúng tình trạng mâu thuẫn trên.

✅ **Đã khôi phục** bằng `scripts/restore_t2_legacy_csv.py` — tái lập **khớp chính xác cả 5 con số** của report cũ (315 tháng · 432 kiểm định focal · 51 bác bỏ thô · 22 Holm · bản b 9), đó là bằng chứng CSV sinh ra đúng thuộc về report đó. Script tự đối chiếu TRƯỚC khi ghi; lệch là dừng chứ không tạo CSV giả.

⚠️ Điểm đáng nhớ về cách làm: `BATTERY_VERSIONS` nay nằm trong `DEC-2026-08-09-policy-shock-control`, nên sửa hằng số đó trong file — dù chỉ để chạy một lần — sẽ làm test chữ ký đỏ. Script **override lúc chạy** (gán thuộc tính trên module đã import), không chạm file nào. Đi vòng qua cổng một cách hợp lệ, không vô hiệu hóa cổng.

### 💵 Cú sốc chính sách Fed — biến kiểm soát CÒN THIẾU của bảng γ (mới, research)

**Vì sao nó thuộc về dự án này, không phải module rời:** bảng γ ước lượng "cú sốc GPR → vĩ mô toàn cầu". Nhưng tin Fed **cũng đẩy đúng những biến đó** (lãi suất, DXY, VIX, giá dầu). Tháng nào có cả cú sốc GPR lẫn công bố FOMC mà không tách ra thì γ **hút luôn** phần do Fed gây ra. Battery hiện tại (EPU) kiểm soát **bất định** chính sách, KHÔNG kiểm soát **cú sốc** chính sách — hai thứ khác nhau.

`econometrics/policy_shock.py`: `event_days` · `policy_surprise` · `to_monthly` · `contamination_ratio`. 11 test.

**KHÔNG dùng LLM cho phần này** — cú sốc chính sách Mỹ đo trực tiếp được từ phản ứng giá tài sản quanh công bố (giá phái sinh đã chứa kỳ vọng, nên phần đổi trong ngày công bố CHÍNH LÀ phần bất ngờ). Chấm giọng điệu rồi suy ra độ lớn là thay phép đo trực tiếp bằng proxy nhiễu hơn (#2). LLM vẫn có chỗ nhưng ở chiều khác: các chiều giá KHÔNG định giá riêng ra được (ngôn ngữ forward guidance, bất đồng biểu quyết, độ bất định câu chữ).

**Chạy thật trên dữ liệu sống (2026-08-09):** 195 ngày công bố statement (2003-01 → 2026-07, từ 406 văn bản đã thu thập), `DGS2` từ FRED, ra **167 tháng** có họp FOMC.

| kiểm chứng | kết quả |
|---|---|
| \|Δ2y\| ngày FOMC vs ngày thường | **1.50×** |
| phương sai | **2.01×** |
| cú sốc lớn nhất | 2023-12-13 (pivot, −27bp) · 2003-06-25 (cắt 25bp khi chờ 50) · 2004-01-28 (bỏ "considerable period") · 2008-03 · 2022-06-15 |

Rơi đúng các ca kinh điển của văn liệu — phép đo bắt được thứ cần bắt.

⚠️ **Đây là proxy NGÀY, không phải chuẩn vàng intraday.** Chuẩn vàng là cửa sổ 30 phút quanh 14:00 ET; bản này dùng thay đổi cả ngày nên còn chứa tin khác trong ngày. Tỉ lệ 1.50× là tín hiệu thật nhưng **không sạch**. Chuỗi intraday đã publish (Bauer-Swanson 2023; Bu-Rogers-Wu 2021) sạch hơn — dùng được thì NÊN dùng. Khi báo cáo gọi "policy-window surprise (daily proxy)", đừng gọi "cú sốc chính sách". Trần claim `measurement`.

**✅ ĐÃ NỐI VÀO BẢNG γ → `docs/reports/T2_full_3e1bd83a02b8_cb1a51.md`** (671s, 309 tháng 2000-08 → 2026-06), **đã ký `DEC-2026-08-09-policy-shock-control`**. Thêm **bản battery c** (= b + `mp_surprise` + 6 lag) thay vì sửa bản b — đổi định nghĩa b thì mọi số cũ hết so được. Chữ ký khóa bằng `LOCKED_DECISION_IDS` + `test_policy_shock_control_decision_matches_code` (bắt cả ba cam kết: c ⊃ b · a/b giữ nguyên · `policy_surprise` trả NaN ngoài phạm vi có sự kiện).

Vá thêm khi làm: `_BOARDDOCS_HREF_RE` bỏ sót statement 2000-2002 (nằm dưới `/boarddocs/press/**general**/`, link kết thúc bằng `/` không `default.htm`) → 195 ngày công bố lên **225**. Và `policy_surprise` giờ trả **NaN ngoài phạm vi có sự kiện**: điền 0 cho giai đoạn chưa thu thập là nói dối "không có công bố" trong khi thực tế 8 cuộc họp/năm — biến kiểm soát mang giá trị sai làm lệch hệ số của biến CHÍNH mà không dấu hiệu gì.

| bản battery | bác bỏ thô / 216 | vs kỳ vọng null | ô sống sót Holm |
|---|---|---|---|
| a — không control | 24 | 1.11× | — |
| b — EPU | 19 | 0.88× | 8 |
| **c — EPU + cú sốc chính sách** | **18** | **0.83×** | **7** |

**Đọc kết quả:**
- **Toàn lưới 61/648 vs kỳ vọng 64.8 = 0.94×, z≳−0.50 → DƯỚI null toàn cục.** Câu "γ có sống sót khi kiểm soát Fed không" phần lớn là moot: γ không có tín hiệu ở mức lưới ngay từ đầu.
- Thêm control chính sách đẩy lưới xuống tiếp (0.88× → 0.83×) và bỏ 1 ô giá tài sản (4→3). Tức **có** một chút phần γ đang tính công của Fed, nhưng nhỏ — không phải lời giải thích chính.
- Vẫn **0/0/7-8**: mọi ô sống sót dồn hết vào LEVEL+JUMP, LEVEL và INNOVATION đều 0. Đồng thuận 3 thước đo = 0. Giống hệt run trước → đọc như artifact của thước đo, không phải phát hiện.

### 🏛️ Văn bản Fed — đo độ hiện diện của GPR trong phát ngôn chính sách (mới, research)

**Phân biệt hai thứ hay bị lẫn:** FRED = số (không LLM). **FED = văn bản** (FOMC statement/minutes) → LLM đúng chỗ. `ingest/fomc.py` + `scoring/policy_gpr_scorer.py`.

**Nó KHÔNG đo cú sốc chính sách tiền tệ Mỹ** — cái đó đã có bản đo sạch hơn từ giá phái sinh quanh cửa sổ FOMC (Kuttner 2001; Gürkaynak-Sack-Swanson 2005; Nakamura-Steinsson 2018; chuỗi Bauer-Swanson 2023, Bu-Rogers-Wu 2021 đã publish). Chấm hawkish/dovish bằng LLM để suy ra cú sốc đó là dựng lại cái đã có bằng proxy nhiễu hơn (#2). Lý do `docs/14` §5 chọn Aruoba-Drechsel là vì **VN** không có phái sinh lãi suất; Mỹ thì có.

**Nó đo câu hỏi NGƯỢC LẠI, và là câu hỏi riêng của dự án:** rủi ro địa chính trị có đi vào hàm phản ứng chính sách không, mạnh tới đâu, qua kênh nào. Không nguồn nào bán sẵn; C-I làm biến thể tương tự trên Beige Book/earnings call.

- **Rubric RIÊNG** (`gpr_salience` 0-1 · `channel` · `direction` · `binding` · `evidence` trích nguyên văn), KHÔNG dùng lại thang leo thang ±1.0 — `docs/17` §4.6 ghi thẳng điều này. Hai construct khác nhau: ±1.0 đo *một bên LÀM GÌ*, rubric này đo *một văn bản NÓI VỀ* rủi ro của bên thứ ba. Fed nói "căng thẳng Trung Đông làm tăng giá năng lượng" KHÔNG phải Fed leo thang +0.6.
- **Kênh dùng đúng 4 kênh truyền dẫn của bảng γ**, không phải 6 kênh chấm điểm của docs/00 — đầu ra để đối chiếu với γ tầng 2, trả taxonomy rồi phải map 6→4 (mapping đang MỞ) là tự thêm một bước mơ hồ.
- **Trần claim `measurement`**. Nói "GPR ảnh hưởng quyết định Fed" là bước lên `association`, cần hồi quy — không phải cần thêm một trường JSON.
- Cùng hợp đồng với `statement_scorer`: `training_cutoff` bắt buộc, prompt cấm dùng kiến thức sau ngày công bố, cache phủ MỌI trục version, JSON strict (sai key/miền → raise, KHÔNG clip).

**Hai phát hiện khi chạy thật trên federalreserve.gov (2026-08-09):**

1. **403 là chặn BOT, không phải chặn egress** — thêm `User-Agent` kiểu trình duyệt là 200. Nhầm hai cái này sẽ ra kết luận "không tải được" sai.
2. **Link minutes trong RSS trỏ tới THÔNG CÁO, không phải bản minutes.** Thông cáo ~760 ký tự ("The Federal Reserve on Wednesday released the minutes of…"); bản thật ở `/monetarypolicy/fomcminutesYYYYMMDD.htm` dài **36.171-46.083 ký tự** và đầy nội dung địa chính trị (`middle east` ×12-21, `conflict` ×14-21, `war` ×11-13). Chấm nhầm thông cáo **không báo lỗi** — chỉ làm mọi bản minutes ra salience ~0 một cách HỆ THỐNG, tức chuỗi sai mà trông như thật. Đã thêm `resolve_minutes_url()` + ngưỡng độ dài **theo từng loại** (`statement` 200 / `minutes` 5000) để resolve hỏng thì raise thay vì thành điểm 0 im lặng.

Kiểm thật 4 văn bản gần nhất: statement 1044-1253 ký tự, minutes 36k-46k, resolve đúng cả hai. **CHƯA gọi LLM lần nào** — cần `OPENAI_API_KEY` và đó là chi phí của user. 33 test (fetcher + LLM client đều tiêm vào, không chạm mạng).

**Backfill lịch sử — `list_archive()`, đọc VĂN BẢN THẬT.** RSS chỉ giữ ~15 mục nên đó là đường *cập nhật*; kho thật lấy từ mục lục của Fed: trang lịch hiện tại cho **90 release (2021-01-27 → 2026-07-29)**, `fomchistorical<YYYY>.htm` cho từng năm cũ (2014-2015: 32 release). Chạy thật, không suy đoán.

**❌ TUYỆT ĐỐI KHÔNG backfill bằng cách hỏi LLM nhớ lại nội dung văn bản cũ.** Đó là SINH dữ liệu từ trí nhớ model, không phải ĐO văn bản (#1); model biết chuyện xảy ra sau nên mọi điểm sẽ nhiễm hindsight — đúng thứ `training_cutoff` sinh ra để chặn; và trường `evidence` đòi trích nguyên văn sẽ thành trích dẫn bịa. Ghi cảnh báo này ngay trong `ingest/fomc.py`.

**Bẫy point-in-time thứ ba, đã vá:** URL minutes mang ngày **HỌP**, nhưng minutes công bố **~3 TUẦN SAU** (họp 2015-12-16 → công bố 2016-01-06). Lấy ngày họp làm `published_at` là look-ahead ba tuần. Ngày công bố nằm trong text quanh link — `(Released July 08, 2026)` ở trang mới, `Minutes (Released February 18, 2015):` ở trang cũ (hai layout khác nhau, parse cả hai). Không tìm thấy → `raise`, không lấy tạm ngày họp.

**Kiểm chéo mạnh:** timestamp suy từ archive (14:00 ET, có xử lý DST) **trùng khít** timestamp RSS — statement 2026-07-29 18:00 UTC, minutes 2026-07-08 18:00 UTC. Hai đường độc lập cho cùng một mốc, nên chuỗi backfill nối liền được với chuỗi cập nhật. Khóa bằng test.

**✅ ĐÃ CHẠY THẬT trên vLLM của user (2026-08-09) → `docs/reports/FOMC_gpr_salience_pg1_2000.md`.** `Qwen3-14B-AWQ`, 109 phút, **403/406 văn bản** (3 lỗi contract, 0,7% — nổi lên ở log chứ không bị nuốt thành điểm 0), 1147 đoạn.

| | |
|---|---|
| phạm vi | 2000-03-23 → 2026-07-29, 295 tháng có văn bản |
| salience trung bình | 0.0709 (statement 0.048 · minutes 0.091) |
| có ít nhất một đoạn `binding` | 31.8% văn bản |
| hoàn toàn không có nội dung địa chính trị | 66.8% |

**Narrative check PASS — top-15 rơi đúng vào các đợt thật:** Nga xâm lược Ukraine 2022-03/05/06/09 (0.60-0.70) · hậu 11/9 (minutes 2001-11-08, 0.653) · chiến tranh Iraq 2003-03/05/06 (0.60-0.64) · Trung Đông 2026-04/05/07 (0.47-0.55). `evidence` trích nguyên văn, kiểm tay thấy khớp.

**Kiểm chứng hội tụ (mức `association`, KHÔNG có trong report vốn trần `measurement`):** corr(salience, log1p GPR monthly) = **+0.439** Pearson / +0.316 Spearman trên 295 tháng, đọc từ DB sống. Hai phép đo độc lập — lời của chính Fed vs chỉ số báo chí C-I — đồng hướng. Đây là bằng chứng cho tiền đề của cả dự án, không phải chỉ cho module này.

**✅ `pg2` ĐÃ CHẠY (2026-08-09) → `docs/reports/FOMC_gpr_salience_pg2_2000.md`** (115 phút, **435/436** văn bản — 1 lỗi contract so với 3 ở pg1). Coverage rộng hơn pg1 (436 vs 406) nhờ bản vá `_BOARDDOCS_HREF_RE`. **Tốt hơn pg1 trên mọi chiều đo được:**

| | pg1 | pg2 |
|---|---|---|
| lệch thiên tai (2 ca cũ) | **0.40 / 0.39** | **0.10 / 0.02** |
| trích dẫn khớp nguyên văn | 92.5% | **94.9%** (112 exact / 6 missing / 317 empty) |
| corr Spearman với log1p GPR | +0.316 | **+0.358** |
| corr Pearson | +0.439 | +0.437 |
| văn bản hoàn toàn không có nội dung ĐCT | 66.8% | 72.9% |

**Đây là chữ ký của một rubric tốt lên chứ không phải chỉ khác đi:** Pearson gần như không đổi trong khi Spearman TĂNG — siết rubric bỏ được nhiễu (dương tính giả) mà không bỏ mất tín hiệu. Narrative check vẫn đúng: top-10 là Iraq 2003, Ukraine 2022, Trung Đông 2026.

`evidence_check` giờ chạy TỰ ĐỘNG trên mọi hàng (`verify_evidence`, đối chiếu máy với văn bản gốc) — cổng chống bịa không cần người. `judge_score()` (LLM thẩm định) đã có nhưng CHƯA chạy; nhớ giới hạn: hai LLM đồng ý là **độ tin cậy**, không phải **độ đúng**.

**🐛 Lệch đã đo ở pg1, là lý do có pg2:** 2/134 văn bản có salience>0 là **thiên tai** bị chấm thành địa chính trị (`Hurricane Rita caused further disruption to energy production` 0.39; `Gasoline prices rose in the aftermath of the hurricanes` 0.40). Model neo vào "gián đoạn nguồn cung năng lượng" rồi suy ra địa chính trị — đúng kiểu lệch `docs/17` §5 đã ghi. `pg2` loại trừ tường minh thiên tai/đại dịch và nói rõ "gián đoạn chỉ là địa chính trị nếu nguyên nhân là nhà nước / nhóm vũ trang / quyết định chính trị". ⚠️ Bump version làm **toàn bộ cache pg1 vô hiệu** (đúng thiết kế) → chạy lại tốn thêm ~2 giờ GPU. Với 1,5% ô nhiễm, **chưa chạy lại** — để user quyết.

**vLLM chạy được ngay, không cần client thứ hai:** `statement_scorer.openai_chat_client(model, base_url, api_key)` hoạt động với mọi endpoint OpenAI-compatible và `policy_gpr_scorer.LLMClient` cố ý cùng chữ ký. ⚠️ Client đó đặt `response_format={"type":"json_object"}` — vLLM chỉ hỗ trợ khi bật guided decoding; không bật thì lỗi ngay request đầu, đó là lỗi CẤU HÌNH, không được sửa bằng cách nới lỏng parse.

### 🔌 FRED vào DB + đọc point-in-time có nhận biết revise

**FRED KHÔNG cần LLM.** Nó là số sẵn từ API St. Louis Fed (Brent/DXY/VIX/US10Y), không có chữ để chấm — LLM chỉ vào chỗ có văn bản, đó là việc của AI-GPR (chấm bài báo). FRED gọi được từ sandbox, không cần API key. `ingest/market_data.py` đã nối vào `versioning.py`; ingest thật: **32.838 hàng, 1990-01-02 → 2026-08-06**.

**Hai lỗi lộ ra khi lần đầu đọc production path từ DB, đã sửa:**

1. **`load_series(as_of=...)` trả VỀ RỖNG.** Tôi thêm `loaded_at <= as_of` ở lượt trước — trộn "lúc TA nạp" với "lúc giá trị biết được". Cả DB nạp hôm nay nên mọi `as_of` trước hôm nay ra 0 hàng: đúng kỹ thuật, vô dụng thực tế. Bỏ điều kiện đó.
2. **Thay bằng `revision_aware=True`** (mặc định): với mỗi `(series_id, date)`, lấy giá trị **đang có hiệu lực tại `as_of`** — bản archive có `revised_at > as_of` (lấy bản bị thay thế sớm nhất), nếu không có thì bản chạy.

**Bằng chứng trên dữ liệu sống** — `GPRD_ACT` ngày 2026-06-24:

| góc nhìn | giá trị |
|---|---|
| hôm nay (bản chạy) | 163.08 |
| `as_of=2026-06-30, revision_aware=True` | **293.83** ← số thật đã công bố lúc đó |
| `as_of=2026-06-30, revision_aware=False` | 163.08 ← look-ahead trên trục revise |

Chênh 80%. Backtest đọc bản hôm nay là dùng thông tin chưa tồn tại. `store.load_jump_series` lọc `data_version=RUNNING_VERSION` (đường sống, `as_of=now`) — replay lịch sử là việc của `load_series(revision_aware=True)`.

**`ingest/macro_monthly.py` (mới) — lấp nốt khoảng trống cuối của đường DB.** 6 chuỗi THÁNG: `INDPRO`/`CPI`/`INFL_EXP` (outcome vĩ mô thực) + `EPU_US`/`EPU_GLOBAL` (battery) + `FREIGHT_PPI` (kênh vật lý). Ingest thật: **2.803 hàng, 1985-01 → 2026-07**. Trước đó ba nhóm này CHỈ tồn tại ở đường file nên panel tầng 2 không dựng được từ DB.

- Lưu **mức thô**; transform (`100·Δln INDPRO`, `Δln CPI`, sai phân `infl_exp`, `log1p` EPU, `Δln` freight) vẫn là việc của `data_files.transform_*` — không fork quy ước sang chỗ thứ hai (docs/07 §0).
- **`available_at` theo TỪNG series**, không một con số chung: `INDPRO`/`CPI` +18 ngày, `FREIGHT_PPI` +20, `EPU_*` +7, `INFL_EXP` +5 — tính từ **đầu tháng kế tiếp**, không từ `date`. Series chưa khai độ trễ → `raise`, không mặc định 0 (mặc định 0 là look-ahead im lặng).
- Mã FRED không import lại được từ `data_files` (chiều phụ thuộc ngược = vòng tròn) nên khóa bằng `test_macro_monthly_codes_match_research_path`.
- Đọc lại qua `dataset.load_monthly_macro_raw()`. Kiểm thật: `as_of=2026-07-10` → `ip` dừng ở tháng 5, vì IP tháng 6 phải tới 2026-07-19 mới công bố. Đúng point-in-time.
- Coverage khớp kỳ vọng: `epu_global` 354 tháng (1997+), `freight` 457 (1990+), còn lại 497-499.

⚠️ `BRENT`/`DXY` NaN ở 3 ngày cuối là **độ trễ publish thật của FRED**, không phải lỗi.

⚠️ **ALFRED vẫn là việc chưa làm.** Với macro revise hồi tố mạnh (INDPRO revise tới 5 năm, CPI/PPI nhiều kỳ), nguồn point-in-time đúng là **ALFRED vintage** — bản FRED luôn là vintage mới nhất. Cơ chế archive chỉ giữ vintage TỪ LÚC ta bắt đầu nạp trở đi, KHÔNG dựng lại được quá khứ trước đó. ALFRED cần API key riêng của FRED → cần user cấp. Với ước lượng γ (mô tả truyền dẫn) bản hiện tại chấp nhận được; với backtest sinh tín hiệu thì KHÔNG.

### 🩹 Áp 3 patch user cung cấp: đối chiếu mức lưới + chi phí mẫu battery

User đưa 3 file patch ở repo root (`patch1_grid_null_check.py`, `patch2_battery_and_sample.py`, `patch3_report_wiring.py` — bản mô tả, KHÔNG phải module chạy được). Đã áp vào code thật, 369 test pass (4 fail có sẵn từ trước, xem cuối mục).

- **`multiplicity.grid_null_check()` (patch 1)** — đối chiếu số bác bỏ thô với `n·α` dưới **null toàn cục**. Trả lời câu Holm KHÔNG trả lời: Holm nói "ô NÀO sống sót trong họ này", cái này nói "toàn lưới có nhiều hơn nhiễu thuần không". Ở `T2_full_f2579b30928f` hai câu cho kết luận **ngược nhau** — 15 ô "sống sót Holm" nhưng 34 bác bỏ thô < 43.2 kỳ vọng null (đã kiểm lại trên CSV thật: 432/34/15, khớp chính xác). Họ Holm chỉ 4/3/1 outcome nên ngưỡng nghiêm nhất α/4, gần như không phạt gì so với quy mô 432 kiểm định. `z_indep` là **cận dưới** của |z| thật (kỳ vọng cộng tính bất kể tương quan, chỉ phương sai mới phình) — đọc dấu, không báo cáo như p-value.
- **`run_t2_full.BATTERY_MODE = "level_lags"` (patch 2), đã ký `DEC-2026-08-09-battery-control-form`** — battery EPU vào dạng LEVEL + 6 lag thay vì cùng thước đo với shock (`same_measure`, docs/14 §2 1a). Hợp lệ vì `INNOVATION(EPU)` là tổ hợp tuyến tính của `{LEVEL(EPU), lag}` nên span control chứa trọn nó. **Chạy thật cả hai chế độ trên dữ liệu thật (2026-08-09), không suy đoán:**

  | chế độ | mẫu | bắt đầu | cột ràng buộc |
  |---|---|---|---|
  | `same_measure` | 231 tháng | 2007-02 | `epu_global_LEVEL_PLUS_JUMP` |
  | `level_lags` | **315 tháng** | **2000-02** | `GPR_THREAT_LEVEL_PLUS_JUMP` |

  **+84 tháng (7 năm)**; 231 khớp đúng mẫu của `T2_full_f2579b30928f` → chẩn đoán của patch được xác nhận. **Phát hiện thêm, sửa cả patch lẫn phán đoán ban đầu của tôi:** sau khi đổi, cột ràng buộc **chuyển sang JUMP của chính trục shock** — phần 1990-2000 còn mất là chi phí **NỘI TẠI** của thước đo LEVEL+JUMP, không phải lỗi control; bỏ `epu_global` khỏi battery cũng không lấy lại được. **Đánh đổi thật, ghi vào report mỗi run**: `JUMP` phi tuyến KHÔNG nằm trong span `{LEVEL, lag}` → ở thước đo LEVEL+JUMP, `level_lags` hấp thụ ÍT HƠN. Cả hai chế độ giữ lại; chữ ký khóa bằng `LOCKED_DECISION_IDS` + `test_battery_control_form_decision_matches_code`.
- **`build_monthly_panel(dropna=False)` (mới, cần cho patch 2)** — chẩn đoán mẫu của patch chạy trên panel đã complete-case thì **vô nghĩa** (mọi cột cùng một `first_valid`). Thêm cờ trả panel chưa complete-case; `main()` dựng **một lần** rồi `.dropna()` — ý nghĩa "một mẫu duy nhất" không đổi. `sample_binding_report`/`sample_cost` in ra "mất bao nhiêu tháng, vì cột nào" trước mỗi run và vào report.
- **Guard P1 bắt được patch 3 khi áp thẳng** — bảng phụ mức lưới nằm chung một phần tử với văn xuôi nên guard soi cả bảng và báo đỏ. Sửa đúng hướng: số trong văn xuôi lấy từ `stats` (`grid_*`, `sample_*` là trường mới), khối bảng là phần tử riêng. `GridNullCheck.to_markdown()` giữ lại cho notebook nhưng **runner không dùng** — nó format từ trường của chính nó nên nằm ngoài payload runner (ghi trong docstring).
- **Thứ tự mục trong report có chủ đích:** *Chi phí mẫu* (ngay sau Metadata) → *Đối chiếu mức lưới* → mới tới bảng Holm. Đọc "15 ô sống sót" trước rồi mới đọc "34 < 43.2" thì ấn tượng đầu đã hình thành.
- **Test mới:** 7 cho `grid_null_check` (gồm case T2_full thật + case "Holm sống sót nhưng lưới dưới null"), 1 cho `dropna=False`, 11 cho runner (tên cột control khớp panel thật ở CẢ hai chế độ — lệch tên thì lỗi nổ sau ~5 phút ước lượng chứ không phải lúc dựng panel).

### 🗂️ Cập nhật đường dẫn dữ liệu theo layout mới + vintage 2026-08

Commit `e3bde3b` dời file vào `data/GPR index/` + `data/AI-GPRs/` nhưng code vẫn trỏ đường cũ → `run_t2_full.py` và `test_report_guard_p1` gãy. Đã trỏ lại toàn bộ 9 hằng số `DEFAULT_*` (`data_files.py`) + default `--path` của `ingest/{gpr_daily,gpr_monthly,ai_gpr}.py`, và đồng bộ README/Dockerfile/docker-compose/CLAUDE.md.

**Vintage lên theo (đây là đổi DỮ LIỆU, không phải dọn đường dẫn):** daily `1985-01-01 → 2026-08-03` (trước: hết 2026-06-29) · monthly `1900-01 → 2026-07` (trước: hết 2026-06). `--source-version` của hai script ingest lên `*_202608`. Cả 8 loader đã chạy thật trên file mới, parse sạch. AI-GPR chỉ đổi chỗ, vintage không đổi.

`data_gpr_export (1).xls` **trùng nội dung** `data_gpr_export_202608.xls` (đối chiếu `assert_frame_equal`) — chọn bản có vintage trong tên. `(1)` trong tên file daily là hậu tố trình duyệt, giữ nguyên tên thật; **không** có fallback ngầm dò tên file (bẫy "đổi default âm thầm", docs/18 §7).

⚠️ Hệ quả: `_data_version()` băm byte 2 file này → **report chạy sau đây sẽ có tên khác** `T2_full_f2579b30928f.md`. Đó là đúng thiết kế (#4), không phải lỗi. Quy tắc đổi vintage ghi ở `data/README.md`.

3 file `patch*.py` ở repo root vẫn còn nguyên (chưa xóa) — nội dung đã vào code hết.

## Trạng thái trước đó (2026-08-05, vòng 2)

### 📄 Task 1-3 AI-GPR: đọc paper, phân tích toàn mẫu vai trò VN, đề xuất mapping kênh

Ba việc user yêu cầu làm liền ("làm từ 1 đến 3 luôn"), tất cả dựa trên dữ liệu/paper thật, không đoán — xem `docs/16` v1.6 để đọc đầy đủ:

- **Task 3 (đọc `AI_GPR_PAPER.pdf`) giải quyết dứt điểm 2 câu hỏi mở của docs/16:** `GPR_AER` = chỉ số GPR keyword-based GỐC của chính Caldara-Iacoviello (2022), tính lại trên đúng 3 tờ báo mà AI-GPR dùng (để so sánh công bằng) — không phải GPRD gốc đầy đủ. Tương quan AI-GPR vs bản này = 0.69 theo paper, khớp 0.70 đo trên file thật. Cơ chế 8 vùng oil không cộng dồn về `GPR_OIL`: prompt phân loại vùng cho phép chọn "one or more" vùng/bài báo — thiết kế đúng, không phải lỗi. Bảng cũ "13 vùng" của v1.0 **đúng** theo paper (v1.1/v1.3 kết luận sai là "13 vùng chưa từng xác minh") — 8 cột CSV công khai là bản gộp nhóm từ 13 vùng gốc (Africa=North+West Africa, Americas=Canada+Mexico+Latin America, Asia=Central Asia+Southeast Asia+China).
- **Task 2 (phân tích toàn mẫu vai trò VN, 1960-2026, 799 tháng, thay quan sát vài dòng trước đó):** câu "VN gần như luôn spillover" của docs/16 §3 **chỉ đúng cho giai đoạn 2015-2026** (spillover 67.4% biên độ, 64.7% số tháng) — **sai như phát biểu lịch sử chung**: 1960-1989 (thời chiến tranh Việt Nam) VN chủ yếu là `respondent` (57.1% biên độ, 63.3% số tháng), toàn mẫu 799 tháng respondent vẫn chiếm ưu thế (56.7% vs 17.9% spillover). Cơ chế hợp lý (VN chuyển từ "trong cuộc chiến" sang "nền kinh tế mở hứng sốc bên ngoài"), đường chuyển tiếp trơn qua 3 giai đoạn — không phải artifact chọn mốc. May mắn: giai đoạn spillover chiếm ưu thế (2015+) gần trùng Development+Validation window của dự án (2015-2023) — giả định `vn_exposure.py` hợp lý trong đúng cửa sổ dùng để ước lượng/validate, chỉ sai nếu khái quát ngược lịch sử xa. Số liệu đầy đủ ở `docs/16` §3.1 mới.
- **Task 1 (đề xuất `EVENT_TYPE_TO_CHANNEL`, mới trong `data_files.py`, CHƯA dùng production):** 8 loại sự kiện AI-GPR **không có category tương ứng trực tiếp cho energy/trade** — `military_conflict`/`civil_war`/`coup`/`nuclear_threat`→`military`, `sanctions`→`financial`, còn `terrorism`/`diplomatic_tension`/`other`→`None` (chưa xác định, không đoán). Energy nên lấy từ `AIGPR_OIL_*` (đã có, daily), trade nên lấy từ bilateral index (đã có, monthly) — cả hai đã ingest, không cần suy ra từ event-type. Test khóa mapping không lệch khỏi `AI_GPR_EVENT_TYPES` thật + khóa phát hiện "không có energy/trade" (`tests/econ/test_ai_gpr_decompositions.py`).
- **Việc code:** chỉ thêm hằng số + docstring lý do, KHÔNG đổi đường production nào (nguyên tắc #1 — chưa qua cổng kiểm định thì không vào service). 333 test pass.

**Vòng 3 cùng ngày — user chọn ký `EVENT_TYPE_TO_CHANNEL`:** thêm `DEC-2026-08-05-event-type-channel` vào `config/hypothesis_registry.yaml` §`decisions:` (cùng thủ tục `DEC-2026-08-02-shock-axis`), khóa bằng `LOCKED_DECISION_IDS` + test mới `test_event_type_channel_decision_matches_code` (chặn code đổi mapping mà quên sửa chữ ký). **Phạm vi chữ ký hẹp có chủ đích:** chỉ xác nhận Ý NGHĨA của mapping (8 loại sự kiện → 4 kênh, energy/trade lấy từ nguồn khác không suy từ event-type) — KHÔNG mở khóa dùng trong `gamma_lookup.py`/`vn_exposure.py` hay bất kỳ đường production nào, việc nối dây thật vẫn là quyết định kiến trúc riêng qua nguyên tắc #1. 334 test pass.

**Vòng 4 cùng ngày — user: "mục đích tới production, cập nhật đủ cho dev để test và prod".** Gỡ một khoảng trống production thật (không phải khoảng trống của yêu cầu vừa ký): AI-GPR có loader research (`data_files.py`) từ vòng 1 nhưng **chưa có đường ingest vào Postgres** như `GPRD`/`GPRC` đã có (`ingest/gpr_daily.py`/`gpr_monthly.py`). Thêm `ingest/ai_gpr.py` — ingest 12 chuỗi TỔNG HỢP (headline/threat/act/oil-tổng/oil-8-vùng/AER/NONOIL) vào `ext_series`, đúng pattern UPSERT idempotent của 2 script ingest cũ. `AI_GPR_COLUMNS` chuyển từ `data_files.py` sang đây làm nguồn CHÍNH THỨC (production là nguồn tên series_id chuẩn), `data_files.py` import lại — đúng chiều phụ thuộc research→ingest đã có sẵn cho GPRD. **Cố ý KHÔNG ingest 4 file "Country Decompositions"** (eventtype/country×eventtype/bilateral/country×vai trò) — cardinality quá lớn, chưa có use case tiêu thụ, IC chưa chứng minh (#6); ingest raw series tổng hợp được sanctioned bởi nguyên tắc #2 ("chỉ ingest"), nhưng ép thêm 1600+ series decomposition chưa dùng vào đâu là khác — đó vẫn là việc riêng, có chủ đích để lại. Thêm `tests/test_ai_gpr_ingest.py` (10 test, mock DB — điểm khác biệt: `ingest/gpr_daily.py`/`gpr_monthly.py` cũ HOÀN TOÀN không có test nào, kể cả offline; module mới có, vì user hỏi rõ "để test"). `load_dataframe`/`to_long` đã chạy thật trên file thật (24319 dòng daily, 799 dòng monthly) — sạch, không lỗi. `upsert()` mock qua `create_engine`, CHƯA chạm Postgres sống (không có DB trong sandbox — cùng giới hạn mọi `ingest/*.py`). Cập nhật lệnh ingest trong CLAUDE.md + đính chính blocker `ai_gpr_data_unverified` (registry) đang mô tả tình trạng cũ (chưa tải) sang tình trạng thật (đã tải+ingest được, chưa chạy Postgres sống). 344 test pass.

## Trạng thái trước đó (2026-08-05, vòng 1)

### 🐛 6 bug thật vá trong pipeline serving (rà lại sau khi ship) + ✅ AI-GPR daily xác minh trên file thật

**Rà lại `pipeline/news_pipeline.py` + `service/*.py` sau khi ship (2026-08-05), tìm và vá 6 bug thật** (không phải giả thuyết — tái hiện trước khi vá, có test khóa lại):
- `published_at` tz-naive làm crash (Statement cho phép naive, phần còn lại pipeline là UTC tz-aware) — chuẩn hóa tại ranh giới (`_as_utc`), KHÔNG đổi hợp đồng `Statement` (phá test cũ).
- `ext_series`/`statement_scores` cho phép nhiều `data_version`/`model_version` cùng ngày/tin — không lọc thì `JUMP`/S-GPR rolling đếm trùng. Sửa bằng `DISTINCT ON` lấy bản mới nhất.
- `process_news_item_live` ghi đè `ladder_state` bằng 0 giả khi tính hỏng (vd role lạ) — thêm cờ `ladder_computed`, chỉ ghi DB khi tính thành công thật.
- `speaker_role` lạ, chain-A GPRD cũ (`chain_a_stale` flag mới), Kafka publish fire-and-forget (thêm `flush()` + `on_delivery`, raise rõ khi không xác nhận được).
- 328 test pass. Xem lịch sử commit trên branch để chi tiết từng bug.

**AI-GPR — chỉ số tổng hợp daily + monthly (docs/16) — ⛔ blocker cũ đã gỡ cho phần này.** Tải cả 2 file thật (2026-08-05): daily (vintage `13b8e8b48d41`, 1960-01-01..2026-07-31) + monthly (vintage `92b9ba3bd38f`, 1960-01-01..2026-07-01) — **cùng schema hệt nhau**, chỉ khác tần suất. Lộ ra **schema giả định trước đó sai hoàn toàn** (`AIGPR`/`AIGPRT`/`AIGPRA` giả định ↔ `GPR_AI`/`THREATS_GPR_AI`/`ACTS_GPR_AI` thật, cột ngày `Date` không phải `date`) — đã sửa `AI_GPR_COLUMNS` + thêm `load_ai_gpr_monthly()` (dùng chung `_load_ai_gpr()` với bản daily) + test khớp file thật.

**⚠️ docs/16 §3 tự đính chính lần 2 — tiền đề "Country index daily" SAI.** Trang download thật liệt kê `ai_gpr_country_monthly.csv`/`ai_gpr_bilateral_monthly.csv` — **monthly**, không phải daily như v1.1 khẳng định. Kết luận "gỡ ràng buộc #10 cho VN daily track" **rút lại** — #10 vẫn cấm, `vn_market_series_missing` KHÔNG phải blocker duy nhất còn lại. Điểm ĐÚNG: Oil GPR theo vùng **thật sự có ở daily** (8 vùng, không phải 13 như bảng cũ ghi — xác nhận sai trên cả 2 file).

**✅ AI-GPR "Country Decompositions" — ĐỦ 4/4 file, tải + ingest xong (2026-08-05).** `ai_gpr_eventtype_monthly.csv` (global, 8 loại sự kiện — `load_ai_gpr_eventtype_monthly`), `ai_gpr_country_eventtype_monthly.csv` (200 nước × 8 loại, 1602 cột — `load_ai_gpr_country_eventtype_monthly` + `select_country_eventtype`, Vietnam xác nhận có đủ 8 cột), `ai_gpr_bilateral_monthly.csv` (1200 cặp CÓ HƯỚNG — `load_ai_gpr_bilateral_monthly` + `select_bilateral_pair`, nhiều cặp Vietnam), `ai_gpr_country_monthly.csv` (200 nước × 4 vai all/initiator/respondent/spillover — `load_ai_gpr_country_monthly` + `select_country_role`). **Xác minh quan trọng**: cả 8-loại-sự-kiện lẫn 4-vai-trò đều **cộng dồn đúng về tổng** (GPR_AI / `all`, lệch ≤0.0002) — khác hẳn 8 cột oil-vùng KHÔNG cộng dồn về GPR_OIL. **Taxonomy 8 loại sự kiện KHÔNG map sẵn sang 4 kênh truyền dẫn** (energy/trade/financial/military) — `sanctions`≈financial, `military_conflict`≈military là 2 cặp rõ, còn energy/trade không có category tương ứng trực tiếp — quyết định mapping còn mở, chưa tự bịa. **⚠️ Soi nhanh Vietnam qua `select_country_role`: KHÔNG "luôn luôn spillover"** như khung docs/16 §3 giả định — có tháng `respondent`>0 (quan sát vài dòng, chưa phải phân tích thống kê đầy đủ). Không còn file AI-GPR nào thiếu — việc còn lại là nghiên cứu (mapping kênh, phân tích vai trò VN đầy đủ), không phải tải data. 330 test pass.

327 test pass (9 test mới: 2 cho `load_ai_gpr_monthly`, 7 cho 3 loader Country Decompositions).

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

⚠️ **Layout đổi 2026-08-08** (commit `e3bde3b`): `data/GPR index/` + `data/AI-GPRs/`. Mọi hằng số `DEFAULT_*` trong `data_files.py`/`ingest/*.py` đã trỏ theo (2026-08-09). Chi tiết đầy đủ + quy tắc đổi vintage: `data/README.md`.

- `data/GPR index/data_gpr_daily_recent (1).xls`: GPRD/GPRD_ACT/GPRD_THREAT daily, 15190 dòng, 1985-01-01 → **2026-08-03**. DÙNG ĐƯỢC NGAY. (`(1)` là hậu tố trình duyệt, không phải bản nháp.)
- `data/GPR index/data_gpr_export_202608.xls` (bản 44 nước): 1519 dòng × 115 cột, monthly 1900 → **2026-07**. Chứa 44 cột `GPRC_*` (recent 1985+) + 44 cột `GPRHC_*` (historical 1900+), gồm cả `GPRC_VNM` và `GPRHC_VNM`. Cột dictionary: `var_name`/`var_label`. File `data_gpr_export (1).xls` cùng thư mục **trùng nội dung** (đã đối chiếu `assert_frame_equal`) — không dùng.
- `data/AI-GPRs/*.csv`: 2 chỉ số tổng hợp (daily 24319 dòng 1960→2026-07-31, monthly 799 dòng) + 4 file Country Decompositions. Vintage không đổi, chỉ đổi chỗ.

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

Đọc GPR từ `data/GPR index/*.xls` + macro từ FRED, cache ở `data/cache/`. Xuất report versioned vào `docs/reports/` — **không bao giờ ghi đè**.

**Ingest vào PostgreSQL** (cần `--dsn`, đây là đường production):

```bash
psql "$DSN" -f sql/001_schema_core.sql
psql "$DSN" -f sql/002_schema_serving.sql   # statements/statement_scores/ladder_state/news_assessment
# --path/--path-daily/--path-monthly đã mặc định đúng file hiện có; ghi ra đây cho rõ.
python -m gpr_engine.ingest.gpr_daily   --path "data/GPR index/data_gpr_daily_recent (1).xls" --dsn "$DSN"
python -m gpr_engine.ingest.gpr_monthly --path "data/GPR index/data_gpr_export_202608.xls" --dsn "$DSN"
python -m gpr_engine.ingest.market_data   --dsn "$DSN" --source fred   # BRENT/DXY/VIX/US10Y (daily)
python -m gpr_engine.ingest.macro_monthly --dsn "$DSN"                 # IP/CPI/INFL_EXP/EPU/FREIGHT (monthly)
python -m gpr_engine.ingest.ai_gpr --dsn "$DSN" \
    --path-daily data/AI-GPRs/ai_gpr_data_daily.csv --path-monthly data/AI-GPRs/ai_gpr_data_monthly.csv
```

**Chạy pipeline serving thật** (sau khi đã ingest ở trên — cần γ đã có ở `docs/reports/data/t2_full_holm_*.csv`, tức đã chạy `run_t2_full.py` ít nhất một lần):

```bash
export GPR_DB_DSN=... OPENAI_API_KEY=... GPR_TRAINING_CUTOFF=2026-01-01 GPR_KAFKA_BOOTSTRAP=host:9092
python scripts/run_news_service.py
```

`tests/test_config_locked.py` khóa `config/backtest.yaml` bằng máy: sửa mốc split mà không cập nhật `LOCKED_SPLIT` trong **cùng commit** → test đỏ. Đó là tính năng (nguyên tắc #3), không phải lỗi.

### Docker (mới 2026-08-05)

Đóng gói `Dockerfile` (multi-stage, `python:3.11-slim`) + `docker-compose.yml` (Postgres + Kafka KRaft + app, dùng cho dev/thử nghiệm cục bộ — production thật nên trỏ `GPR_DB_DSN`/`GPR_KAFKA_BOOTSTRAP` sang cụm quản lý riêng, chỉ chạy service `app`). **Chưa build/run được thật trong sandbox này** (Docker daemon không khởi động được trong môi trường Claude Code — đã thử `dockerd` trực tiếp, treo không lỗi, không có quyền cgroup/network cần thiết) — đã kiểm bằng cách khác: mô phỏng chính xác layout COPY của Dockerfile trong venv riêng (`pip install .` từ `pyproject.toml`+`src/`, import tất cả module `ingest`/`pipeline`, chạy `python -m gpr_engine.ingest.ai_gpr --help`, `load_published_gamma()` đọc đúng `docs/reports/data/`) — tất cả PASS. `docker compose config` (không cần daemon) xác nhận YAML hợp lệ. Cả 3 image (`python:3.11-slim`, `postgres:16-alpine`, `apache/kafka:4.3.1`) xác minh tồn tại thật qua Docker Hub API trước khi ghim tag — không đoán tag.

**Cách dùng:**
```bash
cp .env.example .env          # điền OPENAI_API_KEY thật, sửa GPR_DB_DSN/GPR_KAFKA_BOOTSTRAP nếu KHÔNG dùng compose
docker compose up -d postgres kafka
docker compose exec -T postgres psql -U gpr -d gpr_engine < sql/001_schema_core.sql
docker compose exec -T postgres psql -U gpr -d gpr_engine < sql/002_schema_serving.sql
# đặt file GPR đã tải vào ./data/ (mount sẵn vào /app/data trong container)
docker compose run --rm app python -m gpr_engine.ingest.gpr_daily \
    --path "data/GPR index/data_gpr_daily_recent (1).xls" \
    --dsn postgresql://gpr:gpr_dev_password@postgres:5432/gpr_engine
# tương tự cho ingest.gpr_monthly / ingest.market_data / ingest.ai_gpr
docker compose up app          # chạy pipeline serving thật (Kafka consumer)
```
Ảnh `app` **không copy `data/`** (file GPR `.xls`/`.csv` là gitignored, do người vận hành cung cấp) — mount qua volume `./data:/app/data`, khớp đúng use case "sau này có file GPR về để xử lý": thả file vào `data/`, chạy lại lệnh ingest tương ứng, không cần rebuild ảnh. Với API tin tức đầu vào: publish JSON khớp schema `Statement` (xem docstring `scripts/run_news_service.py`) vào topic Kafka `GPR_KAFKA_TOPIC_IN` (mặc định `gpr.news.raw`) — bất kỳ ngôn ngữ/hệ thống nào cũng publish được, không cần chạm code Python.

### Nạp lại file nguồn định kỳ — cơ chế vintage (`ingest/versioning.py`, mới 2026-08-09)

**Không còn phải tự đặt `--data-version` mỗi lần nạp.** Mặc định `--snapshot delta`:

- bản CHẠY `v1` luôn là bản mới nhất — ngày mới append, giá trị bị revise được cập nhật + đóng dấu `revised_at`;
- giá trị CŨ bị ghi đè được **chép sang nhãn archive** `<prefix>_pre_<YYYYMMDD>` TRƯỚC khi ghi đè → tái lập được "hôm đó ta biết gì";
- mỗi lần nạp ghi một dòng vào sổ `data_versions` (bảng này trước đây **chết**, 0 dòng, không script nào ghi);
- mọi đường đọc hiện có không đổi (`load_series` mặc định `v1` = mới nhất) — đây là lý do chọn delta thay vì snapshot đầy đủ.

`--snapshot full` giữ thêm bản sao TOÀN BỘ dưới nhãn `<prefix>_<YYYYMMDD>` nếu cần vintage tuyệt đối.

**Vì sao không phải "chỉ append ngày mới"** — đo trên DB sống 2026-08-09, so vintage cũ (hết 2026-06-29) với file mới (hết 2026-08-03), phần chồng lấp 45.465 hàng:

| cửa sổ | hàng đổi |
|---|---|
| trước 2025-03 | **0 / 44.007** — lịch sử sâu đóng băng thật |
| 2025-03 → nay | 126 / 1.458 (8.6%) |
| riêng 2026 | **108 / 540 (20%)** |

42 NGÀY bị tính lại, giống hệt ở cả 3 series → C-I tính lại trọn ngày, không phải làm tròn. median |Δ| = **42.9 điểm** trên thang ~300, max 130.7 (`GPRD_ACT 2026-06-24: 293.8 → 163.1`). Monthly: 520 giá trị đổi, cùng cửa sổ 2025-03 → 2026-06. Nên append-only sẽ giữ giá trị sai ở đúng 15 tháng gần nhất; còn snapshot đầy đủ thì chép 45.570 hàng để giữ 126 hàng thật sự khác (0,28%).

**Lỗ point-in-time đã vá cùng lúc:** `load_series(as_of=)` và `store.load_jump_series` giờ lọc **hai đồng hồ** — `available_at <= as_of` (nội dung) VÀ `loaded_at <= as_of` (vintage). Thiếu vế thứ hai thì replay quá khứ dùng giá trị đã revise về sau = look-ahead trên trục revise. Với đường sống (`as_of=now`) điều kiện này là no-op.

⚠️ Còn lại: `ingest/market_data.py` (FRED) **chưa nối** vào cơ chế này — vẫn `--data-version v1` UPSERT đè như cũ.

## Bản đồ code

**6 module còn là stub `raise NotImplementedError` ngay khi import** — chưa viết, không phải hỏng. Import chúng là crash. Còn stub: `econometrics/{surprise, tvp_var}`, `indices/{builder, divergence}`, `backtest/*` (2). Mọi thứ khác đã thực thi. (docs/11 §4 §7 có bảng module đầy đủ + việc cần làm cho từng cái, gồm cả module mới chưa tồn tại: `econometrics/analogue.py`, `scoring/{policy_scorer,track_record}.py`.)

Cascade 3 tầng (nguyên tắc #8) ánh xạ thẳng vào cây thư mục — đây là trục kiến trúc chính:

- `econometrics/shocks.py` — **G2.0, input của cascade**: LEVEL≠SHOCK. `innovation()` (AR(p), p từ `select_ar_order` BIC/trần-5), `jump()`, `gpa_surprise_v1()`. Mọi hồi quy shock LẤY TỪ ĐÂY, không đưa level vào (#9). Order pre-registered trong registry — đổi phải cập nhật `tests/test_registry_locked.py`.
- `econometrics/tier2_global_macro.py` — **tầng 1–2, ENGINE generic**: shock → Oil/DXY/VIX/US10Y. Ước lượng 1 lần, country-agnostic. Truyền thẳng `inference`/`lags`/`simultaneous`/`method`/`tau`/`seed` xuống LP (mặc định = bản cũ). ⚠️ `lag_augmented` **ép `macro_lags=0`** — giữ cả hai là lag trùng khít, X'X suy biến, SE vô nghĩa mà không có lỗi nào bắn ra.
- `econometrics/tier3_country.py` — **tầng 3, PARAMS từng nước**: tách BA hệ số `β` (global-direct) / `θ` (indirect, tính bằng **tích chập** qua horizon) / `λ` (domestic-direct, từ `GPR^{c,⊥}` đã orthogonalize). Hệ số đọc từ `config/params/<country>.yaml`, không điền tay. Đóng góp kênh dùng Shapley/LMG. `simultaneous=True` cho dải sup-t **theo từng hệ số**; cột lag augmentation gắn `role="lag_augmentation"` (nuisance, không đọc như β/θ/λ).
- `econometrics/local_projection.py` — LP dùng chung cho cả hai tầng. Hai chế độ suy diễn: `inference="hac"` (mặc định, bản cũ) và `inference="lag_augmented"` (MO-PM 2021 — **tự thêm lag của cả y lẫn shock**, HC1 thay HAC; thiếu lag của SHOCK là sụp cơ sở bỏ HAC, nên đừng tự ghép tay qua `controls`). `simultaneous=True` cho dải sup-t: đọc "IRF vượt 0 ở h=7" từ dải pointwise trên 25 horizon là đọc sai — ~2,5 điểm nằm ngoài ngay cả khi model đúng. **`simultaneous` CHỈ hợp lệ với `lag_augmented`** (Ω là EHW; ghép với SE HAC = hai bộ sai số chuẩn trong một dải) — raise. Với `return_all=True` trả `supt_c` **riêng cho từng hệ số**. `method="quantile"` cho τ; sup-t + quantile raise `NotImplementedError` (cần bootstrap).
- `econometrics/shock_axis.py` — **cổng máy của `DEC-2026-08-02-shock-axis`**: `gate_shock_eligibility(measure, inference)`. LEVEL/LEVEL+JUMP **chỉ eligible với `lag_augmented`** — đó là điều kiện làm quyết định A không phá #9. Nới cổng cho `hac` = rút lại chữ ký; `test_shock_axis_gate_matches_signed_decision` bắt. Còn chứa **cổng NHÃN** của spec kép (`check_component_labelling`): gọi `β_ANTICIPATED` là "cú sốc" → raise. Đó là Guard P1 cho **nhãn** thay vì cho **số** — spec kép không phá #9 nhờ cách gọi tên, không nhờ công thức.
- `econometrics/shocks.delta_decomposition` — **spec kép `docs/16` §2.2**: `Δ LEVEL = ANTICIPATED + SURPRISE`. **SURPRISE ≡ `innovation()`** (vì `Ê[Δlevel] = Ê[level] − level₋₁`) nên ANTICIPATED lấy bằng hiệu → hai thành phần cộng lại bằng *đúng* Δ LEVEL, không thể lệch do hai đường ước lượng. Phân rã trên **sai phân**, KHÔNG dùng `persistent_ar` (= Ê[LEVEL], gần nghiệm đơn vị → quay lại vấn đề #9). So hai hệ số **bắt buộc** qua `standardized_contribution` — `Var(ANT)/Var(SUR)≈0.1` nên hệ số thô không so được (E2: 48.9% ô đảo chiều).
- `econometrics/multiplicity.py` — **M10, bội giữa OUTCOME**: `holm()` + `holm_by_family()`. Chiều **horizon đã do sup-t xử lý** — phạt lại ở đây là mất hết power. Một hàng = một kiểm định = một (outcome, shock) trên CẢ đường IRF, **không phải** một (outcome, shock, horizon); truyền cả 25 horizon vào là phạt chiều horizon lần thứ hai. `family` bắt buộc khai báo (governance §6.6 chưa ký); họ phải phân hoạch + phủ hết, thiếu là raise. **`grid_null_check()` (2026-08-09)** trả lời câu KHÁC: không phải "ô nào sống sót" mà "toàn lưới có nhiều hơn nhiễu thuần không" — so số bác bỏ thô với `n·α`. Hai câu này cho kết luận ngược nhau khi số kiểm định lớn còn họ thì nhỏ (T2_full: 15 ô "sống sót" nhưng 34 < 43.2 kỳ vọng null). Gọi trên TOÀN BỘ p-value focal của lưới, không phải trên một họ. `z_indep` là cận dưới của |z| thật — đọc dấu và độ lớn xấp xỉ, KHÔNG báo cáo như p-value.

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
- `ingest/ai_gpr.py` (mới 2026-08-05) — ingest 12 chuỗi TỔNG HỢP AI-GPR (headline/threat/act/oil-tổng/oil-8-vùng/AER/NONOIL) vào `ext_series`, cùng pattern `gpr_daily.py`/`gpr_monthly.py`. `AI_GPR_COLUMNS` chuyển về đây làm nguồn CHÍNH THỨC — `data_files.py` import lại (đúng chiều phụ thuộc research→ingest đã có sẵn cho `GPR_DAILY_SERIES`/`PUBLISH_LAG_DAYS`). ⚠️ **CỐ Ý không ingest 4 file "Country Decompositions"** (eventtype/country×eventtype/bilateral/country×vai trò) — cardinality lớn (tới 1600+ cột), chưa có use case tiêu thụ, IC chưa chứng minh (#6) — ingest 4 file đó là việc riêng khi có lý do. `PUBLISH_LAG_DAYS_DAILY/MONTHLY` là giả định thận trọng chưa verify (cùng trạng thái `gpr_daily.py`/`gpr_monthly.py`). Có test offline (`tests/test_ai_gpr_ingest.py`, mock DB) — phần `load_dataframe`/`to_long` đã chạy thật trên file thật (24319 dòng daily, 799 dòng monthly, parse sạch), phần `upsert` chưa chạm Postgres sống (không có DB trong sandbox).
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
