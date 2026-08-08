# 18 — BUILD SPEC (Python), bản đã đối chiếu code

**File:** `docs/18_build_spec.md` · **Phiên bản:** 1.1 — 2026-08-08
**Thay thế:** `docs/archive/18_build_spec_v1.0.md` (bản v1.0 của user, commit `1ef98a8` trên main, tên file cũ gõ nhầm `18_buid_spec.md`).
**Vai trò:** bản đồ code cho `docs/17_master_plan.md`. Master plan nói *làm gì*; doc này nói *code ở đâu, hàm gì, thứ tự nào*.
**⚠️ Tiêu đề trong v1.0 ghi "11 — BUILD SPEC" nhưng `docs/11_product_plan.md` là doc KHÁC** — code có ~15 chỗ trích dẫn "docs/11 §5.3", "docs/11 §6" (`analogue.py`, `panel_var.py`, `composer.py`, `guard.py`, `data_files.py`) trỏ về doc cũ đó, không phải doc này. Khi archive `11_product_plan.md` phải cập nhật các tham chiếu đó cùng commit.

> **Kết luận rà soát trong một câu:** §1 (tách offline/online bằng artifact) là **đóng góp lớn nhất và đúng** — nó vá một khớp nối đang lỏng thật trong code. §2 (layout) **đắt hơn giá trị nó mang lại** dưới dạng đổi tên, vì ~11 module bị đánh dấu "cần viết/stub" **đã tồn tại và đã chạy**. §3 (schema) có **một lỗi vi phạm chữ ký đã ký** phải sửa trước khi code. Chi tiết ở §E.

---

## 1. QUYẾT ĐỊNH KIẾN TRÚC GỐC — GIỮ NGUYÊN, ĐỒNG Ý HOÀN TOÀN

> **Sản phẩm KHÔNG chạy hồi quy lúc nhận request.** Nó nạp một artifact tham số đã fit, có version.

```
   OFFLINE (research, chạy tay/cron tháng)        ARTIFACT           ONLINE (serving, realtime)
┌────────────────────────────────────┐      ┌──────────────┐    ┌──────────────────────────┐
│ ingest → panel → shocks → LP       │─────▶│ params/      │───▶│ scorer → indices →       │
│ → tier2 (γ) → tier3 (β/θ/λ)        │      │  v2026-08/   │    │ trigger → assess → API   │
│ → report + gate                    │      │  *.parquet   │    │                          │
└────────────────────────────────────┘      │  meta.json   │    └──────────────────────────┘
        chậm, đắt, có governance            └──────────────┘         nhanh, rẻ, không có
                                             immutable                bậc tự do thống kê
```

**Vì sao đây là phần đáng giá nhất của doc:** khớp nối hiện tại đang lỏng thật, không phải rủi ro giả định —

- `pipeline/gamma_lookup.py::load_published_gamma()` đọc **file mới nhất khớp glob** trong `docs/reports/data/t2_full_holm_*.csv`. Nhận định sinh hôm nay và nhận định sinh tuần sau **không truy được về cùng một bộ tham số** nếu ai đó chạy lại `run_t2_full.py` ở giữa. `params_version` immutable xóa hẳn lớp lỗi này.
- Cùng hàm đó, với `panel=None` (mặc định trong pipeline theo từng tin, vì `build_monthly_panel` kéo FRED — quá nặng cho một request) trả `standardized = beta`, **không chuẩn hóa**. Nhưng `DEC-2026-08-03-dual-component` **bắt buộc** báo cáo chuẩn hóa. → Artifact phải mang sẵn `sd(shock)` (hoặc thẳng `beta_standardized`) để online không phải dựng lại panel mới nói đúng. Đây là lý do kỹ thuật thứ hai, độc lập, cho §1.

**Ràng buộc bắt buộc:** online **không bao giờ** fit gì. Nếu online cần một con số không có trong artifact → đó là bug thiết kế, không phải lý do gọi `.fit()`.

**Một điểm phải nói rõ, nếu không luật trên sẽ bị vi phạm trong im lặng:** đường online hiện tại **có tính toán thống kê** — `process_news_item_live` gọi `indices/s_gpr.expanding_percentile` và chuỗi JUMP rolling để nuôi `econometrics/ladder`. Nó không gọi `statsmodels.fit()` nên **bài test quét import của §6 sẽ PASS mà vẫn để lọt**. Phân định:

| Việc online | Cho phép? | Lý do |
|---|---|---|
| Ước lượng tham số (LP, AR, quantile) | ❌ cấm | §1 |
| Tính phân vị **so với ngưỡng lấy từ artifact** | ✅ được | Ngưỡng là tham số; so sánh không phải ước lượng. Đây là lý do trường `percentiles` trong schema tồn tại — dùng nó, đừng tính lại phân vị từ toàn bộ lịch sử |
| Tính `expanding_percentile` trên toàn lịch sử tại request-time | ⚠️ chỉ khi artifact chưa có ngưỡng | Chậm và **kết quả đổi theo lịch sử nạp được** → không tái lập |

→ Test §6 cần thêm một mục ngoài quét import: kiểm `assess/` lấy ngưỡng từ `artifact.percentiles`, không tự tính.

---

## 2. LAYOUT — ĐỀ XUẤT SỬA: THÊM, ĐỪNG ĐỔI TÊN

Layout v1.0 gọn hơn thật. Nhưng bảng dưới là đối chiếu từng dòng với repo — **11 mục bị đánh nhãn sai**, phần lớn là "★ cần viết" cho thứ đã chạy và có test:

| v1.0 ghi | Thực tế trong repo | Trạng thái thật |
|---|---|---|
| `data/sources/ai_gpr.py` ★ MỚI | `econometrics/data_files.py` (6 loader + `ai_gpr_vintage()`) + `ingest/ai_gpr.py` (12 chuỗi → `ext_series`) | ✅ **đã xong 2026-08-05** |
| `econometrics/shocks.decompose()` ★ | `shocks.delta_decomposition()` — ANTICIPATED+SURPRISE, đồng nhất thức, có test khóa | ✅ **đã xong, đã ký** |
| `econometrics/analogue.py` ★ MỚI | `econometrics/analogue.py` — k-NN, n<5 raise, IQR đổi dấu, `available_at ≤ t` trong retrieval | ✅ **đã xong (M5)** |
| `scoring/client.py` ★ | `scoring/statement_scorer.py` — `LLMClient` tiêm vào, JSON strict, cache hash 5 trục | ✅ đã có |
| `scoring/tier_b.py` ★ | cùng file trên — rubric ±1.0 chính là tầng B | ✅ đã có |
| `assess/guard.py` ★ | `reporting/guard.py` — chạy **runtime**, `NarrativeBuilder.render()` là cửa duy nhất | ✅ đã có |
| `assess/compose.py` ★ | `reporting/composer.py` — card + brief + `compose_vn_note` + `assert_claim_ceiling` | ✅ đã có |
| `assess/transmission.py` ★ | `pipeline/gamma_lookup.py` + `pipeline/vn_exposure.py` | ✅ đã có (nhưng đọc file, chưa đọc artifact — xem §1) |
| `serving/events.py` + `workers.py` ★ | `service/kafka_io.py` + `scripts/run_news_service.py` | ✅ đã có |
| `indices/s_gpr.py` 🔴 stub | đã thực thi 2026-08-02 (công thức docs/00 §2.5, strict `<`) | ✅ **không phải stub** |
| `indices/ladder.py` 🔴 stub | `econometrics/ladder.py` + `config/ladder_v1.yaml` đã thực thi | ✅ **không phải stub** |
| `econometrics/panel_var.py` 🔴 stub | `granger_block_test()` đã thực thi | ✅ **không phải stub** |
| — (không nhắc) | **Stub thật**: `econometrics/{surprise,tvp_var}`, `indices/{builder,divergence}`, `backtest/*` — raise ngay khi import | 🔴 6 module |
| `serving/api.py` ★ | không có FastAPI ở đâu trong repo | 🔴 **thiếu thật** |
| `params/` ★ | không có | 🔴 **thiếu thật, ưu tiên 1** |
| `econometrics/measurement_error.py` ★ | không có | 🔴 thiếu thật (nhưng xuống robustness — `docs/17_master_plan.md` §3.1) |
| `scoring/tier_a.py` ★ | không có (tầng A replication chưa làm) | 🔴 thiếu thật |
| `scoring/audit.py` ★ | không có | 🔴 thiếu thật |
| `indices/aggregate.py` ★ | không có (mẫu số chung $A_t$) | 🔴 thiếu thật |
| `track_record/scoring.py` ★ | không có (`docs/reports/data/track_record.jsonl` có file, chưa có code chấm) | 🔴 thiếu thật |
| `data/registry.py` ★ | vintage rải rác: `ai_gpr_vintage()`, `freight_vintage()`, `real_macro_vintage()`, `benchmark_vintage()` | 🟡 có mảnh, **chưa có `data_version` phủ mọi nguồn** |

**Đề xuất:** giữ §1/§3 nguyên vẹn, nhưng **layout đi theo hai bước, không đổi tên trong bước một**:

- **Bước 1 (đi cùng P1):** chỉ **thêm** `params/` và `assess/`. `assess/` là lớp mỏng orchestration gọi lại `reporting/` + `pipeline/` đang chạy, không copy logic. `serving/api.py` thêm mới cạnh `service/` đang có.
- **Bước 2 (sau khi artifact chạy, một commit cơ học riêng):** đổi tên `tier2_global_macro.py→tier2.py`, `data_files.py→data/sources/*`, gộp `reporting/`+`pipeline/`→`assess/`, `service/`→`serving/`. **Không đổi một dòng logic nào trong commit đó**, để diff đọc được và 344 test là lưới an toàn.

Lý do không gộp hai bước: `CLAUDE.md` §"Bản đồ code" là ngữ cảnh chính của mọi phiên làm việc và trỏ theo đường dẫn hiện tại; đổi tên cùng lúc với thêm tính năng là lúc dễ mất nhất những cảnh báo đắt tiền đã ghi trong docstring (`lag_augmented` ép `macro_lags=0`, strict `<` của `expanding_percentile`, convolution của `mediation_analysis`).

---

## 3. INTERFACE CHÍNH — MỘT LỖI PHẢI SỬA TRƯỚC KHI CODE

```python
# params/schema.py
class Tier2Params(BaseModel):
    horizon: int
    component: Literal["anticipated", "surprise"]   # ⚠️ KHÔNG PHẢI ["persistent","shock"]
    shock_measure: str          # 'AIGPR' | 'GPRD' | 'GPRD_ACT'... — chuỗi nào làm shock
    shock_variant: Literal["pooled", "act", "threat"]      # biến thể GPRD
    transmission_channel: Literal["energy","trade","financial","military"] | None
    outcome: str
    tau: float | None           # None = OLS
    inference: Literal["hac", "lag_augmented"]   # cổng eligibility phụ thuộc trường này
    beta: float
    beta_standardized: float    # β × sd(regressor) — BẮT BUỘC, xem §1
    sd_regressor: float
    se: float
    ci_lo: float; ci_hi: float
    ci_kind: Literal["pointwise", "supt"]        # sup-t KHÔNG dùng được với quantile
    p_holm: float | None        # sau Holm trong họ outcome
    family: str                 # asset_price | real_macro | physical
    n_obs: int
    converged: bool             # QuantReg IRLS — 386/6000 hàng T2-full là False
```

**Ba sửa đổi, theo thứ tự quan trọng:**

1. 🔴 **`component: Literal["persistent","shock"]` vi phạm chữ ký đã ký.** `DEC-2026-08-03-dual-component` ghi điều kiện: *"β_ANTICIPATED phải gọi là 'phản ứng với thành phần đã dự báo được'. Gọi là 'tác động của cú sốc' vi phạm #9"*, và cổng máy `shock_axis.check_component_labelling` **raise** đúng lỗi này. Hai lý do cụ thể ngoài chuyện tuân thủ:
   - "persistent" là tên của một object KHÁC đã tồn tại: `shocks.persistent_ar()` = Ê[LEVEL] (gần nghiệm đơn vị). Thành phần trong spec kép là fitted của AR **trên sai phân**. Đặt trùng tên hai thứ khác nhau trong wire format là lỗi sẽ sống rất lâu.
   - Gọi thành phần thứ hai là "shock" và thành phần thứ nhất là "persistent" ngầm khẳng định cái sau không phải cú sốc — đúng cách đọc mà #9 cấm.
   → **Dùng `anticipated` / `surprise`**, khớp `delta_decomposition` đã có.
2. 🔴 **`channel: str` gộp hai trục đã gây nhầm trong repo này.** `pooled/act/threat` là **biến thể GPRD dùng làm shock**; `energy/trade/financial/military` là **kênh truyền dẫn**. `gamma_lookup.commitment_to_gamma_channel` hiện là proxy tường minh giữa hai trục và mọi Model Brief đều phải in `sample_caveat` về việc đó. Một trường `channel: str` sẽ xóa luôn cảnh báo đó khỏi wire format → tách hai trường như trên.
3. 🟡 **`ci_lo/ci_hi  # sup-t band` không đúng cho mọi hàng.** `simultaneous=True` + `method="quantile"` raise `NotImplementedError` (hàm ảnh hưởng QuantReg chưa làm). Hàng τ **không thể** có dải sup-t → thêm `ci_kind` để `assess/` không đọc nhầm pointwise thành đồng thời. Cùng lý do, `converged` phải đi theo hàng, nếu không số không hội tụ chảy thẳng ra sản phẩm (đã xảy ra ở T2-full, được cứu bằng ký hiệu `‡` trong bảng in).

```python
class ParamsArtifact(BaseModel):
    version: str            # "2026-08-a"
    data_version: str       # hash mọi input vintage
    git_commit: str
    fitted_at: datetime
    sample: tuple[date, date]          # thêm: mẫu ước lượng, để assess kiểm tiền lệ
    tier2: list[Tier2Params]
    tier3: dict[str, Tier3Params]      # country → β/θ/λ
    percentiles: dict[str, list[float]]
    claim_ceiling: dict[str, Literal["measurement","association","predictive"]]
    # ↑ theo TỪNG tầng, không phải một giá trị: tier2 = 'predictive, chưa xác nhận
    #   holdout' trong khi tier3['VN'] = 'association' cho tới khi vn.yaml có fitted:

    def lookup(self, *, outcome, horizon, shock_measure, shock_variant,
               component, tau=None, transmission_channel=None) -> Tier2Params | None:
        """None ⇒ chưa ước lượng ⇒ assess KHÔNG nói độ lớn. Không nội suy."""
```

`tier3` **phải cho phép rỗng**: `config/params/vn.yaml` chưa có mục `fitted:`, nên artifact đầu tiên sẽ có `tier3 = {}`. `assess` gặp rỗng → `magnitude=None` → composer viết định tính. Đó là hành vi đúng (nguyên tắc #4), không phải lỗi validate.

```python
# scoring/tier_a.py — replication, so được với chuỗi công bố
def score_article(text: str, *, title: str, date: date) -> ArticleScore:
    """0–1 đơn cực. Prompt Appendix A.6 nguyên văn. JSON strict, cắt 2000 ký tự."""

# scoring/tier_b.py — của mình, phát ngôn sơ cấp
def score_statement(text: str, *, actor: str, published_at: datetime) -> StatementScore:
    """±1.0 lưỡng cực + commitment/specificity/actor_weight. Chấm VĂN BẢN, không chấm hậu quả."""
```
⚠️ v1.0 ghi `temp=0`; code hiện là `DEFAULT_TEMPERATURE = 0.1`. Temperature nằm trong khóa cache và 5 trục version → chốt một giá trị (doc 17 §7 #8) rồi sửa **cả hai nơi trong cùng commit**; chọn 0 thì phải backfill lại điểm đã chấm. `score_statement` cũng **bắt buộc** nhận `training_cutoff` (cổng contamination, `docs/14` §3.1) — chữ ký v1.0 thiếu.

```python
# assess/transmission.py
def assess(scores, state: IndexState, artifact: ParamsArtifact) -> TransmissionView:
    """Tra artifact. Không fit, không nội suy, không đoán."""

# assess/guard.py
def enforce(narrative: str, payload: dict) -> str:
    """Mọi số trong narrative phải khớp một trường payload. Không khớp → raise."""
```
`enforce` đã tồn tại (`reporting/guard.py`) và **mạnh hơn** chữ ký này: nó chạy sau `NarrativeBuilder.render()` nên không thể quên gọi. Khi chuyển sang `assess/`, giữ nguyên tính chất "cửa duy nhất" — hạ xuống thành hàm gọi rời là mất chính thứ làm nó hiệu quả. Ba giới hạn đã biết của guard giữ nguyên và phải ghi lại chỗ mới: không kiểm số đúng/sai · không hiểu ngữ nghĩa · không bắt số bị bỏ sót.

---

## 4. THỨ TỰ BUILD (sửa theo trạng thái thật)

### P1 — Offline hoàn chỉnh, sinh artifact đầu tiên (2–3 tuần)

| # | Việc | File | Ghi chú so với v1.0 |
|---|---|---|---|
| 0 | **Sửa đường dẫn data** (`data/AI-GPRs/…`, `data/GPR index/… (1).xls` vs DEFAULT_*) | `econometrics/data_files.py` | **thêm mới** — hiện không script nào chạy được ngay |
| 1 | ~~`load_ai_gpr()` + 5 subindices + vintage~~ | — | ✅ **đã xong**, gạch |
| 2 | ~~`decompose()`~~ | — | ✅ **đã xong** (`delta_decomposition`) |
| 3 | Hiệu chuẩn phân vị/JUMP trên AI-GPR, **có xử lý zero-inflation** (`GPR_OIL` = 0 ở 31.8% ngày, theo vùng tới 99.7%) | `econometrics/shocks.py` | giữ, thêm ràng buộc |
| 3b | **Chạy lại E2 trên AI-GPR** | `scripts/run_e2_component_check.py` | **thêm mới** — quyết định cách đọc spec kép, xem `docs/17_master_plan.md` §A4 |
| 4 | Panel đổi được **nguồn shock** (GPR gốc ↔ AI-GPR) | `econometrics/data_files.py` | **thêm mới** — hiện hard-code file xls, không có tham số |
| 5 | tier2 trả **đủ hệ số** của spec đa regressor (`return_all=True` xuyên qua, `supt_c` riêng từng hệ số) | `econometrics/tier2_global_macro.py` | **thêm mới** — hiện chỉ trả hệ số của một `shock`, regressor thứ hai rơi vào `controls` và **bị vứt** |
| 6 | Cột ANTICIPATED/SURPRISE vào panel | `econometrics/data_files.py` | **thêm mới** — `components=True` hiện là act/threat, không phải cặp phân rã |
| 7 | IV / common factor | `econometrics/measurement_error.py` ★ | **xuống robustness** (`docs/17_master_plan.md` §3.1: corr monthly 0.853, không phải 0.69) |
| 8 | `run_t2_full.py` chạy 3 bản → bảng γ | `scripts/` | giữ |
| 9 | cascade tier3 nước pilot, nhãn PLUMBING | `scripts/run_tier3.py` | ⛔ **chốt nguồn WIG/IPSA trước** — `pilot_market_series_missing`, không có trên FRED |
| 10 | `ParamsArtifact` + `publish_params.py` | `params/` ★ | giữ — **hạng mục giá trị nhất của doc này** |
| 11 | `gamma_lookup` đọc **artifact**, không đọc glob file mới nhất | `pipeline/gamma_lookup.py` | **thêm mới** — nếu bỏ, §1 chỉ tồn tại trên giấy |

**Done khi:** `params/v2026-08-a/` tồn tại, `lookup()` trả số thật, `validate()` pass, **và** `gamma_lookup` không còn đọc `docs/reports/data/*.csv` theo glob.

### P2 — Scoring (4–5 tuần)

| # | Việc | Ghi chú |
|---|---|---|
| 12 | LLM client (temp chốt, JSON strict, retry, cache hash) | phần lớn **đã có** trong `statement_scorer.py`; việc thật là tách `client.py` + chốt temperature |
| 13 | `tier_a.py` + prompt yaml (Appendix A.6 nguyên văn) | 🔴 thiếu thật |
| 14 | `tier_b.py` + rubric docs/00 | **đã có** — việc là đổi tên/di chuyển |
| 15 | Collector 2 nguồn (Trump + MOFA CN, đã ký) + dedup | 🔴 thiếu thật |
| 16 | `aggregate.py` (Σ/A_t) · `s_gpr.py` · `ladder.py` | `s_gpr`/`ladder` **đã xong**; chỉ `aggregate.py` là mới. Ngưỡng S1/S3 vẫn chờ user |
| 17 | `audit.py` + gold set → α ≥ 0.6 | 🔴 thiếu thật; **chặn bởi người chấm thứ hai**, không phải bởi code |

### P3 — Online + sản phẩm (4 tuần)

| # | Việc | Ghi chú |
|---|---|---|
| 18 | `analogue.py` | ✅ **đã xong** — việc là nối vào pipeline (cần panel tháng, hiện để trống có chủ đích) |
| 19 | `trigger.py` · `measurement.py` · `transmission.py` | phần lớn đã có trong `pipeline/`; việc là chuyển sang đọc artifact |
| 20 | `guard.py` + test đối kháng | guard đã có; **test đối kháng là việc mới và đáng làm** |
| 21 | `compose.py` | ✅ đã có (`reporting/composer.py`) |
| 22 | **FastAPI** + Kafka + workers | Kafka đã có; **FastAPI là lỗ hổng thật, chưa có dòng nào** |
| 23 | `track_record/scoring.py` (CRPS/Brier) | 🔴 thiếu thật |
| 24 | VNINDEX → tier3 VN → `artifact.tier3["VN"]` | ⛔ VNINDEX **không phải blocker duy nhất**: country/bilateral là monthly (#10 cấm ffill) → track VN daily vẫn chặn. Xem `docs/17_master_plan.md` §A2 |

---

## 5. LƯU TRỮ

| Kho | Dùng cho |
|---|---|
| **PostgreSQL** | `statements`, `statement_scores`, `article_scores`, `index_daily`, `cards`, `briefs`, `track_record`, **`ladder_state`** |
| **Parquet** (`params/<version>/`) | artifact — immutable, không sửa tại chỗ |
| **Redis** | cache điểm theo hash, rate-limit, **bản sao nóng** của ladder state |
| **Kafka** | topic `gpr.cards`, `gpr.briefs` → BeaverX agents |

⚠️ **Sửa so với v1.0: ladder state KHÔNG chuyển sang Redis làm nguồn chân lý.** Bảng `ladder_state` đã có trong `sql/002_schema_serving.sql` với `config_version` — nó là **dữ liệu để tái lập một nhận định đã phát**, không phải cache. Mất Redis = mất khả năng trả lời "hôm đó vì sao ra state 3". Redis giữ bản nóng, Postgres là nguồn chân lý. (Ghi chú liên quan: `process_news_item_live` có cờ `ladder_computed` — chỉ ghi DB khi tính thành công thật, không ghi 0 giả. Giữ tính chất này khi thêm Redis.)

Bảng điểm **bắt buộc** có `model_version`, `prompt_version`, `rubric_version`, **`temperature`**, `scored_at`, `content_hash`. Thêm `temperature` vì nó đã nằm trong khóa cache 5 trục — thiếu ở DB thì DB và cache bất đồng.

⚠️ Đọc kèm: `ext_series`/`statement_scores` cho phép nhiều `data_version`/`model_version` cùng ngày/tin. Mọi truy vấn nuôi JUMP/S-GPR phải `DISTINCT ON` bản mới nhất — đã vá 2026-08-05, đừng viết lại query thiếu mệnh đề đó.

---

## 6. TEST

| Tầng | Nội dung |
|---|---|
| unit | công thức, transform, decompose, aggregate — không gọi mạng |
| golden | 50 phát ngôn đã chấm tay; regression khi đổi prompt/model |
| **guard** | **đối kháng**: narrative chứa số không có trong payload → phải raise |
| contract | `assess()` với `lookup() → None` phải trả `magnitude=None`, **không** đoán |
| integration | ingest → panel → tier2 → artifact → assess, dữ liệu nhỏ |
| no-fit | quét import: `assess/`, `serving/` **cấm** import statsmodels/sklearn |
| **no-recompute** ★ | `assess/` lấy ngưỡng từ `artifact.percentiles`, **không** tự tính phân vị trên toàn lịch sử (xem §1 — test quét import một mình không bắt được) |
| **labelling** ★ | `Tier2Params.component` chỉ nhận `anticipated`/`surprise`; narrative không được gọi `anticipated` là "cú sốc" — nối lại `shock_axis.check_component_labelling` |
| **governance** ★ | artifact publish ra phải có `git_commit` khớp HEAD sạch; `LOCKED_DECISION_IDS` không đổi mà `decisions:` đổi → đỏ (đã có `tests/test_registry_locked.py`) |

Ba test cuối là các quyết định của §1/§3 viết thành code. Test `no-fit` một mình **không đủ** — đó là điểm mù đã phân tích ở §1.

---

## 7. BA CẠM BẪY ĐÃ GẶP TRONG REPO NÀY

1. **Số hard-code trong report.** Đã xảy ra thật (narrative ghi "1.8×" trong khi hai trường tính được cho 2.77×). `guard.enforce()` áp cho **cả script research**, không chỉ sản phẩm.
2. **Đổi default âm thầm.** Đổi `shock_method` mặc định làm mọi report cũ không tái lập từ HEAD. Mọi thay đổi default → bump `data_version` hoặc `params.version`, gắn `pipeline_note` vào report cũ.
3. **So sánh hệ số khác thang đo.** ⭐ Cạm bẫy thứ ba, đã cắn hai lần: `LEVEL+JUMP` (registry `level_plus_jump_composition`) và persistent-vs-shock (E2: **48.9% ô đảo chiều** sau chuẩn hóa). Đây là lý do `beta_standardized` + `sd_regressor` là **trường bắt buộc** của artifact chứ không phải tùy chọn: nếu online phải tự chuẩn hóa thì sớm muộn sẽ có nơi quên.

---

## 8. TUẦN NÀY (sửa)

```
0. sửa đường dẫn data/                       — chặn mọi thứ khác
1. chạy lại E2 trên AI-GPR                   — quyết định cách đọc spec kép
2. params/schema.py + artifact.py            — chốt 4 chữ ký của §3 TRƯỚC khi code phần còn lại
3. tier2 return_all + cột ANTICIPATED/SURPRISE vào panel  — điều kiện để chạy 1a
```

⚠️ **Sửa khẳng định của v1.0** ("bốn việc này không phụ thuộc quyết định nào đang treo"): việc "tier2 thêm chiều component" **có** phụ thuộc `docs/17_master_plan.md` §7 #2 — chốt ô chính `SCA-01.primary_cell.shock` bằng spec kép là chốt **bằng thiết kế** chứ không bằng E1c-exo, và `DEC-2026-08-03-dual-component` ghi rõ đó là quyết định RIÊNG cần chữ ký mới. Code cứ viết được (nó chỉ thêm chiều báo cáo), nhưng **gắn nhãn ô nào là ô chính thì không** — làm trước là lặp lại đúng thứ mà cơ chế UNRESOLVED sinh ra để chặn.

---

# PHỤ LỤC §E — TÓM TẮT RÀ SOÁT v1.0

| Hạng mục | Đánh giá | Việc |
|---|---|---|
| §1 offline/online + artifact | ✅ **Đúng và giá trị nhất.** Vá khớp nối lỏng thật (glob file mới nhất + `standardized=beta` khi `panel=None`) | Giữ nguyên; thêm phân định "tính phân vị online" ở §1 |
| §2 layout | 🟡 **Nhãn sai 11 mục** (9 mục "★ cần viết"/"🔴 stub" đã chạy; 6 stub thật không được nhắc) | Thêm `params/`+`assess/`+`api.py` trước, đổi tên sau trong commit cơ học riêng |
| §3 `component: ["persistent","shock"]` | 🔴 **Vi phạm `DEC-2026-08-03-dual-component`** + trùng tên với `persistent_ar()` (object khác) | Đổi thành `["anticipated","surprise"]` |
| §3 `channel: str` | 🔴 Gộp hai trục đã gây nhầm (biến thể shock vs kênh truyền dẫn) | Tách `shock_variant` / `transmission_channel` |
| §3 `ci_lo/ci_hi # sup-t` | 🟡 Hàng quantile không thể có sup-t (`NotImplementedError`) | Thêm `ci_kind`, `converged`, `p_holm`, `family`, `n_obs`, `inference` |
| §3 `claim_ceiling` một giá trị | 🟡 tier2 và tier3['VN'] khác trần | Đổi thành dict theo tầng; `tier3` cho phép rỗng |
| §3 `score_statement` | 🟡 Thiếu `training_cutoff` (cổng contamination bắt buộc) | Thêm vào chữ ký |
| §4 P1 mục 1–2 | 🟡 Đã xong từ 2026-08-05 | Gạch, thay bằng 5 việc thật (đường dẫn, E2 lại, nguồn shock, return_all, cột phân rã) |
| §4 P1 mục 7 (pilot) | 🟡 Bị chặn bởi `pilot_market_series_missing` (WIG/IPSA không có trên FRED) | Chốt nguồn trước |
| §5 ladder state → Redis | 🔴 Mất khả năng tái lập nhận định đã phát | Postgres là nguồn chân lý, Redis là cache |
| §5 bảng điểm | 🟡 Thiếu `temperature` (đã nằm trong khóa cache) | Thêm cột |
| §6 test no-fit | 🟡 Có điểm mù: online tính `expanding_percentile` không import statsmodels vẫn lọt | Thêm test `no-recompute` + `labelling` + `governance` |
| §7 cạm bẫy | 🟡 Thiếu cái đã cắn hai lần: so hệ số khác thang đo | Thêm mục 3 |
| §8 "không phụ thuộc quyết định treo" | 🔴 Sai với mục 4 (chiều component ↔ chốt ô chính) | Viết code được, gắn nhãn ô chính thì không |
