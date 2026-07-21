# G0 — Research Governance

**Phiên bản:** 1.1 — 2026-07-21 (thêm §7: hai quyết định governance đang mở, phát hiện khi đối chiếu `docs/14` v1.2 với code)
**Quan hệ tài liệu:** thực thi bước D1 trong `10_action_plan.md` §113. Được `09_review_response.md` §2.8 yêu cầu (🔴 bắt buộc). Claims matrix nằm ở `07_formulas_reference_v2.md` §6.4 — file này **trỏ về**, không lặp.

> Mục đích: chống data-snooping và HARKing (hypothesizing after results are known) bằng **kỷ luật ghi trước, khóa bằng máy** — không bằng lời hứa. Đây là điều kiện tiên quyết để mọi cổng GO/NO-GO sau này (D3, D4, G3) có giá trị.

---

## 1. Hypothesis registry — đăng ký trước khi chạy

**File:** `config/hypothesis_registry.yaml` · **Khóa:** `tests/test_registry_locked.py`.

Mỗi giả thuyết ghi: `id`, `statement` (phát biểu + H0), `data`, `shock`, `method`, `outcome`, `decides_gate`, `registered` (ngày), `status`. Quy tắc vòng đời:

- `status: registered` — đã đăng ký, **chưa chạy**. Sửa tự do (chưa tiêu bậc tự do nào).
- `status: tested` — đã chạy + có report versioned. **KHÓA**: không sửa `statement`/`shock`/`method`/`data`. Đổi ý sau khi đã `tested` = giả thuyết **MỚI** (id mới), không phải sửa cái cũ. Đây chính là ranh giới giữa "khám phá hợp lệ" và "HARKing".

Đã đăng ký (2026-07-18, trước khi đọc kết quả G2a-innovation): **KĐ1** (tính giải thích), **KĐ3** (threats vs acts), **KĐ5** (lead-lag global→VN, giá trị thương mại cao nhất), **KĐ12** (transmission decomposition 3 kênh). Định nghĩa gốc: `docs/01` §C2.

### 1.1 Spec khóa trước — AR order cho PERSISTENT

Bậc tự do mà `docs/10` §5 cảnh báo mạnh nhất: order `p` của AR trong `shocks.py` (PERSISTENT = Ê_{t-1}[LEVEL]). Nếu thử nhiều order rồi chọn cái cho kết quả G2a "đẹp" = snooping ở cửa mới.

**Khóa:** `p` chọn bằng **BIC trong trần parsimony `max_order=5`** trên **development window 2015–2020 only** (`select_ar_order`), deterministic, tái lập được. Giá trị chốt ghi trong registry: GPRD `p=5`, GPRD_ACT `p=5`, GPRD_THREAT `p=2`.

**Vì sao trần 5 + BIC (robustness đã chạy 2026-07-18):** AIC/BIC **không có cực tiểu nội** với GPR daily — tự tương quan regime dài đẩy argmin AIC→20+, BIC→14–16; để tiêu chí tự do chọn thì nó đuổi biên, spec bất ổn + snooping order. **Nhưng** INNOVATION đo được đã ổn định từ `p≈6`: `corr(innov_p8, innov_p10)=0.99`, autocorr innovation ≈ 0.03–0.04 ở mọi order 4..16 — mục tiêu (khử phần đã dự báo được) đạt rồi, thêm lag không đổi kết quả thực chất. Trần `p=5` (1 tuần giao dịch) có diễn giải kinh tế, đủ khử autocorr (`ρ₁≈0.04` từ `p=4`), parsimony. Lag regime bậc cao còn lại LP tầng 2 kiểm soát bằng macro-lags.

**boundary_flag=true** giờ mang nghĩa: order = trần parsimony **chủ động** (không phải cực tiểu nội, cũng không phải AIC bị chặn). `robustness_checked: true` trong registry xác nhận đã kiểm — không cần nới thêm.

---

## 2. Holdout policy — TÁCH THEO TRACK (quyết định 2026-07-19, docs/13 §4.1)

**Khóa cứng nền:** `config/backtest.yaml` split 4 tầng + `tests/test_config_locked.py`.
Development 2015–2020 / Validation 2021–2023 / Pseudo-OOS 2024–2025 / Final holdout 2026-H1.

**Vấn đề số học buộc phải tách track (không phải chọn A/B/C tùy ý):** tại horizon `h`,
cú sốc cuối dùng được = (ngày cuối dữ liệu − h). Dữ liệu kết thúc ~2026-06:

| Track / horizon | 2026-H1 cho ra bao nhiêu quan sát dùng được |
|---|---|
| Ngày, h=30 | ~95 phiên — **dùng được** |
| Tháng, h=1 | ~5 tháng |
| Tháng, h=6 | **0** |
| Tháng, h=0..24 (ô chính SCA) | **0 — holdout RỖNG theo cấu tạo** |

A/B/C (giữ / dời / tách theo regime) đều giả định holdout là lát cắt thời gian tranh
luận được về *chất lượng*. Với track tháng vấn đề không phải chất lượng — là **không tồn tại**.

**Chính sách chốt:**

| Track | Chính sách | Lý do |
|---|---|---|
| **Ngày** | GIỮ `final_holdout: 2026-01-01…2026-06-30`, chạm ĐÚNG 1 LẦN, báo cáo kèm cảnh báo chế độ đơn lẻ (Hormuz) | ~95 quan sát dùng được; giả thuyết đang test là giả thuyết ĐUÔI → cửa sổ chứa sự kiện đuôi lớn nhất lịch sử là ĐÚNG loại dữ liệu |
| **Tháng** | **CHƯA CÓ holdout.** Pseudo-OOS 2024–2025 là trần bằng chứng. `claim_ceiling = predictive, chưa xác nhận holdout`. Hoãn final holdout tới ~2028-H2 (đủ ~24 tháng hậu 2026) | Holdout tháng rỗng theo cấu tạo (bảng trên) |

**KHÔNG dời holdout sang 2026-H2** (B/C cũ): ở đó (a) không có sự kiện đuôi để test giả
thuyết đuôi, (b) `jump()` dùng q95 rolling 250 phiên → JUMP bị nén cơ học đúng khoảng đó.
Test giả thuyết đuôi trên mẫu không đuôi bằng thước đo đang bị bóp = phí lần chạm duy nhất.

**Trần claim thấp hơn cho track tháng — chấp nhận được, phải GHI RA:** sản phẩm phân phối
+ đo lường chỉ cần pseudo-OOS + tính bền qua specification curve + danh sách episode kiểm
chứng được. Bằng chứng cấp holdout chỉ use case tín hiệu giao dịch cần — mà docs/11 §13.3
đề nghị bỏ. Trần thấp hơn không hỏng sản phẩm; nó phải được ghi thay vì ngầm hiểu.

- Chạm holdout NGÀY: đặt `final_holdout_touched: true` + commit trong cùng commit chạm.
  Test khóa enforce. Sau khi chạm: KHÔNG sửa model theo kết quả (CLAUDE.md #3).
- Holdout theo episode: KHÔNG dùng — chọn episode nào giữ là bậc tự do mới không khóa chặt
  đủ; sự kiện đuôi quá hiếm để holdout nào có power. Ghi thẳng điều này thay vì dựng cơ chế
  trông nghiêm ngặt mà không xác nhận được gì.

---

## 3. Multiple-testing policy — đếm số lần thử

Mỗi lần chạy 1 spec trên 1 outcome = **1 trial**. Số trial phạt vào:
- **Deflated Sharpe Ratio** (Bailey–López de Prado) ở G3.
- **Hansen SPA / White Reality Check** cho so sánh nhiều chiến lược.
- **Block bootstrap** giữ autocorrelation khi tính CI.

Ghi ở `trial_log.n_trials` trong registry, cập nhật thủ công mỗi backtest mới. Research LP (G2a/G2b) **chưa** tính vào — đếm bắt đầu ở G3 (backtest tín hiệu). Gate G3 (config `gates`) đã bỏ ngưỡng "IC>0.03" đơn lẻ, thay bằng incremental-IC>0 có CI, ổn định qua regime, dương sau phí.

---

## 4. Versioning policy

- Mọi report nghiên cứu: `data_version` (hash file/nguồn) + `git_commit` + `generated_at`. `run_tier2.py` đã enforce; report **không bao giờ ghi đè** (tên theo `<shock_type>_<data_version>`).
- Bảng điểm số: `model_version` + `rubric_version` (CLAUDE.md #4).
- Feature có version trong tên khi spec chưa cuối: vd `GPA_SURPRISE_V1` (surrogate) để không lẫn với spec đầy đủ sau này.

---

## 5. Claims matrix — chỉ claim đúng mức nhận dạng

Ma trận đầy đủ: **`07_formulas_reference_v2.md` §6.4**. Tóm tắt ràng buộc:

`measurement ≺ association ≺ prediction ≺ structural response ≺ causal effect`

Reduced-form LP → gọi "transmission decomposition"/"predictive", **KHÔNG "causal"** cho tới khi có structural ID (LP-IV/proxy-SVAR, G2.5 optional). Variance decomposition dùng Shapley/LMG/FEVD, KHÔNG `θ²Var(M)/Var(r)`. Mỗi giả thuyết trong registry ghi `claim_ceiling` khi cần (vd KĐ12).

---

## 6. Cổng D1 (định nghĩa "done")

- [x] `config/hypothesis_registry.yaml` tồn tại, 4 giả thuyết đầu đăng ký với `status: registered`.
- [x] AR order khóa trong registry (pre-registration trước khi đọc G2a).
- [x] `tests/test_registry_locked.py` enforce cấu trúc + khóa spec bằng máy.
- [x] Holdout/multiple-testing/versioning policy viết rõ; claims matrix trỏ về 07v2 §6.4.

---

## 7. QUYẾT ĐỊNH ĐANG MỞ — chưa chốt, **không được ngầm hiểu là đã chốt**

Cả hai phát hiện 2026-07-21 khi đối chiếu `docs/14` với code. Ghi ở đây vì đây là **quyết định governance**, không phải lựa chọn kỹ thuật: cái nào cũng đổi nghĩa của một nguyên tắc đã khóa. Chưa chốt thì registry **chưa được sửa** theo hướng nào.

### 7.1 SHOCK mặc định — LEVEL, hay để làm trục báo cáo?

`docs/14` v1.1 §2 mục 1c ghi "shock mặc định = LEVEL". Va chạm ba chỗ:

1. **CLAUDE.md #9** — level vào hồi quy rồi gọi hệ số là "tác động của cú sốc" là sai khái niệm.
2. **`scripts/run_tier2.py:76`** — `GATE_ELIGIBLE_SHOCK_TYPES = {"innovation"}`, run LEVEL tự đóng dấu `INELIGIBLE`.
3. **E0 tự khai** level là ngoại lệ có chủ đích, chỉ dùng khi tái lập spec người khác.

Lịch sử: E1 → E1b → E1c chưa từng kết luận được thước đo nào thắng. `SCA-01.primary_cell.shock = UNRESOLVED`, chặn bởi `data/gold_events.csv` (cần 2 người dựng tay).

**Ba lựa chọn:**

| | Chọn | Hệ quả phải làm kèm |
|---|---|---|
| A | **SHOCK làm trục báo cáo** cho bảng γ mô tả: chạy cả {LEVEL, INNOVATION, LEVEL+JUMP}, báo cáo hết, không chọn | Sửa `GATE_ELIGIBLE_SHOCK_TYPES` cho phép mọi thước đo khi report **ghi cả ba**. `primary_cell.shock` vẫn UNRESOLVED. **Không** đụng #9 |
| B | LEVEL thành mặc định nhà | Sửa **CLAUDE.md #9** + cổng máy + registry, **cùng một commit**. Phải viết lý do vào đây, không để trong checkbox |
| C | Giữ INNOVATION, hoãn 1a tới khi có gold set | Đường găng dài thêm không xác định; docs/14 sinh ra để gỡ đúng chỗ nghẽn này |

**Khuyến nghị: A.** Chọn một thước đo bây giờ là chốt bằng thẩm quyền chứ không bằng bằng chứng — đúng cái HARKing mà registry sinh ra để chặn. Bảng γ là **mô tả**, curve SCA mới là **suy diễn**; hai việc không cần chung một quyết định. Nếu ba thước đo cho cùng câu chuyện thì kết luận bền hơn hẳn so với chọn trước một cái.

**Chốt:** _chưa điền_ · **Người:** _chưa điền_ · **Ngày:** _chưa điền_ · **Lý do:** _chưa điền_

### 7.2 Chân B không còn development window (cutoff × split)

`docs/14` §3.1.3 buộc claim dự báo chân B chỉ kiểm trên dữ liệu **sau training cutoff của scorer**. Với GPT-4o-mini (cutoff ≈ 10/2023), post-cutoff = 2024+. Nhưng §2 file này khóa: Pseudo-OOS 2024–2025, Final holdout 2026-H1.

**Cửa sổ sạch duy nhất của chân B CHÍNH LÀ pseudo-OOS + holdout.** Chân B không còn development window. KĐ8 trên track tháng ≈ 24 quan sát — không đủ power cho kết luận nào.

Đây là ràng buộc số học giống hệt §2 (holdout tháng rỗng theo cấu tạo): không phải tranh luận về *chất lượng* cửa sổ, mà là nó **không tồn tại**.

| | Lối ra | Đánh đổi |
|---|---|---|
| (i) | KĐ8 đánh ở tần suất **ngày/tuần** | 2024–2025 cho ~500 quan sát thay vì 24. Cần collector chân B chạy dày |
| (ii) | 2024–2025 = **development window của chân B**; claim dự báo hoãn tới khi 2026-H2+ đủ dữ liệu | Trung thực nhất, chậm nhất. Trần claim chân B v1 = `association` |
| (iii) | Scorer có cutoff **sớm hơn** để 2021–2023 thành post-cutoff sạch | Đổi chất lượng chấm lấy sạch thời gian |

**Khuyến nghị: (i)+(ii).** Nhất quán với §2: trần claim thấp hơn không hỏng sản phẩm, nhưng **phải được ghi ra thay vì ngầm hiểu**.

**Chốt:** _chưa điền_ · **Người:** _chưa điền_ · **Ngày:** _chưa điền_ · **Lý do:** _chưa điền_
