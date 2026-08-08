# 11 — BUILD SPEC (Python)

**Phiên bản:** 1.0 — 2026-08-03
**Vai trò:** bản đồ code cho `docs/10_master_plan.md`. Doc 10 nói *làm gì*; doc này nói *code ở đâu, hàm gì, thứ tự nào*.
**Nguyên tắc:** repo hiện là research repo. Biến thành product **không phải viết lại** — mà là tách hai đường và thêm tầng serving.

---

## 1. QUYẾT ĐỊNH KIẾN TRÚC GỐC

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

Ba lợi ích: (1) request path không đụng statsmodels; (2) mọi nhận định truy được về đúng một `params_version`; (3) đổi mô hình = publish artifact mới, không deploy lại service.

**Ràng buộc bắt buộc:** online **không bao giờ** fit gì. Nếu online cần một con số không có trong artifact → đó là bug thiết kế, không phải lý do gọi `.fit()`.

---

## 2. LAYOUT

```
src/gpr_engine/
├── data/                    # ingest — offline + nightly
│   ├── sources/
│   │   ├── ai_gpr.py        # ★ MỚI — headline + 5 subindices
│   │   ├── gpr_legacy.py    # GPR gốc C-I (proxy thứ 2)
│   │   ├── fred.py          # oil/dxy/vix/us10y/freight/real macro
│   │   ├── uncertainty.py   # EPU, WUI
│   │   └── markets.py       # VNINDEX ← blocker
│   ├── registry.py          # ★ ghim vintage, hash, data_version
│   ├── dataset.py           # ✓ có
│   └── panel.py             # ✓ build_monthly_panel / daily
│
├── econometrics/            # offline
│   ├── shocks.py            # ✓ + decompose() ★
│   ├── local_projection.py  # ✓ lag_augmented, sup-t, quantile
│   ├── tier2.py             # ✓ + chiều component/channel/τ
│   ├── tier3.py             # ✓ + cumulative k-day
│   ├── panel_var.py         # 🔴 block-exo + Granger
│   ├── measurement_error.py # ★ MỚI — IV / common factor
│   └── analogue.py          # ★ MỚI — k-NN episode
│
├── scoring/                 # online + offline backfill
│   ├── client.py            # ★ LLM client: temp=0, JSON strict, retry, cache
│   ├── tier_a.py            # ★ replication AI-GPR (prompt Appendix A.6)
│   ├── tier_b.py            # ★ rubric ±1.0 (docs/00 §2)
│   └── audit.py             # ★ Krippendorff α, gold set
│
├── indices/
│   ├── aggregate.py         # ★ Σ S_it / A_t, mẫu số chung
│   ├── s_gpr.py             # 🔴 chỉ số chân B
│   └── ladder.py            # 🔴 escalation state machine
│
├── params/                  # ★ MỚI — cầu nối offline↔online
│   ├── artifact.py          # ParamsArtifact: load/save/validate/version
│   └── schema.py            # pydantic
│
├── assess/                  # ★ MỚI — online, lõi sản phẩm
│   ├── trigger.py           # khi nào ra card/brief
│   ├── measurement.py       # → MeasurementCard
│   ├── transmission.py      # tra artifact, KHÔNG fit
│   ├── compose.py           # LLM narrate
│   └── guard.py             # ★ P1 — chặn số không khớp payload
│
├── serving/                 # ★ MỚI
│   ├── api.py               # FastAPI
│   ├── workers.py           # collector poll + scoring queue
│   └── events.py            # Kafka producer
│
└── track_record/
    └── scoring.py           # ★ CRPS, Brier, reliability

scripts/     run_ingest.py · run_tier2.py · run_tier3.py · publish_params.py · backfill_scores.py
config/      sources.yaml · params/vn.yaml · prompts/{tier_a,tier_b}.yaml · registry.yaml
tests/       econ/ · scoring/ · assess/ · integration/
```

`✓` có · `🔴` stub · `★` cần viết

---

## 3. INTERFACE CHÍNH

Bốn chữ ký này quyết định phần còn lại. Chốt trước khi code.

```python
# params/schema.py
class Tier2Params(BaseModel):
    horizon: int; component: Literal["persistent","shock"]
    channel: str; outcome: str; tau: float | None      # None = OLS
    beta: float; se: float; ci_lo: float; ci_hi: float  # sup-t band

class ParamsArtifact(BaseModel):
    version: str            # "2026-08-a"
    data_version: str       # hash mọi input vintage
    git_commit: str
    fitted_at: datetime
    tier2: list[Tier2Params]
    tier3: dict[str, Tier3Params]     # country → β/θ/λ
    percentiles: dict[str, list[float]]  # hiệu chuẩn JUMP/ngưỡng
    claim_ceiling: Literal["measurement","association","predictive"]

    def lookup(self, *, channel, outcome, horizon, tau=None) -> Tier2Params | None:
        """None ⇒ chưa ước lượng ⇒ assess KHÔNG nói độ lớn. Không nội suy."""
```

```python
# scoring/tier_a.py  — replication, so được với chuỗi công bố
def score_article(text: str, *, title: str, date: date) -> ArticleScore:
    """0–1 đơn cực. Prompt Appendix A.6 nguyên văn. temp=0, JSON strict, cắt 2000 ký tự."""

# scoring/tier_b.py  — của mình, phát ngôn sơ cấp
def score_statement(text: str, *, actor: str, published_at: datetime) -> StatementScore:
    """±1.0 lưỡng cực + commitment/specificity/actor_weight. Chấm VĂN BẢN, không chấm hậu quả."""
```

```python
# assess/transmission.py
def assess(scores: StatementScore | ArticleScore,
           state: IndexState,
           artifact: ParamsArtifact) -> TransmissionView:
    """Tra artifact. Không fit, không nội suy, không đoán.
    artifact.lookup() trả None → TransmissionView.magnitude = None
    → compose() viết 'chưa ước lượng' thay vì con số."""
```

```python
# assess/guard.py
def enforce(narrative: str, payload: dict) -> str:
    """Mọi số trong narrative phải khớp một trường payload.
    Không khớp → raise GuardViolation. CHẶN, không cảnh báo."""
```

---

## 4. THỨ TỰ BUILD

### P1 — Offline hoàn chỉnh, sinh artifact đầu tiên (2–3 tuần)

| # | Việc | File |
|---|---|---|
| 1 | `load_ai_gpr()` + 5 subindices + ghim vintage | `data/sources/ai_gpr.py`, `data/registry.py` |
| 2 | `decompose(series, p) -> (persistent, shock)` | `econometrics/shocks.py` |
| 3 | Hiệu chuẩn lại phân vị/JUMP trên AI-GPR | `econometrics/shocks.py` |
| 4 | tier2 thêm chiều `component × channel × τ` | `econometrics/tier2.py` |
| 5 | IV / common factor (GPR gốc làm proxy 2) | `econometrics/measurement_error.py` |
| 6 | `run_tier2.py` chạy 3 bản → bảng γ | `scripts/` |
| 7 | cascade tier3 nước pilot (PL/CL), nhãn PLUMBING | `scripts/run_tier3.py` |
| 8 | `ParamsArtifact` + `publish_params.py` | `params/` |

**Done khi:** `params/v2026-08-a/` tồn tại, `lookup()` trả ra số thật, `validate()` pass.

### P2 — Scoring (4–5 tuần)

| # | Việc | File |
|---|---|---|
| 9 | LLM client: temp=0, JSON strict, retry, cache theo hash | `scoring/client.py` |
| 10 | `tier_a.py` + prompt yaml (Appendix A.6 nguyên văn) | `scoring/`, `config/prompts/` |
| 11 | `tier_b.py` + rubric docs/00 | `scoring/` |
| 12 | Collector 2 nguồn + dedup | `serving/workers.py` |
| 13 | `aggregate.py` (Σ/A_t), `s_gpr.py`, `ladder.py` | `indices/` |
| 14 | `audit.py` + gold set → α ≥ 0.6 | `scoring/` |

**Done khi:** phát ngôn thật → `StatementScore` < 10s; α ≥ 0.6.

### P3 — Online + sản phẩm (4 tuần)

| # | Việc | File |
|---|---|---|
| 15 | `analogue.py` (k-NN, n<5 im lặng, liệt kê episode) | `econometrics/` |
| 16 | `trigger.py` · `measurement.py` · `transmission.py` | `assess/` |
| 17 | `guard.py` + test đối kháng | `assess/` |
| 18 | `compose.py` (LLM narrate từ payload) | `assess/` |
| 19 | FastAPI + Kafka + workers | `serving/` |
| 20 | `track_record/scoring.py` (CRPS/Brier) | |
| 21 | VNINDEX → tier3 VN → artifact có `tier3["VN"]` | `data/sources/markets.py` |

**Done khi:** tin 14:07 → card 14:10; brief cuối tháng có γ thật.

---

## 5. LƯU TRỮ

| Kho | Dùng cho |
|---|---|
| **PostgreSQL** | `statements`, `statement_scores`, `article_scores`, `index_daily`, `cards`, `briefs`, `track_record` |
| **Parquet** (`params/<version>/`) | artifact — immutable, không sửa tại chỗ |
| **Redis** | ladder state, cache điểm theo hash, rate-limit |
| **Kafka** | topic `gpr.cards`, `gpr.briefs` → BeaverX agents |

Bảng điểm **bắt buộc** có `model_version`, `prompt_version`, `rubric_version`, `scored_at`, `content_hash` — thiếu là mất tái lập.

---

## 6. TEST

| Tầng | Nội dung |
|---|---|
| unit | công thức, transform, decompose, aggregate — không gọi mạng |
| golden | 50 phát ngôn đã chấm tay; regression khi đổi prompt/model |
| **guard** | **đối kháng**: narrative chứa số không có trong payload → phải raise |
| contract | `assess()` với `artifact.lookup() → None` phải trả `magnitude=None`, **không** đoán |
| integration | ingest → panel → tier2 → artifact → assess, dữ liệu nhỏ |
| no-fit | quét import: `assess/`, `serving/` **cấm** import statsmodels/sklearn.fit |

Test cuối là ràng buộc kiến trúc §1 viết thành code — nó chặn đúng thứ dễ trôi nhất khi vội.

---

## 7. HAI CẠM BẪY ĐÃ GẶP TRONG REPO NÀY

**Số hard-code trong report.** Đã xảy ra thật (narrative ghi "1.8×" trong khi hai trường tính được cho 2.77×). `guard.enforce()` phải áp cho **cả script research**, không chỉ sản phẩm.

**Đổi default âm thầm.** Đổi `shock_method` mặc định làm mọi report cũ không tái lập từ HEAD. Mọi thay đổi default → bump `data_version` hoặc `params.version`, và gắn `pipeline_note` vào report cũ.

---

## 8. TUẦN NÀY

```
1. data/sources/ai_gpr.py      — load + vintage pin
2. data/registry.py            — data_version phủ mọi nguồn
3. shocks.decompose()          — persistent/shock, có test
4. tier2 thêm chiều component  — chạy 1a
```

Bốn việc này không phụ thuộc quyết định nào đang treo ở doc 10 §7.