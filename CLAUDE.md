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

## Trạng thái hiện tại (cập nhật 2026-07-19)

**Bối cảnh:** review ngoài (`docs/08`) chỉ ra 8 lỗi 🔴 → sửa xong ở Phase F. Công thức chân lý: `docs/07_formulas_reference_v2.md` (v2.1, v1 archived). Thứ tự build: `docs/10` §4 (Phase F→D), giờ **product plan `docs/11` v2.1 chi phối hướng sản phẩm** và `docs/12` (specification curve) là protocol pre-registered cho suy diễn tầng 2. Đọc 11 + 12 trước khi làm tiếp econometrics.

- **G1 + Phase F + D1–D3 + E1 done.** Ingest ×3, schema `ext_series` (available_at/data_version…), `load_series(as_of=)` point-in-time, `backtest.yaml` split 4 tầng khóa máy — tất cả xong. ~50 test pass.
- **G2.0 (D2) done:** `econometrics/shocks.py` — `LEVEL/PERSISTENT/INNOVATION/JUMP` + `gpa_surprise_v1`, rolling no-leakage. PERSISTENT = AR(p), **p chọn bằng BIC trong trần parsimony p=5** (KHÔNG AIC — AIC/BIC đuổi biên với daily; robustness đã chạy). Order pre-registered **GPRD=5, GPRD_ACT=5, GPRD_THREAT=2**, khóa ở `config/hypothesis_registry.yaml`.
- **G0 (D1) done:** `config/hypothesis_registry.yaml` + `docs/g0_governance.md` + `tests/test_registry_locked.py` (khóa máy giống config-lock). Pre-register KĐ1/3/5/12.
- **G2a rerun (D3) done, CHỜ HUMAN REVIEW:** `docs/reports/G2a_innovation_*_ar5-5-2.md`. GPRD innovation → macro: VIX kênh mạnh nhất (13/31 h) nhưng **dấu âm ở h dài — phản trực giác, cần soi**. Verdict = PENDING HUMAN REVIEW (máy chấm 1/2/3/5; user quyết 4/6). Mục human review còn trống.
- **E1 done:** `docs/reports/E1_shock_diagnosis_*.md`. Bằng chứng cứng: cú sốc Hormuz (GPRD→500.8 ngày 2026-03-02) NẰM TRONG mẫu G2a mà γ(oil)≈0. **AR(5) nén INNOVATION xuống 2.77× ngày thường trong khi JUMP giữ percentile 99.9** → JUMP nên là shock chính (docs/11 §5.2 KĐ-N1).

- **E1b done:** `docs/reports/E1b_shock_ranking_*.md`. Rank thước đo shock theo sức phát hiện 166 episode lớn: **LEVEL+JUMP 68.7% > JUMP 55.4% > INNOVATION 32.5%** (winner đứng đầu mọi sub-sample). → ô chính SCA-01 (`primary_cell.shock=LEVEL+JUMP`) đã điền trong registry. Thêm `tests/test_report_guard_p1.py` (Guard P1: mọi số narrative khớp payload).

- **`build_monthly_panel()` done** (2026-07-19): `data_files.build_monthly_panel` — track monthly, grid dầu-tháng thật (KHÔNG forward-fill, #10). Cột: `GPR_INNOV` (β), `GPRC_VNM_ORTH_INNOV` (λ — orthogonalize khỏi GPR global rồi innovation), macro tổng hợp tháng. 378 tháng 1995-2026, corr(β,λ)=−0.21. 6 test.
- **E0 replication PASS** (2026-07-19): `scripts/run_e0_replication.py` — tái lập C-I 2022 (GPR→IP giảm h=1,2 p<0.10, đáy β=−0.37 h=2). Pipeline (nạp+align+LP+HAC) ĐÚNG → null của G2a/lưới SCA là phát hiện thật, không phải bug. Report `E0_replication_CI2022_*.md`. Ngoại lệ #9 có chủ đích: E0 dùng log(GPR) LEVEL vì tái lập spec paper.

**⚠️ Nợ đường tới hạn — CHỈ CÒN quyết định của user (docs/12 §9):**
- **Lưới SCA-01 `blockers=[holdout_decision_g0]`** — tất cả blocker code đã gỡ. Còn DUY NHẤT: **user quyết holdout A/B/C** cho 2026-H1 (Hormuz làm nó thành regime đơn lẻ), ghi `g0_governance.md` TRƯỚC khi chạy lưới (docs/11 §9/§13). + protocol_commit docs/12 + đính chính lỗi Romano-Wolf docs/12.
- **E0 replication harness** (Caldara-Iacoviello, docs/11 §5.8) — chặn lưới; docs/10 chưa liệt kê (nợ đồng bộ 10↔11).
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

**Research runner tầng 2 (G2a, offline — không cần PostgreSQL):**

```bash
.venv/bin/python scripts/run_tier2.py                            # shock=zscore LEVEL -> report tự đánh dấu INELIGIBLE (#9)
.venv/bin/python scripts/run_tier2.py --shock-method innovation  # SHOCK HỢP LỆ (G2.0 xong) — dùng shocks.innovation
.venv/bin/python scripts/run_tier2.py --refresh --horizon 20     # --refresh = kéo lại FRED, bỏ cache
.venv/bin/python scripts/run_e1_diagnosis.py                     # E1: chẩn đoán spec shock quanh Hormuz 2026-02 (docs/11 §10)
```

Report versioned vào `docs/reports/` — **không bao giờ ghi đè** (`FileExistsError`). Tên mã hóa spec: innovation kèm order-tag (`..._ar5-5-2.md`). Đổi spec → xóa artifact cũ trước khi chạy lại.

**Guard số (P1, docs/11 §1 / docs/12 §5.4):** mọi số trong narrative report PHẢI tính từ dict `stats`, KHÔNG hard-code. Bug đã xảy ra thật (E1 ghi "1.8×" trong khi payload = 2.77×). Thêm số vào report thì thêm trường vào `stats` rồi tham chiếu, không gõ tay.

Đọc GPR từ `data/*.xls` + macro từ FRED, cache ở `data/cache/`. Xuất report versioned vào `docs/reports/` — **không bao giờ ghi đè**.

**Ingest vào PostgreSQL** (cần `--dsn`, đây là đường production):

```bash
psql "$DSN" -f sql/001_schema_core.sql
python -m gpr_engine.ingest.gpr_daily   --path data/data_gpr_daily_recent.xls --dsn "$DSN"
python -m gpr_engine.ingest.gpr_monthly --path data/data_gpr_export_202607.xls --dsn "$DSN"
python -m gpr_engine.ingest.market_data --dsn "$DSN" --source fred
```

`tests/test_config_locked.py` khóa `config/backtest.yaml` bằng máy: sửa mốc split mà không cập nhật `LOCKED_SPLIT` trong **cùng commit** → test đỏ. Đó là tính năng (nguyên tắc #3), không phải lỗi.

## Bản đồ code

**9 module còn là stub `raise NotImplementedError` ngay khi import** — chưa viết, không phải hỏng. Import chúng là crash. Đã thực thi: `ingest/*` (3), `econometrics/{dataset, data_files, local_projection, tier2_global_macro, tier3_country, shocks}`. Còn stub: `econometrics/{surprise, ladder, panel_var, tvp_var}`, `indices/*` (3), `backtest/*` (2), `scoring/statement_scorer`. (docs/11 §4 §7 có bảng module đầy đủ + việc cần làm cho từng cái, gồm cả module mới chưa tồn tại: `econometrics/analogue.py`, `scoring/{policy_scorer,track_record}.py`.)

Cascade 3 tầng (nguyên tắc #8) ánh xạ thẳng vào cây thư mục — đây là trục kiến trúc chính:

- `econometrics/shocks.py` — **G2.0, input của cascade**: LEVEL≠SHOCK. `innovation()` (AR(p), p từ `select_ar_order` BIC/trần-5), `jump()`, `gpa_surprise_v1()`. Mọi hồi quy shock LẤY TỪ ĐÂY, không đưa level vào (#9). Order pre-registered trong registry — đổi phải cập nhật `tests/test_registry_locked.py`.
- `econometrics/tier2_global_macro.py` — **tầng 1–2, ENGINE generic**: shock → Oil/DXY/VIX/US10Y. Ước lượng 1 lần, country-agnostic.
- `econometrics/tier3_country.py` — **tầng 3, PARAMS từng nước**: tách BA hệ số `β` (global-direct) / `θ` (indirect, tính bằng **tích chập** qua horizon) / `λ` (domestic-direct, từ `GPR^{c,⊥}` đã orthogonalize). Hệ số đọc từ `config/params/<country>.yaml`, không điền tay. Đóng góp kênh dùng Shapley/LMG.
- `econometrics/local_projection.py` — LP dùng chung cho cả hai tầng.

**Governance (khóa máy):** `config/hypothesis_registry.yaml` pre-register giả thuyết + AR order + trial log; `config/backtest.yaml` khóa split. Cả hai có test khóa (`tests/test_registry_locked.py`, `tests/test_config_locked.py`): sửa giá trị đã khóa mà không cập nhật hằng số `LOCKED_*` trong cùng commit → test đỏ. Policy văn bản ở `docs/g0_governance.md`.

**Hai đường nạp dữ liệu song song, cố ý:**

- `dataset.py` — đường **production**, đọc `ext_series` từ PostgreSQL, point-in-time qua `load_series(..., as_of=...)`.
- `data_files.py` — đường **research offline**, đọc file + FRED. Dùng lại đúng transform của `dataset.py` (`log1p_gpr`, `transform_global_macro`) — khác I/O, **không lặp lại quy ước biến đổi**. Thêm transform mới thì sửa ở `dataset.py`, không fork sang đây.

Quy ước transform (docs/07 §0), sai là hỏng ước lượng: shock GPR vào hồi quy → **INNOVATION** (`shocks.innovation`, #9 — KHÔNG đưa level); z-score/log1p chỉ là LEVEL đối chứng (run_tier2 tự gắn INELIGIBLE khi dùng); Oil/DXY → `Δln`; VIX → giữ level; US10Y → sai phân. (log1p ép GPRD 370→5.9 làm phẳng spike — log1p chỉ dành country-GPR nước nhỏ, không cho GPRD daily.)

Gate là **người quyết, không phải máy**: `run_tier2.gate_checklist` xuất verdict + mục Human review; run trên level tự gắn `INELIGIBLE` theo nguyên tắc #9.

## Cách làm việc trong repo này

- Đọc `docs/` theo thứ tự số trước khi code module tương ứng.
- Mỗi module có test đi kèm trong `tests/`. Viết test trước cho phần công thức (econometrics, indices).
- Notebook khám phá đặt trong `notebooks/`, không import ngược vào production code.
- Commit nhỏ, message rõ. Không refactor lan man ngoài scope task đang làm.
- Khi bí về thiết kế: hỏi lại, đừng tự quyết định kiến trúc lớn.
