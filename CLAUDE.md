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

## Trạng thái hiện tại (cập nhật 2026-07-16, sau review `docs/08` + phản hồi `docs/09`)

**Bối cảnh:** review ngoài (`docs/08`) chỉ ra 8 lỗi phương pháp 🔴 phải sửa TRƯỚC G2. Phản hồi + phân loại ở `docs/09`. Công thức đã sửa ở `docs/07_formulas_reference_v2.md` (v2.1 — **file 07 v2 là nguồn chân lý công thức, bản v1 đã archive**). Thứ tự build mới: `docs/09` §4.

- **G1 done:** `ingest/gpr_daily.py`, `ingest/gpr_monthly.py`, `ingest/market_data.py` (FRED/yfinance macro; VN series chờ đường nối BeaverX), `sql/001_schema_core.sql`, `notebooks/01_explore.ipynb` (narrative check pass: đỉnh GPRHC_VNM khớp Chiến tranh VN, GPRC_VNM đỉnh cửa sổ 2018+ ở 2025-04/2026-03; corr GPRC_VNM~GPRD ≈ 0.48).
- **Đồng bộ review done (2026-07-16):** schema `ext_series` + `available_at/revised_at/source_version/data_version/quality_flag` & bảng `index_quality`; 3 ingest module ghi `available_at` (daily +1d, monthly = đầu tháng kế +5d, market = close ngày D); `load_series(as_of=)` point-in-time; `backtest.yaml` split 4 tầng + final holdout 2026-H1; nguyên tắc 9–12 ở trên.
- **⚠️ G2a phải chạy lại:** `docs/reports/G2a_global_macro.md` chạy trên **level**, kết luận "GPRD coincident, không leading" **KHÔNG có hiệu lực** (nguyên tắc 9). Chuỗi level autocorrelated → "coincident" là kết quả mặc định. Chưa kết luận được GO/NO-GO tầng 2 cho tới khi chạy lại với innovation.
- **Tiếp theo — G2.0 feature foundation** (chặn mọi thứ sau): module xây `LEVEL / PERSISTENT / INNOVATION / JUMP / GPT_INNOVATION / GPA_SURPRISE`, rolling, no leakage. Rồi mới G2a (chạy lại, innovation) → G2b (daily: GPRD only; monthly: +GPRC_VNM) → G2c. Tất cả 🔬 research, ra report trước khi service hóa.
- **Chưa làm (nợ từ `docs/09` §5):** G0 research governance (hypothesis registry, holdout policy); cập nhật `docs/05_build_order.md` + `docs/06` cho khớp v2.

## Dữ liệu đã có sẵn (trong `data/` khi user cung cấp)

- `data_gpr_daily_recent.xls`: GPRD/GPRD_ACT/GPRD_THREAT daily, 1985 → 2026-06-29. DÙNG ĐƯỢC NGAY.
- `data_gpr_export_202607.xls` (bản 44 nước, ĐÃ CÓ): 1518 dòng × 115 cột, monthly 1900 → 2026-06. Chứa 44 cột `GPRC_*` (recent 1985+) + 44 cột `GPRHC_*` (historical 1900+), gồm cả `GPRC_VNM` và `GPRHC_VNM`. Cột dictionary: `var_name`/`var_label`.

### Lưu ý phân phối GPRC_VNM (quan trọng cho econometrics)
- GPRC_VNM: mean ≈ 0.05, std ≈ 0.05, **lệch phải mạnh** (đa số tháng ~0, thỉnh thoảng spike). Đặc tính chung của country-GPR nước nhỏ.
- **BẮT BUỘC dùng log(1+GPR) hoặc chuẩn hóa** khi đưa vào hồi quy — không dùng giá trị thô, nếu không vài spike sẽ chi phối toàn bộ ước lượng.
- Narrative check đã pass: GPRHC_VNM đỉnh 1968-02 (Tết Mậu Thân), 1972-04/05 (Easter Offensive); GPRC_VNM giai đoạn 2018+ đỉnh rơi vào 2026-03/04/05 và 2025-04 (căng thẳng thuế quan Mỹ-Việt).

## Lệnh hay dùng

Môi trường: `.venv/` ở repo root, Python 3.12, `gpr_engine` đã cài editable (import thẳng từ `src/`, không cần `pip install -e` lại).

```bash
pytest                                   # toàn bộ (32 test, ~90s)
pytest tests/econ/test_tier3_country.py  # 1 file
pytest tests/econ/test_tier3_country.py::test_ten_test -x   # 1 test, dừng ngay khi fail
ruff check .                             # lint (hiện có 7 lỗi E702/E401 sẵn — không phải do bạn)
ruff check . --fix
```

**Research runner (G2a, offline — không cần PostgreSQL):**

```bash
python scripts/run_tier2.py                              # shock=zscore LEVEL -> tự đánh dấu INELIGIBLE
python scripts/run_tier2.py --shock-method innovation    # cần G2.0 (docs/10 D2) làm trước
python scripts/run_tier2.py --refresh --horizon 20       # --refresh = kéo lại FRED, bỏ cache
```

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

**10/24 module là stub `raise NotImplementedError` ngay khi import** — chưa viết, không phải hỏng. Import chúng là crash. Đã thực thi: `ingest/*` (3), `econometrics/{dataset, data_files, local_projection, tier2_global_macro, tier3_country}`. Còn stub: `econometrics/{surprise, ladder, panel_var, tvp_var}`, `indices/*` (3), `backtest/*` (2), `scoring/statement_scorer`.

Cascade 3 tầng (nguyên tắc #8) ánh xạ thẳng vào cây thư mục — đây là trục kiến trúc chính:

- `econometrics/tier2_global_macro.py` — **tầng 1–2, ENGINE generic**: shock → Oil/DXY/VIX/US10Y. Ước lượng 1 lần, country-agnostic.
- `econometrics/tier3_country.py` — **tầng 3, PARAMS từng nước**: tách BA hệ số `β` (global-direct) / `θ` (indirect, tính bằng **tích chập** qua horizon) / `λ` (domestic-direct, từ `GPR^{c,⊥}` đã orthogonalize). Hệ số đọc từ `config/params/<country>.yaml`, không điền tay. Đóng góp kênh dùng Shapley/LMG.
- `econometrics/local_projection.py` — LP dùng chung cho cả hai tầng.

**Hai đường nạp dữ liệu song song, cố ý:**

- `dataset.py` — đường **production**, đọc `ext_series` từ PostgreSQL, point-in-time qua `load_series(..., as_of=...)`.
- `data_files.py` — đường **research offline**, đọc file + FRED. Dùng lại đúng transform của `dataset.py` (`log1p_gpr`, `transform_global_macro`) — khác I/O, **không lặp lại quy ước biến đổi**. Thêm transform mới thì sửa ở `dataset.py`, không fork sang đây.

Quy ước transform (docs/07 §0), sai là hỏng ước lượng: country-GPR → `log(1+GPR)`; GPRD daily global → **z-score, KHÔNG log1p** (log1p ép 370→5.9, làm phẳng spike khủng hoảng); Oil/DXY → `Δln`; VIX → giữ level; US10Y → sai phân.

Gate là **người quyết, không phải máy**: `run_tier2.gate_checklist` xuất verdict + mục Human review; run trên level tự gắn `INELIGIBLE` theo nguyên tắc #9.

## Cách làm việc trong repo này

- Đọc `docs/` theo thứ tự số trước khi code module tương ứng.
- Mỗi module có test đi kèm trong `tests/`. Viết test trước cho phần công thức (econometrics, indices).
- Notebook khám phá đặt trong `notebooks/`, không import ngược vào production code.
- Commit nhỏ, message rõ. Không refactor lan man ngoài scope task đang làm.
- Khi bí về thiết kế: hỏi lại, đừng tự quyết định kiến trúc lớn.
