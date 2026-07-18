# G0 — Research Governance

**Phiên bản:** 1.0 — 2026-07-18
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

## 2. Holdout policy — final holdout chạm đúng 1 lần

**Khóa cứng:** `config/backtest.yaml` split 4 tầng + `tests/test_config_locked.py`.

- Development 2015–2020 (tự do thử) / Validation 2021–2023 (chọn model/feature) / Pseudo-OOS 2024–2025 (walk-forward) / **Final holdout 2026-H1 — chạm ĐÚNG 1 LẦN**.
- Ai được chạm final holdout: chỉ sau khi MỌI quyết định model đã chốt trên development+validation. Sau khi chạm: **KHÔNG sửa model theo kết quả**. Kết quả xấu = báo cáo kết quả xấu (CLAUDE.md #3).
- Ghi log: đặt `final_holdout_touched: true` + `final_holdout_touched_commit: <hash>` trong cùng commit chạm. Test khóa enforce: `touched=true` phải kèm commit.

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
