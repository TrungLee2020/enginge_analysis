# 10 — ACTION PLAN: TỪ FIX BUG ĐẾN PHÁT TRIỂN (sau review 08/09)

**Phiên bản:** 1.0 — 2026-07-16
**Quan hệ tài liệu:** Kế hoạch thực thi cụ thể sau `08_review_and_recommendations.md` (review) và `09_review_response.md` (phản hồi + phân loại). Công thức chuẩn: `07_formulas_reference_v2.md` (v2.1). Thứ tự build tổng: `09` §4.
**Trạng thái đầu vào:** review code 2026-07-16 trên toàn bộ module thật (ingest ×3, dataset, data_files, local_projection, tier2, tier3, run_tier2). Các module còn lại là stub.

---

## 0. ĐÃ LÀM (2026-07-16, đợt đồng bộ docs/schema)

Ghi lại để không làm trùng:

- ✅ `sql/001_schema_core.sql`: `ext_series` + `available_at/revised_at/source_version/data_version/quality_flag`, PK mới `(series_id, date, data_version)`, index point-in-time; thêm bảng `index_quality`.
- ✅ 3 ingest module ghi `available_at`: daily = date+1d, monthly = **đầu tháng kế tiếp**+5d, market = close cùng ngày. (Lag là giả định thận trọng, chưa verify vintage thật — việc của G1-audit.)
- ✅ `dataset.load_series(as_of=...)` — lọc `available_at <= as_of` cho backtest point-in-time.
- ✅ `config/backtest.yaml`: split 4 tầng (dev 2015-20 / val 2021-23 / pseudo-OOS 2024-25 / **final holdout 2026-H1**), purge+embargo, gate mới, 7 benchmark. Khóa cũ `oos_start: 2023` bị thay hợp lệ (chưa backtest nào từng chạy).
- ✅ `CLAUDE.md`: nguyên tắc #3 viết lại; #8 mở rộng β/θ/λ + convolution; thêm **#9 innovation-not-level, #10 no-forward-fill, #11 available_at, #12 claims matrix**.
- ✅ `07_formulas_reference_v2.md` → v2.1: §3 tầng 2 đổi level → innovation (sót từ v2.0), thêm Z_t + EMSpread.
- ✅ Banner đính chính trên `05_build_order.md`, `06_transmission_cascade_update.md`.
- ✅ `docs/reports/G2a_global_macro.md`: banner ⛔ VÔ HIỆU (chạy trên level + gate ép dấu).
- ✅ Memory phiên làm việc: kết luận "GPRD coincident NO-GO" đổi thành "superseded, phải chạy lại với innovation".

Tests: 22/22 pass sau các thay đổi trên.

---

## 1. KẾT QUẢ REVIEW CODE (2026-07-16)

### Nền tốt, giữ nguyên
- `local_projection.py`: LP chuẩn Jordà, HAC/Newey-West đúng, guard mẫu nhỏ.
- `data_files.build_tier2_panel`: lưới bdate liên tục + complete-case một lần — đã sửa bug NaN thật (mỗi horizon chạy mẫu khác nhau).
- DXY splice major↔broad ở cấp return (overlap corr 0.926) — hợp lệ, có document.
- Ingest idempotent, giờ có vintage đầy đủ.

### 🔴 Bug phải sửa (Phase F)

| # | File | Lỗi | Đối chiếu |
|---|---|---|---|
| B1 | `scripts/run_tier2.py` | `gate_verdict()` ép "đúng dấu kỳ vọng" (`EXPECT_SIGN`/`LIT_EXPECT`) = confirmation bias; narrative "GPR coincident" hard-code trong report; **chạy lại là ghi đè banner vô hiệu** trên report cũ | review §4.6, 09 §2.5 |
| B2 | `tier3_country.py` `mediation_analysis()` | `Indirect = Σ_M θ_M·γ_M` **nhân cùng horizon** — phải là convolution `Σ_M Σ_s γ(s)·θ(h−s)` | review §4.1, 07v2 §5.2 |
| B3 | `tier3_country.py` `variance_decomposition()` | `θ²Var(M)/Var(r)` bỏ covariance, tổng có thể >100% — phải Shapley/LMG | review §4.5, 07v2 §5.3, CLAUDE.md #12 |
| B4 | `tier3_country.py` `estimate_tier3()` | Thiếu term `Σ_j β_j·GPR^{j,innov}` (global-direct) — chỉ có λ+θ (dạng v1). **Lưu ý: 01 Lớp 4b vốn có đủ 3 hệ số; 06/07-v1 làm rơi β khi chi tiết hóa, code theo. Fix = khôi phục spec gốc** | review §4.2, 01 §Lớp4b, 07v2 §5.1 |
| B5 | (toàn repo) | **Innovation không tồn tại**: `transform_gpr_shocks` chỉ có zscore/log1p (đều là level); module G2.0 chưa có; `surprise.py` stub | review §4.4, CLAUDE.md #9 |

### 🟡 Đáng sửa cùng đợt

| # | File | Vấn đề |
|---|---|---|
| M1 | `data_files.transform_gpr_shocks` | z-score dùng mean/std **toàn mẫu** — vô hại cho IRF descriptive (affine không đổi t-stat), nhưng là leakage nếu chảy vào signal. Innovation module phải rolling ngay từ đầu |
| M2 | `config/params/vn.yaml` | `direct_shock: GPRC_VNM_ORTH` vi phạm #10 nếu dùng daily (GPRC_VNM là monthly). Tách track daily/monthly + thêm mục β sources |
| M3 | `tier3_country.estimate_tier3` | Import `run_local_projection` nhưng không gọi — tự lặp vòng LP+HAC. Sửa: mở rộng utility trả về mọi hệ số |
| M4 | `tier2.global_macro_impact_index` | Chỉ lấy γ tại h=0 — nên là cumulative/peak IRF |
| M5 | docs 00/01/02 | Nợ sync 09 §5 bỏ sót: 00 §3.bis (2 hệ số + mediation cũ), 00 §1 (schema cũ), 01 KĐ12 (nhân cùng horizon), 01 C2 (split cũ), 02 §3.6 (OOS cũ) |

### Không phải bug (đã kiểm, khỏi nghi lại)
- `fill_weekend`: gán về ngày giao dịch **kế tiếp** — an toàn leakage.
- `ffill(limit=3)` trong build_tier2_panel: carry giá trị quá khứ — point-in-time hợp lệ.
- HAC maxlags = max(horizons) cho mọi h: quá bảo thủ (SE hơi rộng), không sai.

---

## 2. PHASE F — FIX (làm trước, 1 đợt)

> **✅ HOÀN TẤT 2026-07-16.** Commits: baseline `cf74b3c` → F0 `3eeaf3f` → F1 `74086c5` → F2 `cc1a3bf` → F3 `7638a4f` → F4 `dca92ff`. Cổng Phase F pass: 32 test (28 econ + 4 config-lock) xanh; run_tier2 smoke-test end-to-end, report tự đánh dấu INELIGIBLE khi shock=level, không ghi đè; grep công thức cũ sạch. Kèm thêm ngoài kế hoạch: archive `07_formulas_reference.md` → `_v1_archived.md` (doc 09 §5 tuyên bố nhưng chưa làm).
>
> Kỷ luật: công thức sửa nào cũng **viết test trước** (CLAUDE.md). Mỗi fix một commit.

### F0 — Đóng nợ sync docs 00/01/02 (M5)
- [ ] `00_engine_design.md`: banner đính chính §3.bis (3 hệ số, convolution, trỏ 07v2) + ghi chú schema §1 lỗi thời.
- [ ] `01_research_methodology.md`: sửa KĐ12 sang convolution; C2 split trỏ về `config/backtest.yaml` (4 tầng).
- [ ] `02_engineering_plan.md`: ghi chú OOS 2023 → split 4 tầng.
- Done khi: grep `Σ γ_{M,j}·θ` không còn xuất hiện như công thức "đúng" ngoài phần lịch sử/đối chứng.

### F1 — `run_tier2.py`: gate mới + chặn ghi đè (B1)
- [ ] Bỏ `EXPECT_SIGN`, `LIT_EXPECT`, logic "sai dấu = trượt".
- [ ] `gate_verdict()` mới theo 09 §2.5 — 6 tiêu chí: (1) pipeline đúng; (2) IRF ổn định qua spec; (3) CI báo đầy đủ; (4) dấu/độ lớn CÓ giải thích kinh tế (không bắt buộc trùng kỳ vọng); (5) null vẫn lưu; (6) channel-specific > generic khi phù hợp. Những tiêu chí máy không tự quyết (4) → report ghi "cần human review", không tự phán GO.
- [ ] Metadata report ghi rõ `shock_type: level|innovation` — chạy với level thì report tự đánh dấu "không dùng để kết luận gate".
- [ ] Output đổi tên file theo spec: `G2a_<shock_type>_<data_version>.md` — không bao giờ ghi đè report cũ.
- [ ] Narrative "GPR coincident" hard-code → bỏ, phần diễn giải sinh từ kết quả thực.

### F2 — `tier3_country.py`: khôi phục spec 3 hệ số (B2, B3, B4, M3)
- [ ] Test trước: convolution khớp tính tay trên IRF đồ chơi (γ, θ ngắn); Shapley tổng = R² full model, bất biến hoán vị; estimate_tier3 trả đủ β/θ/λ trên dữ liệu giả có cấu trúc biết trước.
- [ ] Mở rộng `run_local_projection` trả về **mọi** hệ số (không chỉ shock) → tier3 dùng lại, xóa vòng lặp trùng.
- [ ] `estimate_tier3`: thêm `global_shocks` (β) tách khỏi `direct_shock` (λ) — phương trình 07v2 §5.1.
- [ ] `mediation_analysis` → `transmission_decomposition` (đổi tên theo claims matrix #12): `Indirect_{j→c}(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ^c_M(h−s)`; nhận nguyên IRF theo horizon, không nhận scalar.
- [ ] `variance_decomposition` → `shapley_r2()`: K kênh ≤ 5 → 2⁵ subset, tính trực tiếp. Giữ hàm cũ chỉ khi đổi tên thành `_naive_variance_share_DEPRECATED` + warning, hoặc xóa hẳn (khuyến nghị: xóa — chưa ai gọi ngoài test).

### F3 — `config/params/vn.yaml`: tách track (M2)
```yaml
country: VN
market_series: VNINDEX
daily_track:                    # nguyên tắc #10: KHÔNG GPRC_VNM ở đây
  global_shocks: [GPRD_INNOV]          # β — global-direct
  direct_shock: null                   # chưa có daily VN shock (chờ AI-GPR daily / V-phase)
  macro_channels: [oil, dxy, vix, us10y]
monthly_track:
  global_shocks: [GPR_INNOV]
  direct_shock: GPRC_VNM_ORTH_INNOV    # λ — monthly only
  macro_channels: [oil, dxy, vix, us10y]
controls: [vnindex_lag1, liquidity_hose]
market: {price_limit_pct: 7.0, settlement: "T+2.5", lot_size: 100}
```

### F4 — Test khóa config (từ 02 §3.6: enforce bằng máy)
- [ ] `tests/test_config_locked.py`: assert 4 mốc split + `final_holdout_touched` flag đúng giá trị đã chốt. Ai sửa mốc → test đỏ. Assert thêm: nếu `final_holdout_touched: true` thì phải có `final_holdout_touched_commit`.

**⛔ Cổng Phase F:** toàn bộ test pass (cũ + mới); `run_tier2.py` chạy lại không phá report cũ; grep công thức cũ sạch.

---

## 3. PHASE D — PHÁT TRIỂN (thứ tự theo 09 §4)

### D1 = G0 — Research Governance (rẻ, làm trước G2.0)
- [ ] `docs/g0_governance.md`: hypothesis registry (mỗi giả thuyết: id, phát biểu, dữ liệu, test, ngày đăng ký — đăng ký TRƯỚC khi chạy); holdout policy (ai được chạm final holdout, khi nào, ghi log ở đâu); multiple-testing policy (đếm số lần thử để tính Deflated Sharpe); versioning policy.
- Claims matrix đã có ở 07v2 §6.4 — trỏ về, không lặp.
- Deliverable nhỏ: đăng ký ngay 4 giả thuyết đầu (KĐ1, KĐ3, KĐ5, KĐ12 bản innovation).

### D2 = G2.0 — `econometrics/shocks.py` (MẤU CHỐT — chặn mọi thứ sau)
Xây 6 biến theo 07v2 §2.0, tất cả **rolling, chỉ dùng quá khứ**:
```
LEVEL       = ln(1+GPR)                     (giữ để đối chứng, không vào hồi quy shock)
PERSISTENT  = Ê_{t-1}[LEVEL]                (AR(p)/EWMA rolling — chọn bằng AIC trên dev window)
INNOVATION  = LEVEL − PERSISTENT            ← shock chính
JUMP        = max(0, z_t − q95_rolling)
GPT_INNOV   = như trên, riêng threats
GPA_SURPRISE_v1 = GPA − Ê[GPA | GPT lags, GPA lags]
```
- [ ] **GPA_SURPRISE_v1 là surrogate**: spec đầy đủ (00 §4.2) condition trên S-GPR + Ladder — chưa tồn tại (G5/G6). Ghi rõ version trong tên cột (`GPA_SURPRISE_V1`) để KĐ9 sau này không lẫn hai spec.
- [ ] Test chống leakage (quan trọng nhất file test): sửa giá trị tại t+k bất kỳ **không được** làm đổi innovation tại ≤ t. Test hành vi: innovation của white noise ≈ chính nó; của AR(1) mạnh ≈ residual.
- [ ] Tách 3 pipeline dataset theo #10: `build_daily_panel()` (GPRD innovation + macro daily) / `build_monthly_panel()` (+GPRC_VNM) / event để sau.

**⛔ Cổng D2:** test leakage pass; innovation của GPRD có autocorr thấp (sanity: |ρ₁| ≪ ρ₁ của level).

### D3 = G2a re-run — trả lời câu hỏi đang mở
- [ ] Chạy `run_tier2.py` (đã fix F1) với `GPRD_INNOV`, controls Z_t, thêm EM spread nếu FRED có (BAMLEMIBHGCRPIOAS hoặc tương đương).
- [ ] Robustness: sub-sample như cũ + so sánh level vs innovation cạnh nhau (level giữ làm đối chứng).
- [ ] Report mới `G2a_innovation_<version>.md` — human review mục "giải thích kinh tế" trước khi phán GO/NO-GO.
- **Trạng thái tri thức hiện tại: CHƯA AI BIẾT innovation có lead hay không.** Kết luận cũ vô hiệu; không mang theo prior "NO-GO".

**⛔ Cổng D3 (gate mới, 6 tiêu chí):** quyết định GO/NO-GO tầng 2 **thật** — lần đầu tiên.

### D4 = G2b — Country transmission cho VN
- [ ] Chạy `estimate_tier3` (đã fix F2) trên **2 track riêng**: daily (GPRD_INNOV only, không GPRC) và monthly (+GPRC_VNM⊥ innovation).
- [ ] Kiểm định theo 01: **KĐ1** (explanatory), **KĐ3** (GPT vs GPA — dùng GPT_INNOV vs GPA_SURPRISE_V1), **KĐ5** (lead-lag GPRD→VN — "giá trị thương mại cao nhất", 02 §G2), **KĐ12** (transmission decomposition bản convolution + bootstrap SE).
- [ ] Shapley cho đóng góp kênh; historical contribution cho serving sau này.
- [ ] Report `G2b_country_<version>.md`; θ/λ/β fit xong ghi lại vào `vn.yaml` (không điền tay — CLAUDE.md #8).

**⛔ Cổng D4 = cổng G2b:** KĐ1 pass trên ít nhất 1 track → G3. Fail cả hai → dừng, đánh giá lại (không ép).

### D5 = G2c — So sánh shock types
- [ ] Bảng so: generic GPR innovation vs GPT_INNOV vs GPA_SURPRISE_V1 vs JUMP — trên cùng outcome, cùng window. Trả lời "shock nào đáng dùng" trước khi G3 tiêu tiền vào backtest.

### Sau đó (không chi tiết ở đây)
G2.5 structural ID (optional, không chặn) → G3 locked backtest (chỉ sau khi D3/D4 có GO) → G4 serving. Xem 09 §4.

---

## 4. THỨ TỰ & PHỤ THUỘC

```
F0 ─┐
F1 ─┼─ độc lập, làm song song được ─┐
F3 ─┤                               ├─→ D2 (G2.0 shocks) ─→ D3 (G2a rerun) ─→ D5
F4 ─┘                               │            └────────→ D4 (G2b) ──────→ (G3...)
F2 ────── (D4 cần F2) ──────────────┘
D1 (G0) ── độc lập, chèn bất kỳ lúc nào trước D3
```

Nguyên tắc xuyên suốt: 🔬 research hết — mọi bước ra **report versioned** (`data_version` + git commit), không service hóa gì cho tới sau G3. Kết quả null/xấu vẫn lưu và báo cáo.

---

## 5. RỦI RO CỦA CHÍNH PLAN NÀY

| Rủi ro | Giảm thiểu |
|---|---|
| Innovation spec (AR vs EWMA, window) tự nó là 1 bậc tự do — thử nhiều spec rồi chọn cái đẹp = data snooping ở cửa mới | Chọn spec bằng AIC **trên development window only** (2015-20), đăng ký trong hypothesis registry TRƯỚC khi nhìn kết quả G2a |
| G2a innovation lại NO-GO thật | Vẫn có giá trị: đóng cửa tầng 2 một cách ĐÚNG, dồn lực vào domestic-direct (λ) + chân B/C — chính là kịch bản memory cũ đoán, nhưng lần này có bằng chứng hợp lệ |
| available_at lag là giả định (daily +1d, monthly +5d) | G1-audit: quan sát vài lần publish thực tế của matteoiacoviello.com; sửa hằng số một chỗ trong ingest |
| Phase F kéo dài, mất đà | F0–F4 đều nhỏ; giới hạn 1 đợt làm việc, không refactor lan man ngoài danh sách B/M |
