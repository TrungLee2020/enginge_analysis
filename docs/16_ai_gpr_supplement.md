# 16 — BỔ SUNG SAU AI-GPR (Iacoviello & Tong, 07/2026)

**Phiên bản:** 1.2 — 2026-08-05 (v1.1 — 2026-08-03, v1.0 cùng ngày)
**Khác v1.1 — sau khi TẢI THẬT file daily và đối chiếu trang download thật (chưa tải file monthly):**
(i) **Schema §1 đã xác minh trên file thật** (`ai_gpr_data_daily.csv`, vintage `13b8e8b48d41`, 1960-01-01..2026-07-31) — tên cột hoàn toàn khác giả định cũ, xem `data_files.py::AI_GPR_COLUMNS`;
(ii) **⛔ Đính chính quan trọng: Country index và Bilateral KHÔNG phải daily.** Trang download thật liệt kê tường minh: `ai_gpr_country_monthly.csv`, `ai_gpr_bilateral_monthly.csv`, `ai_gpr_country_eventtype_monthly.csv` — tên file tự nói lên granularity. §3 v1.1 dùng "country index daily" làm tiền đề để kết luận "gỡ ràng buộc #10" — tiền đề đó **sai**, kết luận đó **rút lại**, xem §3 bản sửa;
(iii) **Oil GPR theo vùng ĐÚNG là có ở daily** (điểm duy nhất bảng cũ đúng hướng) — nhưng file daily chỉ có **8 vùng** (MiddleEast/Russia/USA/Venezuela/Africa/Americas/Asia/NorthSea), không phải 13 như bảng cũ ghi; 13 vùng có thể là số ở bản monthly (chưa tải, chưa xác minh);
(iv) Rủi ro "chỉ có 1 file latest bị ghi đè" nêu ở §1 v1.1 — **đã loại**: link tải có query `?v=<timestamp>` (cache-busting), tên file cố định qua các lần tải, `ai_gpr_vintage()` (hash file) vẫn là cách ghim đúng vì bản thân file thay đổi nội dung mỗi kỳ dù URL không đổi.

**Loại:** doc **bổ sung**, không thay thế. docs/11, 14, 15 giữ nguyên trừ các mục ghi rõ dưới đây.
**Nguồn:** Iacoviello & Tong (2026), "The AI-GPR Index", Fed Board. Dữ liệu công khai, cập nhật định kỳ: `matteoiacoviello.com/ai_gpr.html`
**Vì sao có doc này:** tác giả gốc của GPR vừa publish bản LLM của chính chỉ số đó, kèm dữ liệu. Ba khối lớn trong kế hoạch cũ trở thành ingest thay vì build; một quyết định đang treo được gỡ; một lời khuyên cũ của doc 15 bị bác.

---

## 1. NGUỒN DỮ LIỆU MỚI — INGEST, KHÔNG BUILD

**✅ Bảng dưới đã sửa theo trang download thật + file daily đã tải (2026-08-05).** Bảng v1.1 đoán granularity từ mô tả trang — sai ở 2/5 dòng. Đừng lặp lại lỗi đó: tin file/trang thật, không tin mô tả diễn giải lại.

| Series | Tần suất THẬT | Phủ | Trạng thái | Thay thế việc gì trong plan cũ |
|---|---|---|---|---|
| AI-GPR headline (`GPR_AI`) | daily | 1960–nay | ✅ đã tải, đã ingest | chân A LLM scoring (docs/14 Phase 2 phần news) |
| Threats/Acts (`THREATS_GPR_AI`/`ACTS_GPR_AI`) | daily | 1960–nay | ✅ đã tải, đã ingest | tách ACT/THREAT thô của `shocks.py` |
| Oil GPR theo vùng (`GPR_OIL_*`, 8 vùng ở bản daily) | **daily** | 1960–nay | ✅ đã tải, đã ingest | channel routing kênh energy (docs/11 §5.3 giai đoạn 2) — ở mức DAILY, tốt hơn kỳ vọng ban đầu |
| Country index × 200 nước × 4 vai | **monthly** (KHÔNG phải daily — sửa §3 v1.1) | ? | ⏳ chưa tải (`ai_gpr_country_monthly.csv`) | country sub-index — chỉ nâng cấp track THÁNG |
| Country × 8 loại sự kiện | **monthly** | ? | ⏳ chưa tải (`ai_gpr_country_eventtype_monthly.csv`) | ứng viên taxonomy kênh truyền dẫn — cần kiểm 8 loại có map sạch sang 4 kênh (energy/trade/financial/military) không |
| Bilateral có hướng × 1.200 cặp | **monthly** (KHÔNG phải daily) | ? | ⏳ chưa tải (`ai_gpr_bilateral_monthly.csv`) | — mới hoàn toàn, nhưng chỉ ở mức tháng |
| `GPR_AER`, `GPR_NONOIL` | daily | 1960–nay | ⚠️ có trong file, Ý NGHĨA CHƯA XÁC MINH | mới hoàn toàn — cần đọc `AI_GPR_PAPER.pdf` trước khi dùng |

**Việc code — ĐÃ XONG cho phần daily (2026-08-05):** `data_files.py::load_ai_gpr_daily()` + `AI_GPR_COLUMNS` (đã sửa khớp file thật) + `describe_ai_gpr_file()` + `ai_gpr_vintage()`. **Còn thiếu:** loader cho 3 file monthly ở trên — chưa viết, vì chưa có file thật để đối chiếu schema (cùng nguyên tắc "không đoán rồi để im" đã áp dụng cho bản daily).

**Giữ GPRD gốc** làm series đối chứng — E0 đã PASS trên nó, và tương quan AI-GPR vs GPR gốc chỉ 0.69, đủ khác để so sánh có ý nghĩa.

**⚠️ Rủi ro §1 v1.1 nêu ("file latest bị ghi đè") — đã kiểm, KHÔNG xảy ra theo cách đáng lo.** Link tải mang query `?v=<timestamp>` nhưng tên file (`ai_gpr_data_daily.csv`) không đổi qua các lần tải — nội dung file vẫn thay đổi mỗi kỳ cập nhật (đúng bản chất "latest"), nhưng `ai_gpr_vintage()` (hash nội dung, không phải tên file/URL) vẫn phân biệt đúng hai lần tải khác nhau. `load_ai_gpr()` vẫn giữ nguyên tắc: đọc file cục bộ đã tải tay, thiếu thì raise kèm hướng dẫn — **không** tự fetch ngầm (và **không thể** tự fetch trong môi trường Claude Code hiện tại: domain `matteoiacoviello.com` bị chặn ở egress policy của sandbox, xác nhận 2026-08-05 — không phải do trang chặn bot).

---

## 2. GỠ §7.1 — PHƯƠNG ÁN THỨ TƯ, VÀ MỘT ĐÍNH CHÍNH

### 2.1. Đính chính lời khuyên trong docs/15 — **và đính chính chính mục này**

> **Đã kiểm bằng dữ liệu của dự án: `docs/reports/E2_component_decomposition_e73a0a307fc3.md`** (`scripts/run_e2_component_check.py`, 2026-08-03). Kết quả: **cơ chế đúng, kết luận định lượng không đứng được.** Bản v1.0 của mục này viết quá tay; đoạn dưới là bản đã sửa.

**Cơ chế (ĐÚNG, đã tái lập).** docs/15 nói lag augmentation làm `shock=LEVEL` biện minh được vì nó partial-out phần dự báo được. Đúng về mặt cơ chế — và đó chính là điều mục này chỉ ra: theo FWL, hệ số của LEVEL dưới lag augmentation **là** hệ số của thành phần bất ngờ. E2b xác nhận trên 45 ô: `corr(β_LEVEL, β_INNOVATION) = 0.9985`, lệch tương đối trung vị 6.0%. Hai cái gần như là một.

**Kết luận định lượng (KHÔNG đứng được như đã viết).** Bài AI-GPR §6.1 tách ∆GPR bằng AR(4) thành fitted (persistent) + residual (shock):

| Thành phần | Hệ số (thô) | Ý nghĩa |
|---|---|---|
| Persistent (dự báo được) | **−0.271** | ** |
| Shock (residual) | −0.119 | * |

v1.0 đọc bảng này là "persistent tác động hơn gấp đôi". **Hai hệ số đó chưa so được với nhau**: chúng nằm trên hai regressor có phương sai khác hẳn. AR(4) trên chuỗi **sai phân** có R² thấp (trên GPRD tháng: 0.10), nên `Var(fitted)/Var(resid) ≈ 0.11` — phần fitted có biên độ nhỏ hơn khoảng ba lần. Hệ số thô gấp đôi trên một regressor biên độ 1/3 là **đóng góp nhỏ hơn**.

Đây đúng là **tai nạn thang đo** mà registry đã ghi cho `LEVEL+JUMP` (`level_plus_jump_composition`) — cùng cái bẫy, chỗ khác.

E2 chạy đúng phân rã đó trên panel tháng của dự án:

| GPR → IP, h=2 | β_persistent | β_shock |
|---|---|---|
| **Thô** | −1.187 | −0.611 |
| **Chuẩn hóa** (×sd) | −0.088 | **−0.139** |

Thô thì persistent lớn gấp đôi — **tái lập đúng pattern của bài**. Chuẩn hóa thì **thứ tự đảo**. Trên toàn bộ 45 ô: 34 ô có |β_P|>|β_S| theo thô, chỉ 12 ô giữ được sau chuẩn hóa — **22 ô (48.9%) đảo chiều kết luận**. Ở ô chính của T2-full (`GPR_ACT→IP`, h=2), shock có ý nghĩa (p=0.042) còn persistent thì không (p=0.18).

**Hệ quả cho câu "đây là lời giải thích cho G2a yếu": KHÔNG đứng.** Nếu dùng `INNOVATION` là dùng "nửa yếu", thì LEVEL phải cứu được. Trong `T2_full` LEVEL cũng cho **0/4 giá tài sản**, y hệt INNOVATION — vì dưới lag-aug hai cái là cùng một thứ (corr 0.9985). Không có nửa mạnh nào bị bỏ quên ở đó.

**⚠️ Giới hạn của phản biện này — không bác bảng của bài.** E2 chạy GPRD **tháng**; bài chạy AI-GPR **tuần**. AI-GPR dai hơn (§5: tự tương quan 0.73 vs 0.62) → R² của AR(4) trên nó cao hơn → phần fitted biên độ lớn hơn → khoảng cách chuẩn hóa **có thể không đảo**. E2 bác **cách đọc bảng khi chưa chuẩn hóa**, không bác con số của bài.

**Việc phải làm để khép lại:** (a) hỏi bài báo cáo hệ số thô hay chuẩn hóa, và `Var(fitted)/Var(resid)` của họ; (b) chạy lại E2 trên AI-GPR ngay khi `load_ai_gpr()` có dữ liệu. Nếu bài đã chuẩn hóa thì §2.1 v1.0 đúng nguyên và E2 chỉ còn giá trị cho chuỗi GPRD.

### 2.2. Quyết định thay thế cho A/B/C

$$y_{t+h} - y_{t-1} = \alpha_h + \beta_h^{P}\,\widehat{\Delta G}_t + \beta_h^{S}\,\hat u_t + \text{controls} + \varepsilon_{t+h}$$

với $\widehat{\Delta G}_t$ = fitted và $\hat u_t$ = residual từ AR(p) trên $\Delta$AI-GPR.

- **Hai regressor, không phải hai spec.** Không chọn giữa LEVEL/INNOVATION/LEVEL+JUMP nữa — đưa cả hai thành phần vào cùng lúc.
- `INNOVATION` hiện tại của `shocks.py` **chính là** $\hat u_t$ (khác order p). Không cần code mới, cần thêm cột fitted vào design matrix.
- Trục báo cáo SHOCK trong `SCA-01` giữ nguyên làm robustness; ô chính chuyển sang spec kép này.
- **AR order:** bài dùng p=4 trên chuỗi tuần. Registry đã khóa 5/5/2 — spec kép là **id mới**, đăng ký p riêng, không đụng id cũ.

**Đề xuất này SỐNG SÓT nguyên vẹn qua E2 — nó chính là lối ra đúng.** Tranh cãi ở §2.1 là "thành phần nào mạnh hơn"; spec kép **giải tán câu hỏi đó**: đưa cả hai vào thì không phải chọn, báo cáo được cả hai. Nghiêm ngặt hơn LEVEL lẫn INNOVATION đơn lẻ. Hai điều kiện bắt buộc kèm theo (E2 §Kết luận):

1. **Đóng góp phải báo cáo CHUẨN HÓA** (`β×sd`), không phải hệ số thô. Bảng γ mới mà in hệ số thô cạnh nhau sẽ tái lập đúng ngộ nhận của §2.1 v1.0, chỉ khác là lần này do chính mình dựng.
2. **Kỷ luật NHÃN, và phải là cổng máy.** Spec kép không phá CLAUDE.md #9 nhờ *cách gọi tên*, không nhờ công thức: $\beta^P$ hợp lệ khi gọi là "phản ứng với thành phần **đã dự báo được**"; gọi nó là "tác động của cú sốc" vẫn vi phạm #9 y như đưa level trần vào hồi quy. Cái này phải mã hóa như `shock_axis.gate_shock_eligibility`, không để trong văn bản — văn bản không chặn được ai.

### 2.3. Tương tác với ACT/THREAT

Bài tìm thấy: **threats** tác động qua thành phần dự báo được; **acts** chỉ tác động khi bất ngờ. Đây là tương tác 2×2 giữa trục component và trục ACT/THREAT — cả hai dự án đều đã có.

Spec đầy đủ: 4 regressor (threat-persistent, threat-shock, act-persistent, act-shock). Đăng ký cùng id với §2.2.

---

## 3. VIỆT NAM MỞ KHÓA SỚM — RÚT NGẮN LỚN NHẤT

Chỉ số quốc gia gán ba vai: `initiator` · `respondent` · `spillover`. **VN gần như luôn là spillover** — chịu sốc năng lượng, gián đoạn thương mại, không phải bên khởi phát.

**⛔ ĐÍNH CHÍNH v1.2 (2026-08-05) — toàn bộ tiền đề của mục này SAI.** Bản v1.1 viết "Country index là **daily**" và dùng đúng câu đó để kết luận "gỡ ràng buộc #10". Đối chiếu với trang download thật (không phải suy luận): file là **`ai_gpr_country_monthly.csv`** — monthly, không phải daily. Tên file tự nói lên granularity, không cần tải mới biết. Hệ quả:

- **"Gỡ ràng buộc #10" RÚT LẠI.** CLAUDE.md #10 vẫn cấm daily backtest VN dùng series nước ở mức tháng (`GPRC_VNM`) — `ai_gpr_country_monthly.csv` cùng granularity, KHÔNG mở thêm gì cho track daily. Ba lối ra #10 liệt kê ("AI-GPR daily, bilateral daily, hoặc corpus báo Việt") — lối "AI-GPR daily" **không tồn tại** ở mức nước (chỉ tồn tại ở mức headline/threat/act/oil-vùng, không có breakdown theo nước). `vn_market_series_missing` **không phải** blocker duy nhất còn lại như v1.1 nói — track daily của Country Transmission VN vẫn treo y như trước khi có AI-GPR.
- **`build_monthly_panel` KHÔNG cần đường song song daily** như v1.1 đề xuất — đề xuất đó dựa trên tiền đề sai, không code theo.
- **Cái THẬT sự nâng cấp được: track THÁNG.** `ai_gpr_country_monthly.csv` (200 nước × 4 vai: all/initiator/respondent/spillover) thay `GPRC_VNM` bằng series có phân vai sẵn — khớp thẳng vào vai trò `spillover` mà VN gần như luôn ở đó, không cần tự suy ra vai trò như trước. Đây vẫn là nâng cấp thật cho tier3 VN monthly, chỉ là **không** phải daily như v1.1 tuyên bố.
- Corpus tiếng Việt: giữ nguyên đánh giá của v1.1 — đổi vai từ "điều kiện để λ có ý nghĩa" xuống "nâng cấp λ + nuôi khối phản ứng chính sách" (docs/14 §5). Nhận định này không phụ thuộc vào granularity nên không đổi.

**Việc còn treo:** chưa tải `ai_gpr_country_monthly.csv` để xác minh schema thật (cùng nguyên tắc §1 — không đoán cột). `vn_market_series_missing` (cần VNINDEX) vẫn là một trong các blocker, cùng với việc track daily VN vẫn chưa có lối ra nào mới.

---

## 4. HAI CỔNG NỚI ĐƯỢC

**4.1. Contamination (docs/14 §3.1) — nới cho tầng bài báo, GIỮ cho chân B.**

Bài chạy đúng bài kiểm tra §3.1.2 đề xuất: prompt neo ngày, ép model coi như không biết gì sau đó. Kết quả gần như không đổi — tương quan 0.95, sai khác tuyệt đối trung bình 0.02, và lệch nhỏ theo hướng *ngược* với inflation.

→ Với **chấm cường độ rủi ro trong văn bản**, contamination không phải rủi ro vật chất. Nới quy tắc "chỉ claim dự báo trên post-cutoff" cho tầng này.

→ **GIỮ NGUYÊN cổng cho trường `commitment` của chân B.** Chấm "lời đe dọa này có nghiêm túc không" là dự đoán kết cục, khác hẳn "bài này nói về rủi ro mức nào". Bài không kiểm thứ đó. Và chính họ ghi caveat: ra lệnh cho model rằng nó không biết tương lai **không xóa** kiến thức đó khỏi tham số.

**→ Với codebase hiện tại, §4.1 gần như KHÔNG có việc phải làm.** Phần được nới là tầng chấm tin tức — mà §7 cắt luôn tầng đó, và `scoring/statement_scorer.py` vốn chỉ chấm **phát ngôn sơ cấp** (chân B), trong đó có `commitment` — tức đúng phần §4.1 giữ nguyên cổng. Nên: `training_cutoff` **vẫn bắt buộc**, prompt giữ nguyên quy tắc contamination. Ghi ra đây để không ai đi nới nhầm cổng của chân B nhân danh mục này.

**4.2. Model deprecation (docs/14 §7.2-ii) — đã có lời giải.**

Llama 3.1 8B Instruct tương quan **0.91** với GPT-4o mini (cao hơn cả GPT-4o ở 0.90). Yêu cầu "model local pin cứng cho track record" khả thi với model 8B chạy quantized — không cần Qwen3-14B.

---

## 5. RECALIBRATION BẮT BUỘC — AI-GPR KHÔNG CÙNG HÌNH DẠNG VỚI GPRD

| | AI-GPR | GPR gốc |
|---|---|---|
| Độ lệch chuẩn | 48.5 | 60.6 |
| Skewness | 1.64 | 1.97 |
| Phân vị 1 | 42.0 | 18.1 |
| Phân vị 99 | 267 | 300 |
| Tự tương quan 90 ngày | **0.73** | 0.62 |

**Mượt hơn, dai hơn, đuôi phải mỏng hơn, không có ngày nào bằng 0.**

Hệ quả cho code hiện có:
- **`JUMP` phải hiệu chuẩn lại.** Ngưỡng q95/q99 rolling trên chuỗi đuôi mỏng hơn sẽ cho phân phối JUMP khác hẳn. Toàn bộ thiết kế trigger theo đuôi (docs/14, docs/15) cần chạy lại phân vị.
- **Dai hơn củng cố §2.2:** tự tương quan cao hơn → phần dự báo được lớn hơn → càng không nên vứt nó đi.
- E1/E1b/E1c chạy trên GPRD, **không tự động chuyển sang AI-GPR**. Thêm `pipeline_note` như đã làm với các report cũ.

---

## 6. BENCHMARK BATTERY — THÊM MỘT MỨC KHÓ

docs/14 §2.1a: battery hiện là GPR + EPU + WUI. **Thêm AI-GPR.**

Hệ quả cho KĐ8: chân B phải chứng minh thêm thông tin ngoài **cả AI-GPR** — bao gồm threats/acts và bilateral của họ. Đây là mức khó hơn hẳn, và là mức đúng: nếu S-GPR không thêm gì ngoài chuỗi miễn phí của Fed thì không có lý do bán.

---

## 7. CẮT KHỎI KẾ HOẠCH

| Bỏ | Vì |
|---|---|
| Xây LLM scoring cho tin tức (chân A) | Đã có, tốt hơn, miễn phí |
| Tự phân loại kênh energy từ tin | Oil GPR × 13 vùng đã có |
| Tự dựng country sub-index | 200 nước đã có |
| V-phase corpus như điều kiện tiên quyết của tier3 VN | Spillover thay được ở v0 |

Ngân sách backfill $100–250 (docs/14 Phase 2c) **chỉ còn cho chân B**, không cho tin tức.

---

## 8. CÒN LẠI GÌ LÀ CỦA MÌNH — HẸP HƠN, SẮC HƠN

| | AI-GPR | Của mình |
|---|---|---|
| Nguồn | báo chí (thứ cấp) | **phát ngôn sơ cấp**, `published_at` đến phút |
| Thang | 0→1 đơn cực | **±1.0 lưỡng cực** — ngừng bắn/nhượng bộ đo được |
| Chiều | intensity | + `commitment`, `specificity`, `actor_weight` |
| Đầu ra | trang dữ liệu nghiên cứu | **sản phẩm**: card, brief, analogue, track record |
| Nước | 200 nước generic | **VN**: β/θ/λ, biên độ 7%, khối chính sách |

Bốn dòng đó là toàn bộ định vị còn lại. Đủ để đứng, nhưng không còn "chúng tôi xây mô hình GPR" — mà là "chúng tôi đo phát ngôn sơ cấp và truyền dẫn nó vào vĩ mô VN, trên nền chỉ số tốt nhất hiện có".

---

## 9. VIỆC THÊM VÀO LỘ TRÌNH

**Phase 1 (chèn trước 1a):**
- [x] **`load_ai_gpr_daily()` + `describe_ai_gpr_file()` + `ai_gpr_vintage()`** — xong 2026-08-03. File **tải tay** theo khuôn `wui_global.csv`; thiếu file → lỗi kèm hướng dẫn, thiếu cột → raise (không lặng lẽ bỏ qua). ⚠️ `AI_GPR_COLUMNS` là schema **giả định**, phải đối chiếu bằng `describe_ai_gpr_file()` lần tải đầu.
- [x] **Spec kép §2.2 — phần code**: `shocks.delta_decomposition` (SURPRISE ≡ `innovation()` đã có; hai thành phần cộng lại bằng **đúng** Δ LEVEL) + `standardized_contribution` + cổng nhãn `shock_axis.check_component_labelling`. 11 test.
- [x] **E2 diagnostic** — `docs/reports/E2_component_decomposition_e73a0a307fc3.md`, đã dùng để sửa §2.1.
- [ ] ⛔ **Tải dữ liệu AI-GPR + xác minh ghim vintage được** ← *chặn tất cả những mục dưới*
- [ ] Hiệu chuẩn lại phân vị/JUMP trên AI-GPR (`MONTHLY_JUMP_WINDOW` đang hiệu chuẩn cho GPRD)
- [ ] Chạy spec kép trên dữ liệu thật; LEVEL/INNOVATION/LEVEL+JUMP xuống robustness
- [ ] Thêm AI-GPR vào battery
- [ ] Chạy lại E2 trên AI-GPR (§2.1 giới hạn: E2 hiện chạy GPRD tháng)

**Phase 3 (kéo lên sớm):**
- [ ] tier3 VN dùng country/bilateral spillover — chờ VNINDEX **và** dữ liệu AI-GPR

**Phase 2 (thu hẹp):**
- [x] Cổng contamination: **không có việc phải làm** — xem §4.1, phần nới áp cho tầng đã bị §7 cắt
- [ ] Bỏ phần news scoring khỏi kế hoạch (không có code để xóa — `statement_scorer` vốn chỉ chấm phát ngôn sơ cấp)
- [ ] Scorer track-record = Llama 3.1 8B local (`LLMClient` đã là tiêm-vào, không cần đổi kiến trúc)

**Governance đã ghi:** `DEC-2026-08-03-dual-component` trong registry — amend `DEC-2026-08-02-shock-axis` (trục SHOCK: chính → robustness), **giữ nguyên** điều kiện `lag_augmented`. `SCA-01.primary_cell.shock` **vẫn UNRESOLVED**, khóa bằng `test_dual_component_keeps_primary_cell_unresolved`.

**Không đổi:** guard sup-t, cổng `shock_axis`, `vn_market_series_missing`, cổng contamination của chân B (§4.1).

### 9.1. ⛔ Va chạm governance — §2.2 SỬA một chữ ký đã ký

Bản v1.0 ghi "không đổi: **ba** chữ ký §6 docs/14". Sai hai chỗ:

1. Có **bốn** quyết định đã ký ngày 2026-08-02, khóa máy ở `config/hypothesis_registry.yaml` mục `decisions:` + `tests/test_registry_locked.py::test_signed_decisions_locked`.
2. §2.2 **có** đụng một cái: `DEC-2026-08-02-shock-axis` chốt SHOCK là **trục báo cáo chính** với `SCA-01.primary_cell.shock` = UNRESOLVED (chờ E1c-exo). §2.2 hạ trục đó xuống robustness và chốt ô chính bằng spec kép. Đó là **sửa quyết định đã ký**, không phải bổ sung.

**Thủ tục bắt buộc, làm trong CÙNG một commit** (nếu không `test_signed_decisions_locked` đỏ — đó là tính năng):
- Thêm `DEC-2026-08-03-dual-component` vào `decisions:`, ghi rõ nó **amend** `DEC-2026-08-02-shock-axis` ở điểm nào (trục SHOCK: chính → robustness) và **giữ nguyên** điểm nào (điều kiện `lag_augmented` cho LEVEL/LEVEL+JUMP vẫn còn hiệu lực).
- Cập nhật `LOCKED_DECISION_IDS` trong `tests/test_registry_locked.py`.
- Đăng ký giả thuyết **id mới** cho spec kép (AR order riêng, không đụng 5/5/2 đã khóa).
- `primary_cell.shock` chuyển từ `UNRESOLVED` sang spec kép **chỉ khi** chấp nhận rằng nó được chốt bằng *thiết kế* chứ không bằng E1c-exo — và phải ghi ra, vì lý do ban đầu để nó UNRESOLVED là tránh chốt bằng thẩm quyền.