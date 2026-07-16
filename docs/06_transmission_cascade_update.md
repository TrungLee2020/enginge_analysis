# 06 — CẬP NHẬT KIẾN TRÚC 3 TẦNG TRUYỀN DẪN (Transmission Cascade)

**Phiên bản:** 1.1 — 07/2026
**Quan hệ tài liệu:** Bổ sung cho `00_engine_design.md`. Sửa lỗi nhân-quả: model hiện tại map thẳng `GPR shock → VNM` (2 tầng), thiếu tầng vĩ mô toàn cầu trung gian. Tài liệu này định nghĩa cấu trúc 3 tầng và các thay đổi code cụ thể.

> ## ⚠️ ĐÍNH CHÍNH (2026-07-16, sau review `08` / phản hồi `09`)
>
> **Kiến trúc 3 tầng của file này vẫn ĐÚNG và được review khen.** Nhưng 4 chi tiết công thức bên trong đã bị thay. Khi mâu thuẫn, **`07_formulas_reference_v2.md` (v2.1) là nguồn chân lý**, không phải file này:
>
> 1. **§1 tầng 3 thiếu hệ số β.** File này viết `r^c = θ·macro + λ·shock_direct` (HAI hệ số). Đúng phải là **BA**: `β` global-direct + `θ` indirect + `λ` domestic-direct. `GPR^{c,⊥}` là phần RIÊNG nước c, KHÔNG phải tác động trực tiếp của global shock lên nước c — đó là hai thứ khác nhau (review §4.2).
> 2. **§1 mediation sai.** `Indirect = Σ γ_{M,j}·θ^c_M` (nhân cùng horizon) → phải là **tích chập**: `Indirect(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ^c_M(h−s)` (review §4.1).
> 3. **`shock_j` là LEVEL.** Mọi shock phải là **innovation** = `LEVEL − E_{t-1}[LEVEL]` (review §4.4). Ảnh hưởng cả §1 tầng 2 lẫn tầng 3.
> 4. **§1 "variance decomposition"** → dùng **Shapley/LMG/FEVD**, không dùng `θ²Var/Var` (review §4.5).
>
> Thêm: **§2.1 nói "Schema — KHÔNG đổi" đã LỖI THỜI** — `ext_series` nay có `available_at/revised_at/source_version/data_version/quality_flag` (review §4.7). Và **§4 cổng G2a "γ có ý nghĩa, đúng kỳ vọng literature" đã BỊ BỎ** — đó là confirmation bias (review §4.6).
>
> **Gọi tên:** "transmission decomposition"/"predictive", KHÔNG "causal", cho tới khi có structural ID (G2.5 optional).

---

## 0. VẤN ĐỀ ĐANG SỬA

**Sai hiện tại:** `r_VN = f(GPR_shock, controls)` — gộp mọi loại shock vào một hệ số β duy nhất.
Hệ quả: shock Trung Đông (qua kênh dầu) và shock Mỹ-Trung (qua kênh tỷ giá/risk-off) bị trộn thành một, dù chúng đánh VN theo cơ chế hoàn toàn khác.

**Đúng — 3 tầng nối tiếp (mediation):**
```
TẦNG 1  SHOCK           GPR / S-GPR / GPT / GPA  (đã có)
   │
   ▼
TẦNG 2  GLOBAL MACRO    Oil, DXY, VIX, US10Y, EM-spread   ← THIẾU, thêm mới
   │                    = "Global Macro Impact" — sản phẩm độc lập, generic
   ▼
TẦNG 3  MARKET ĐÍCH     r_VN = f(tầng 2 đã truyền qua kênh, + direct effect)
                        params riêng từng nước (β_VN, β_TH...)
```

**Hai lợi ích:**
1. Sửa nhân-quả: tách được shock đi qua kênh nào → hệ số đúng.
2. Hai deliverable thay vì một: **Global Macro Impact** (tầng 1→2, bán cho bất kỳ ai) + **VN Transmission** (tầng 2→3, riêng VN).

**Nguyên tắc engine + params vẫn giữ:** tầng 1–2 là ENGINE (generic, ước lượng 1 lần). Tầng 3 là PARAMS (mỗi nước 1 file).

---

## 1. CÔNG THỨC

### Tầng 2 — Global Macro Response (generic)
Với mỗi biến vĩ mô toàn cầu M ∈ {ΔlnOil, ΔlnDXY, VIX, ΔUS10Y}:
```
M_t = a_M + Σ_j γ_{M,j} · shock_{j,t} + Σ_k ρ_{M,k} · M_{t-k} + u_{M,t}
```
- shock_j: GPRD, GPRD_ACT, GPRD_THREAT, (sau: S-GPR theo channel).
- Ước lượng bằng local projection → IRF: "1 đơn vị GPR shock đẩy dầu lên bao nhiêu sau h ngày".
- **Quan trọng — theo channel:** shock kênh `energy` (Trung Đông) kỳ vọng γ_oil cao; shock kênh `trade` (Mỹ-Trung) kỳ vọng γ_dxy, γ_vix cao. Đây là lý do trường `channel` ở Lớp 1 quan trọng.

### Tầng 3 — Country Transmission (params riêng)
```
r^c_{t+h} = α^c
          + θ^c_oil·ΔlnOil_t + θ^c_dxy·ΔlnDXY_t + θ^c_vix·VIX_t + θ^c_rate·ΔUS10Y_t   (INDIRECT: qua tầng 2)
          + λ^c · shock^direct_{c,t}                                                    (DIRECT: đánh thẳng)
          + Φ^c·X^c_t + ε
```
- **shock^direct**: phần GPR đánh thẳng vào tâm lý nhà đầu tư nước đó không qua biến vĩ mô — với VN là tin Biển Đông, thuế VN, GPRC_VNM⊥ (đã orthogonalize khỏi global).
- Phân rã đóng góp (variance decomposition): khi r_VN giảm, bao nhiêu % do oil / dxy / vix / direct.

### Mediation — đo direct vs indirect ~~(kiểm định nhân-quả)~~
> ⛔ **Công thức dưới là bản v1 ĐÃ BỎ** (nhân cùng horizon — xem đính chính đầu file, mục 2). Bản đúng: `07_formulas_reference_v2.md` §5.2 (tích chập). Giữ nguyên văn để đối chứng:
```
Total effect (GPR → r_VN)  = Direct (λ)  +  Indirect (Σ γ_{M,j} · θ^c_M)    ← SAI, v1
```
- Nếu Indirect >> Direct: VN chịu shock chủ yếu qua kênh vĩ mô toàn cầu (đúng kỳ vọng cho nền kinh tế nhỏ mở).
- Nếu Direct đáng kể: có thành phần rủi ro riêng VN không qua global — biện minh cho việc xây corpus tiếng Việt (V-phase).

---

## 2. THAY ĐỔI CODE — THEO MODULE

### 2.1. Schema — KHÔNG đổi
`ext_series` đã đủ (Oil/DXY/VIX/US10Y là series như GPR). `gpr_indices` chứa được output tầng 2. Không cần migration.

### 2.2. `econometrics/dataset.py` — mở rộng
- [ ] Thêm loader nhóm biến vĩ mô toàn cầu: `load_global_macro()` → DataFrame {oil, dxy, vix, us10y} đã transform (Δln cho giá, level cho VIX).
- [ ] Hàm `align(shock, macro, target, freq)` trả về panel sạch cho cả 3 tầng.
- [ ] Áp dụng log(1+GPR) như CLAUDE.md yêu cầu.

### 2.3. `econometrics/tier2_global_macro.py` — MODULE MỚI 🔬
- [ ] Local projection GPR shock → mỗi biến vĩ mô, h=0..30 ngày.
- [ ] Chạy riêng theo channel khi có S-GPR (energy vs trade vs sanction).
- [ ] Output: bảng γ (IRF coefficients) + đồ thị IRF cho từng biến vĩ mô.
- [ ] Lưu IRF vào `gpr_indices` dạng series phái sinh (vd `GLOBAL_OIL_RESPONSE`).
- [ ] **Đây là "Global Macro Impact" — deliverable độc lập, không cần VN.**

### 2.4. `econometrics/tier3_country.py` — MODULE MỚI 🔬 (đổi tên từ local_projection thuần)
- [ ] Phương trình tầng 3 với tách INDIRECT (qua macro) và DIRECT (λ).
- [ ] Đọc params từ `config/params/<country>.yaml` — khởi đầu `vn.yaml`.
- [ ] Variance decomposition: đóng góp từng kênh vào biến động r_country.
- [ ] Hàm `mediation_analysis()`: tính Direct/Indirect/Total + test ý nghĩa (bootstrap SE).

### 2.5. `econometrics/local_projection.py` — GIỮ, hạ vai trò
- [ ] Trở thành hàm LP tổng quát dùng chung (được tier2 và tier3 gọi), không còn là "model chính". Refactor thành utility: `run_local_projection(y, shock, controls, horizons) -> IRF`.

### 2.6. `config/params/vn.yaml` — MỚI
```yaml
country: VN
market_series: VNINDEX
direct_shock: GPRC_VNM_ORTH        # orthogonalized, xem Lop 4a
macro_channels: [oil, dxy, vix, us10y]
controls: [vnindex_lag1, liquidity_hose]
market:                            # cho backtest tang 3
  price_limit_pct: 7.0
  settlement: "T+2.5"
# theta_* KHONG dien tay — uoc luong tu tier3, ghi lai vao day sau khi fit
```

### 2.7. `indices/builder.py` — bổ sung
- [ ] Xuất các series tầng 2 (`GLOBAL_MACRO_IMPACT_*`) như chỉ số độc lập.
- [ ] Regime toàn cầu (risk-on/off) tính từ tầng 2, tách khỏi regime riêng VN.

### 2.8. `backtest/strategies.py` — cập nhật
- [ ] Chiến lược có thể trigger ở tầng 2 (global risk-off, áp dụng mọi thị trường) HOẶC tầng 3 (VN-specific).
- [ ] `sector_rotation`: dùng channel (shock kênh trade → xoay nhóm xuất khẩu VN; shock kênh energy → nhóm hưởng lợi/chịu thiệt từ giá dầu).

---

## 3. THAY ĐỔI DOCS

- [ ] `00_engine_design.md`: chèn mục "§0.bis Transmission Cascade 3 tầng" trước phần Fusion; sửa các phương trình Lớp 4 sang dạng 2 tầng mediation.
- [ ] `05_build_order.md`: chèn **G2 tách làm G2a (tầng 2 global macro) + G2b (tầng 3 country)** — xem §4 dưới.
- [ ] `01_research_methodology.md`: thêm KĐ12 (mediation: direct vs indirect).

---

## 4. THỨ TỰ THỰC THI CẬP NHẬT (thay G2 cũ)

| Bước | Nội dung | Cổng |
|---|---|---|
| **G2a** 🔬 | `tier2_global_macro.py`: GPR → Oil/DXY/VIX/US10Y bằng LP. Dữ liệu đã có sẵn 100% (chân A). Ra IRF + "Global Macro Impact" | γ có ý nghĩa: GPR shock thật sự đẩy dầu/đô/VIX? (kỳ vọng có, literature xác nhận energy là kênh mạnh nhất) |
| **G2b** 🔬 | `tier3_country.py`: tầng 3 cho VN, tách direct/indirect; `vn.yaml`; mediation analysis. Dùng GPRC_VNM (orthogonalized) làm direct shock | **KĐ1** (explanatory) + **KĐ12** (mediation): Indirect có ý nghĩa? Direct có ý nghĩa? |
| **G3** 🔬 | Backtest — giữ nguyên, nhưng chiến lược giờ chạy được ở cả 2 tầng | IC > 0.03 OOS |
| **G4** 🟢 | Serving — thêm endpoint `/v1/global-macro-impact` (tầng 2) tách khỏi `/v1/country/vn` (tầng 3) | demo 2 sản phẩm |

Phần G5–G7 (chân B/C/fusion) không đổi thứ tự, nhưng khi có S-GPR thì tầng 2 chạy lại **theo channel** để γ chính xác hơn.

---

## 5. THỨ TỰ ƯU TIÊN CHO CLAUDE CODE (làm gì trước)

1. `econometrics/local_projection.py` → refactor thành utility `run_local_projection()` (nền cho cả 2 tầng). Viết test trước.
2. `econometrics/dataset.py` → thêm `load_global_macro()` + transform.
3. `econometrics/tier2_global_macro.py` → module mới, chạy G2a. **Đây là bước cho ra deliverable "Global Macro Impact" đầu tiên, dữ liệu đã đủ.**
4. `config/params/vn.yaml` → tạo file.
5. `econometrics/tier3_country.py` → module mới, chạy G2b + mediation.
6. Cập nhật `indices/builder.py`, `backtest/strategies.py`.
7. Cập nhật 3 docs.

**Lưu ý bất biến (CLAUDE.md):** tier2/tier3 là 🔬 research — chạy ra kết quả trong notebook/report trước. Chỉ service hóa (indices/api) sau khi G2a/G2b pass cổng. Không hard-code θ vào yaml trước khi fit. log(1+GPR) bắt buộc. OOS 2023+ khóa cứng.
