# 15 — PIPELINE GLOBAL: TIN TỨC → CÔNG THỨC × LLM → NHẬN ĐỊNH VĨ MÔ

**Phiên bản:** 1.1 — 2026-08-02 (v1.0: 2026-07-21)
**Khác v1.0:** §3 + §5 cập nhật sau vòng đối chiếu văn bản ↔ **code thật** (2026-08-02). Ba thứ đổi: (i) M10 xong phần code, chỉ còn chữ ký; (ii) "thiếu guard sup-t×hac (1 dòng)" ở §3 là **đánh giá thấp** — nó là lỗi đúng/sai, và còn một lỗ im lặng thứ hai cùng khối; (iii) phát hiện M8/M9 **không với tới được** từ cascade → thêm §6 ghi các khoảng trống code chưa văn bản nào bắt.
**Vai trò:** bản tổng hợp kiến trúc cho deliverable chính **Global Macro Impact**. Không thêm quyết định mới — chỉ ghép các quyết định đã chốt rải rác ở docs/00, 11, 12, 14 và `g0` §7 thành MỘT đường chảy đọc được. Khi có mâu thuẫn, văn bản gốc thắng.
**Phạm vi:** global trước. Country Transmission (VN, β/θ/λ, khối chính sách) là tầng gắn thêm sau — docs/11 §5.5–5.7, docs/14 Phase 3e.

---

## 0. NGUYÊN TẮC PHÂN CÔNG — MỘT DÒNG

> **LLM đo và diễn đạt. Công thức truyền dẫn. Không bao giờ ngược lại.**

| | LLM làm | Công thức làm | LLM CẤM làm |
|---|---|---|---|
| Vào | lọc tin (encoder ~0.6), chấm cường độ ±1.0, phân loại kênh, actor | — | — |
| Giữa | — | shock, γ, phân phối, phân vị, ngưỡng đuôi, analogue k-NN | sinh số, chọn spec |
| Ra | viết narrative **từ payload đã tính** | mọi con số trong narrative | chấm gate, sửa số |

Guard P1 (chặn cứng số không khớp payload) đứng giữa "Ra" và người dùng. Tiền lệ lỗi đã có thật (1.8× vs 2.77×) — guard áp cho cả report nghiên cứu lẫn sản phẩm.

---

## 1. ĐƯỜNG CHẢY BỐN TẦNG

```
TIN/PHÁT NGÔN                 [tầng 1 — INGEST]
Trump · MOFA · Fed · WH   ─→  collector → dedup/cluster
GPRD nightly (t+1, chân A) ─→ hiệu chuẩn lịch sử 1985+
        │
        ▼                     [tầng 2 — ĐO LƯỜNG · lãnh địa LLM · claim=measurement]
encoder lọc → LLM chấm (temp 0.1, JSON strict):
  v ±1.0 · commitment · specificity · actor_w · channel∈{energy,trade,financial,military}
        │
        ├─→ S-GPR (pair/global) · ladder state · phân vị vs 40 năm
        ├─→ JUMP đuôi (aggregation=max cho cuối tuần)
        └─→ MEASUREMENT CARD (realtime, KHÔNG dự báo)
        │
        ▼                     [tầng 3 — TRUYỀN DẪN · lãnh địa công thức]
shock trục báo cáo {LEVEL(lag-aug) · INNOVATION · LEVEL+JUMP}
LP lag-augmented + HC1 · sup-t · quantile τ∈{.10,.25,.50,.75,.90} · số hạng J
tách kênh (ACT/THREAT → LLM channel khi chân B đủ)
battery: hệ số phải sống sót khi control EPU+WUI
Holm trong họ outcome pre-registered {asset_price · real_macro · physical}
        │
        └─→ BẢNG γ: kênh × outcome × τ × h (+ dải sup-t)
        │
        ▼                     [tầng 4 — NHẬN ĐỊNH · ghép + gắn nhãn claim]
trigger: J>0 · chuyển bậc ladder · phân vị ≥90 · im lặng kéo dài
  ├─ analogue k-NN (claim=association): n<5 im lặng, luôn liệt kê episode
  ├─ phân phối có điều kiện (claim=predictive, chưa xác nhận holdout):
  │    γ_τ → skewed-t → "trung vị ~0, đuôi trái dày lên" khi đúng là vậy
  └─ composer LLM + guard P1 → MODEL BRIEF (tháng + bản bất thường)
        │
        └─→ track record công khai (CRPS/Brier, model local pin cứng)
```

---

## 2. VÍ DỤ XUYÊN SUỐT — MỘT TIN ĐI HẾT BỐN TẦNG

*14:07 — Trump đăng: áp thuế bổ sung lên hàng Trung Quốc, hiệu lực 01/08.*

| Phút | Tầng | Ai tính | Cái gì |
|---|---|---|---|
| 14:07:41 | 1 | collector | bắt, dedup, `published_at` đến phút |
| 14:07:44 | 2 | encoder | p(geopolitical)=0.97 → qua |
| 14:07:52 | 2 | **LLM** | v=+0.92, commitment=announced_action, specificity=0.85, actor_w=1.0, **channel=trade** |
| 14:07:53 | 2 | công thức | S-GPR(US→CN) 7d: 2.1→4.8 (p94) · ladder S2→S4 · JUMP=0.62 vượt q95 |
| 14:08 | 2 | template | **MEASUREMENT CARD** phát — chỉ đo lường, ghi rõ "không phải dự báo" |
| +≤24h | 4 | công thức | JUMP vượt ngưỡng → kích bản bất thường: analogue 6 lần S2→S4 trục US-CN (trung vị+IQR, danh sách bấm xem được); tra **cột kênh trade** của bảng γ: τ=0.50 ≈ 0, τ=0.10 < 0 có ý nghĩa → "đuôi trái IP dày lên, trung vị không dịch" |
| +≤24h | 4 | **LLM** | viết narrative từ payload trên — guard P1 đối chiếu từng số |
| cuối tháng | 4 | công thức | brief định kỳ cập nhật; CRPS chấm brief cũ, công khai |

Mọi số trong hai văn bản phát ra đều truy về được một hàm và một `data_version`. LLM chạm vào đúng hai ô có chữ **LLM**.

---

## 3. TRẠNG THÁI TỪNG KHỐI (2026-07-21)

| Khối | Tầng | Trạng thái |
|---|---|---|
| GPRD ingest + panel tháng 5 kênh + real macro + battery EPU/WUI | 1 | ✅ |
| LP lag-aug + HC1 + sup-t + quantile (M8/M9) | 3 | ✅ — **nối vào cascade 2026-08-02**; hai lỗ im lặng đã bịt (§6.1) |
| Bội: Holm trong họ (M10) | 3 | ✅ `multiplicity.py`; **họ = B đã ký** 2026-08-02 (`DEC-2026-08-02-holm-family`) |
| **Bảng γ đầu tiên (1a)** | 3 | ✅ **ĐÃ CHẠY** 2026-08-02 → `docs/reports/T2_full_f2579b30928f.md`. Chờ **human review** |
| Scorer + S-GPR + ladder (chân B — MODULE, 2026-08-02) | 2 | ✅ code: `statement_scorer` (encoder→LLM, JSON strict, contamination §3.1.1 trong prompt, versioning đủ 5 trục) · `s_gpr` (công thức §2.5, 2 chiều không net, w(role)=INIT #7) · `ladder` V1 (`config/ladder_v1.yaml`) — test bằng fake LLM, chưa gọi API thật |
| Collector 2 nguồn + backfill + human audit (chân B — DATA) | 1–2 | ❌ Phase 2, chờ ký §6.1–6.2 + §7.2; cổng α≥0.6 + contamination §3.1 chưa chạy |
| **Analogue + composer + guard P1** | 4 | ✅ code 2026-08-03 — `econometrics/analogue.py` (k-NN, 4 ràng buộc §6 là cơ chế) · `reporting/guard.py` (P1 chạy **runtime**, không chỉ CI) · `reporting/composer.py` (card + brief, 3 trần claim) |
| Serving (FastAPI/Kafka) + track record CRPS/Brier | 4 | ❌ M7 + 3c |

**Thứ tự mở khóa:** ký §7.1/§6.6 (+ §6.2 runner) → **1a chạy, bảng γ tồn tại** → tầng 4 có nội dung để ghép ngay cả khi chân B chưa xong (trigger tạm bằng JUMP chân A) → chân B thay thế dần đầu vào realtime.

---

## 4. TRẦN CLAIM THEO TẦNG — IN TRÊN MỌI OUTPUT

| Tầng | Claim tối đa | Vì sao |
|---|---|---|
| 2 — đo lường | `measurement` | rubric + audit α≥0.6; backfill pre-cutoff chỉ mô tả (contamination §3.1) |
| 4 — analogue | `association` | event-study mô tả, không identification |
| 4 — phân phối | `predictive, chưa xác nhận holdout` | track tháng holdout rỗng theo cấu tạo (`g0` §2) |
| — giao dịch | **không tồn tại** | đã bỏ khỏi lộ trình |

---

## 5. ✅ ĐÃ KÝ 2026-08-02 — TẦNG 3 THÔNG

Bốn quyết định ký cùng ngày, **đúng khuyến nghị đã ghi sẵn** (không thêm quyết định mới). Bản chữ ký: `g0` §7.1/§7.2 + docs/14 §6. Khóa máy: `decisions:` trong registry + `test_signed_decisions_locked`.

| # | Quyết định | Chốt | Cổng máy |
|---|---|---|---|
| 1 | `g0` §7.1 SHOCK trục báo cáo | **A** | `shock_axis.gate_shock_eligibility` — LEVEL/LEVEL+JUMP eligible ⟺ `lag_augmented` |
| 2 | docs/14 §6.6 họ Holm | **B** | `multiplicity.PREREGISTERED_OUTCOME_FAMILIES` (4/3/1) + `test_holm_families_match_report_axis` |
| 3 | `g0` §7.2 cửa sổ chân B | **(i)+(ii)** | trần claim chân B v1 ghi trong `g0` §7.2 |
| 4 | docs/14 §6.1 + §6.3 | Trump + MOFA CN · bỏ tín hiệu giao dịch | — |
| ~~5~~ | ~~Guard `simultaneous ⇒ lag_augmented`~~ | xong | +2 lỗ im lặng khác (§6.1) |

**Điều kiện kèm của (1) đã được ghi vào `g0` §7.1 trước khi ký** — bản gốc phương án A chỉ nói "cho phép mọi thước đo khi report ghi cả ba"; ràng buộc `lag_augmented` chặt hơn và là thứ làm A không phá #9, nên nó phải nằm trong văn bản governance chứ không chỉ trong code.

**Còn mở: docs/14 §6.2 — người chấm mẫu thứ hai.** Cần một con người thật, không ủy quyền cho máy được. Đây là blocker Phase-2 duy nhất còn lại về nhân sự.

**→ Bảng γ đã tồn tại: `docs/reports/T2_full_f2579b30928f.md`.** Lần đầu pipeline này nói một điều về **thế giới** thay vì về chính nó. §7 tóm tắt.

---

## 7. BẢNG γ ĐẦU TIÊN — ĐỌC GÌ (2026-08-02, chờ human review)

Mẫu **231 tháng** (2007-02 → 2026-06), một mẫu duy nhất cho mọi ô. 3600 hàng γ, 432 kiểm định focal, 34 p thô <0.10, **15 sống sót Holm** (bản có battery: 9).

| Thước đo | Giá tài sản | Vĩ mô thực | Kênh vật lý |
|---|---|---|---|
| LEVEL | 0 | 1 | 1 |
| INNOVATION | 0 | 1 | 0 |
| LEVEL+JUMP | 0 | 4 | 2 |

Ba điều đáng chú ý — **diễn giải là việc của human review, đây chỉ là cái máy đọc được**:

1. **Ô đồng thuận cả ba thước đo: `GPR_ACT → IP, h=2, dấu âm`**, sống sót battery EPU. Đó là **cùng hiện tượng E0 replication** (C-I 2022: GPR→IP giảm ở h=1,2) nhưng trên mẫu khác, suy diễn khác (lag-augmented + HC1 thay HAC), và giờ tách được: **ACT chứ không phải THREAT**. Kết luận bền qua cách đo shock — đúng cái lý do chọn phương án A.
2. **Giá tài sản 0/4 ở cả ba thước đo.** Ngược hẳn G2a cũ (level-based, "VIX là kênh mạnh nhất"). Không mâu thuẫn: G2a cũ đã bị vô hiệu (#9 + gate confirmation-bias), chạy trên daily, không có battery, không hiệu chỉnh bội. Nhưng cần human review xem đây là **thông tin** (kênh tài chính price-in nhanh, không còn gì ở tần suất tháng) hay là **mất power** (n=231, Holm conservative trên 4 outcome tương quan mạnh).
3. **LEVEL+JUMP thắng về số ô (6 vs 2 vs 1).** ⚠️ **Không** được đọc là "LEVEL+JUMP là thước đo đúng" — `SCA-01.primary_cell.shock` vẫn UNRESOLVED, và registry đã ghi rằng trọng số LEVEL+JUMP hiện là **tai nạn thang đo** (`level_plus_jump_composition`). Chốt ô chính vẫn chờ E1c-exo + gold set.

---

## 6. KHOẢNG TRỐNG CODE — rà 2026-08-02, chưa văn bản nào bắt

### 6.1 Hai lỗ im lặng trong khối sup-t (ĐÃ SỬA)

§3 v1.0 ghi "thiếu guard sup-t×hac (1 dòng)". Đánh giá thấp — đó không phải guard chính sách mà là lỗi đúng/sai, và có hai cái chứ không một:

1. `simultaneous=True` + `inference="hac"` **chạy trót lọt** và trả `beta ± c·se_HAC`: hằng số `c` lấy từ ma trận hiệp phương sai EHW (hàm ảnh hưởng), độ rộng lấy từ SE HAC. Chính là lỗi "hai bộ sai số chuẩn trong một report" mà `test_supt_diagonal_matches_hc1` sinh ra để chặn — nó lọt được vì hai nguồn nằm ở hai dòng code khác nhau. Giờ **raise**.
2. `simultaneous=True` + `return_all=True` **tính hàm ảnh hưởng xong rồi vứt**: nhánh `return_all` return trước khối sup-t. Đó chính là đường **tầng 3** đi — nơi ta đọc β/θ/λ theo horizon, tức đúng chỗ cần dải đồng thời nhất. Giờ trả dải cho mọi hệ số, mỗi hệ số một `supt_c` **riêng** (β/θ/λ có ma trận tương quan qua horizon khác nhau).

### 6.2 M8/M9 không với tới được từ cascade (ĐÃ NỐI — nhưng runner còn thiếu)

`estimate_tier2`/`estimate_tier3` gọi `run_local_projection` **không truyền** `inference`/`simultaneous`/`method`/`tau`/`lags`, và `estimate_tier2` lọc cột ra bằng danh sách cứng nên nuốt luôn cột sup-t. Hệ quả: hộp tầng 3 ở §1 ("LP lag-augmented + HC1 · sup-t · quantile τ") **không dựng được** — M8/M9 tồn tại ở mức hàm nguyên thủy nhưng chết ở mức deliverable, và bảng γ 1a sẽ ra bằng đúng cái inference mà `SCA-01.lp_inference` nói là sai. Đã nối, mặc định giữ nguyên nên report cũ không đổi.

**Còn lại — việc của runner, không phải của thư viện:** `scripts/run_tier2.py` là runner **daily/tầng-2-tài-chính**, chưa có runner tháng cho 1a. Nó cũng chưa gọi `inference="lag_augmented"`/`simultaneous`/`quantile`, và `SHOCK_METHOD_TO_TYPE` chỉ có `{zscore, log1p, innovation}` — **không có `LEVEL+JUMP`**, nên trục SHOCK ba mức ở §1 chưa dựng được dù `shocks.level_plus_jump()` đã có. Cố ý chưa làm: nó phụ thuộc chữ ký §7.1 (trục SHOCK) và kéo theo một spec chưa chốt (`jump_thresh` q95 hay q99 cho track tháng — registry để hai mức).

### 6.2b Chân B: module xong, dữ liệu chưa (2026-08-02)

Ba stub trên đường LLM đã thành code + test (fake LLM, không mạng): `scoring/statement_scorer.py`, `indices/s_gpr.py`, `econometrics/ladder.py` + `config/ladder_v1.yaml`. Những gì **cố ý chưa làm** vì chờ chữ ký/dữ liệu: collector nguồn thật (§6.1 chọn 2 nguồn), backfill + human audit α≥0.6 (§6.2 người chấm thứ hai), cổng contamination §3.1 (cần điểm thật), encoder fine-tuned (đang là callable tiêm vào). Hai điểm phát hiện khi viết:

1. **Hai taxonomy kênh chỏi nhau**: docs/00 §2.4 chấm 6 kênh `{trade, military, sanction, diplomacy, energy, tech}`; docs/14 §1.1 + §1 file này nói "taxonomy 4 kênh" `{energy, trade, financial, military}` (kênh bảng γ). `sanction/diplomacy/tech` chưa có chỗ trong 4 kênh — code theo docs/00 (nguồn chân lý), mapping 6→4 chỉ điền cặp hiển nhiên, còn lại trả `None` **chờ user chốt**.
2. **Percentile cho chuỗi zero-inflated phải STRICT** (`<`, không `<=`): JUMP/S-GPR đa số ngày = 0 — định nghĩa `<=` cho ngày im ắng percentile ~100 và trigger ">p95" nổ mỗi ngày. Đúng cái bẫy zero-inflation mà registry KĐ-E1c đã ghi cho AUC; `expanding_percentile` dùng strict + test khóa.

### 6.3 Ba thứ ở §1 chưa có định nghĩa ở đâu

- **"số hạng J"** (hộp tầng 3) — không xuất hiện trong docs/07v2, 11, 12, 13, 14 hay registry. Là JUMP đưa vào hồi quy như một regressor cộng thêm, hay là thống kê J của kiểm định over-identification? Hai cái dẫn tới hai spec khác hẳn nhau. Cần đính chính trước khi ai đó code theo phỏng đoán.
- **Trần claim §4 chưa được máy khóa.** Registry có trường `claim_ceiling` nhưng không có test nào chặn một report claim vượt trần tầng của nó. Guard P1 chỉ khóa **số**, không khóa **mức claim**. Nếu §4 định là "in trên mọi output" thì nó cần cùng cơ chế khóa máy như `test_config_locked`/`test_registry_locked`, nếu không nó là lời hứa chứ không phải cổng.
- **`data/wui_global.csv` và `data/gold_events.csv`** vẫn chưa có; cái sau vẫn chặn E1c-exo → `primary_cell.shock`. Không phải việc code (docs/13 §2.2).