# 13 — KẾ HOẠCH GIAI ĐOẠN E1c → LƯỚI SCA

**Phiên bản:** 1.0 — 2026-07-19
**Trạng thái repo tham chiếu:** `a3535f6`
**Quan hệ tài liệu:** nối tiếp `11_product_plan.md` §10 (track E) và `12_specification_curve_protocol.md`. Doc này **sửa** ô chính của `SCA-01` và **bổ sung** một mức vào chiều SHOCK — cả hai đều phải xong trước khi lưới chạy.
**Dùng để làm gì:** mở ra và viết code theo. §2 là spec E1c, §5 là trình tự thi công.

---

## 0. TÓM TẮT: VÌ SAO CÓ DOC NÀY

E0 headline PASS xác nhận loader + LP/HAC theo timing của paper (β=−0.37, p=0.008 tại h=2 tháng, IP giảm). E0 alignment diagnostic cũng đã PASS tại cặp neo raw h=2 → aligned h=1 (`docs/reports/E0_alignment_diagnostic_e73a0a307fc3_c93a877.md`), nên blocker timing M+1 đã gỡ.

Nhưng khi rà `E1b_shock_ranking_8cc9bfb5c3b6.md`, phát hiện một vấn đề **chặn lưới**: E1b xếp hạng thước đo shock bằng một định nghĩa episode nội sinh với chính GPRD, nên ranking phần lớn do cấu tạo quyết định chứ không do dữ liệu. Mà E1b vừa chốt `SCA-01.primary_cell.shock = LEVEL+JUMP` — một trường **không sửa được sau khi thấy kết quả lưới**.

Doc này đặc tả E1c để thay thế, và dọn ba việc governance còn nợ.

---

## 1. VẤN ĐỀ VỚI E1b

### 1.1. Định nghĩa episode nội sinh với thước đo

E1b định nghĩa episode lớn là `GPRD > phân vị 0.975 rolling(250)`, rồi xếp hạng các thước đo theo giá trị của chúng **tại chính những ngày đó**.

| Thước đo | Quan hệ với GPRD | Hệ quả tại ngày episode |
|---|---|---|
| `LEVEL` | biến đổi đơn điệu | chưa có trong E1b cũ do bug implementation |
| `JUMP` = max(0, z − q95) | dương khi z vượt q95 | dương **theo định nghĩa** (97.5 > 95) |
| Nhãn `LEVEL+JUMP` trong report cũ | thực tế là `INNOVATION+JUMP` | được cộng chính thành phần JUMP mà episode bảo đảm cao |
| `INNOVATION` = LEVEL − AR(5) | **cố ý không** đơn điệu | không có lý do gì để cao |

Ranking thực tế của artifact cũ là `INNOVATION+JUMP > JUMP > INNOVATION`: thêm JUMP thì
thắng trong khi episode đã được định nghĩa bằng ngưỡng q97.5 và JUMP bật từ q95. Vì vậy
kết quả vẫn circular, nhưng không phải bằng chứng về LEVEL. `LEVEL` thật chỉ xuất hiện
từ lần chạy E1c-endo mới sau khi sửa contract. Report E1b gọi đây là "thiên vị nhẹ" —
**nó không nhẹ, cơ chế JUMP là phần quyết định của ranking.**

Nguyên tắc vi phạm (Ludvigson, Ma & Ng): các ràng buộc nhận dạng buộc một quan hệ phải đúng theo cấu tạo thì không hữu ích, vì chúng đòi hỏi kết luận phải thành lập ngay từ thiết kế.

### 1.2. Ngưỡng 2σ không so được giữa các thước đo

Vấn đề thứ hai, **độc lập** với 1.1:

- `JUMP` bằng 0 trên ~95% số ngày theo cấu tạo (`max(0, z − q95_rolling)`). Độ lệch chuẩn của chuỗi 95% là số 0 rất nhỏ → mọi giá trị khác 0 nhận z rất lớn.
- `INNOVATION` xấp xỉ đối xứng quanh 0 → 2σ ở đó là đuôi thật.

"Tỉ lệ episode vượt 2σ" đang so hai đại lượng khác bản chất. Lệch **cùng chiều** với 1.1.

### 1.3. Vì sao phải xử lý TRƯỚC khi chạy lưới

`primary_cell` của `SCA-01` là trường đăng ký trước, **không sửa được sau khi thấy kết quả lưới** — sửa sau là dò. Chọn nó bằng một chẩn đoán gần tautological là lỗi governance, không phải lỗi kỹ thuật.

### 1.4. Cái gì của E1b vẫn giữ

- Cơ chế E1 (AR(p) nén cú sốc khi level tăng dần trước cú nhảy) **vẫn đúng** — đó là quan sát trực tiếp trên chuỗi PERSISTENT, không phụ thuộc định nghĩa episode.
- Kỷ luật report (versioned, metadata, không chạm holdout, không hồi quy outcome để tránh circular với lưới) **giữ nguyên cho E1c**.
- E1b **không bị rút** — giữ trong `docs/reports/` như bản ghi. E1c là bản bổ sung, và report E1c phải nêu rõ vì sao kết luận đổi.

---

## 2. SPEC E1c

> **Đính chính implementation 2026-07-19:** report E1c-endo hiện có là artifact lịch
> sử, chưa được dùng làm bằng chứng. Code cũ gắn nhãn `LEVEL+JUMP` nhưng tính
> `INNOVATION+JUMP`. Contract đã khóa thành `LEVEL+JUMP := LEVEL + JUMP`; phải chạy
> lại E1c-endo trước E1c-exo và trước mọi quyết định `primary_cell.shock`.

### 2.1. Câu hỏi

Thước đo shock nào phát hiện đúng các cú sốc địa chính trị lớn, khi tập sự kiện được xác định **độc lập với GPRD**?

### 2.2. Sự kiện ngoại sinh

Đây là cách chuẩn trong văn liệu: phương pháp tường thuật dựng chuỗi cú sốc từ việc đọc lại các sự kiện chính trị và kinh tế trong lịch sử (cú sốc dầu theo mốc chiến tranh, cú sốc tiền tệ từ đọc biên bản FOMC), rồi dùng như biến ngoại sinh.

**Nguồn:** gold set dựng tay mà `docs/11` §14 đã yêu cầu (~50 sự kiện lớn 2018–2026). Mở rộng ngược tới 1990 bằng niên biểu công khai nếu cần mẫu lớn hơn.

**Quy tắc dựng — chốt trước khi nhìn bất kỳ chuỗi GPR nào:**

- Tiêu chí đưa vào ghi ra trước, dạng liệt kê (xung đột vũ trang giữa các quốc gia; tấn công vào hạ tầng năng lượng/hàng hải; áp đặt trừng phạt hoặc thuế quan quy mô lớn; đảo chính/khủng hoảng chính trị ở nước G20 hoặc nước xuất khẩu dầu lớn; leo thang hạt nhân)
- Ngày sự kiện = ngày **sự kiện xảy ra**, không phải ngày báo chí đưa tin
- **Không** tra GPRD để quyết định một sự kiện có "đủ lớn" không
- Hai người dựng độc lập, hợp nhất, ghi lại các bất đồng
- Lưu thành `data/gold_events.csv` với `event_date`, `category`, `sources`, `builder`, `agreed`

> ⚠️ Nếu tập sự kiện được lọc bằng GPRD ở bất kỳ khâu nào, E1c thừa hưởng đúng lỗi của E1b. Đây là ràng buộc quan trọng nhất của doc này.

### 2.3. Thống kê: AUC (Mann–Whitney)

$$\text{AUC}_m = P\big(m_t > m_s\big), \quad t \in \text{event days},\ s \in \text{non-event days}$$

Xác suất thước đo $m$ tại một ngày sự kiện cao hơn tại một ngày ngẫu nhiên không phải sự kiện.

**Vì sao AUC:** bất biến với mọi biến đổi đơn điệu của phân phối biên → **miễn nhiễm với cả zero-inflation của JUMP lẫn skew của LEVEL**. Đây là thứ ngưỡng 2σ không làm được (§1.2).

**Chi tiết thực thi:**
- Cửa sổ sự kiện: ngày sự kiện $\pm 1$ phiên (tính cả lệch múi giờ và publish lag) — chốt trước, không dò
- Loại khỏi nhóm "không sự kiện": $\pm 10$ phiên quanh mọi sự kiện (vùng đệm, tránh nhiễm)
- CI: bootstrap phân tầng theo năm, B=2000
- Báo cáo theo full sample và từng sub-sample (pre-2008 / 2008–2015 / post-2015)
- AUC = 0.5 là ngẫu nhiên; báo cáo cả khoảng cách so với 0.5 và CI

### 2.4. Thước đo đưa vào — thêm `LEVEL` thuần

| Thước đo | Có trong E1b? | Trong lưới `docs/12`? |
|---|---|---|
| `INNOVATION` | ✅ | ✅ |
| `JUMP` | ✅ | ✅ |
| `LEVEL+JUMP` | ✅ | ✅ |
| **`LEVEL` thuần** | ❌ | ❌ ← **thiếu ở cả hai** |

`LEVEL` thuần là spec headline của Caldara–Iacoviello, và **E0 vừa cho nó kết quả có ý nghĩa** (β=−0.37, p=0.008). Theo tiêu chí của chính SSN2020 — có cơ sở lý thuyết, hợp lệ thống kê, không trùng lặp — nó đủ điều kiện. Đây là spec duy nhất đã chứng minh được, mà lại không nằm ở đâu cả.

*Phản biện dự kiến:* LEVEL dai dẳng nên IRF từ nó không diễn giải sạch như impulse response. **Đúng** — nhưng đó là lý do để ghi chú diễn giải, không phải lý do loại khỏi curve.

### 2.5. Phép thử tự bác bỏ (bắt buộc chạy)

Chạy **song song hai bản**:

| Bản | Định nghĩa episode | Mục đích |
|---|---|---|
| E1c-endo | GPRD > q97.5 rolling (như E1b) | đối chứng |
| E1c-exo | gold set ngoại sinh | kết quả thật |

**Đọc kết quả:**

- `LEVEL` thuần **thắng tuyệt đối ở bản endo** → xác nhận chẩn đoán kiểu E1b đo tính đơn điệu theo GPRD chứ không đo sức phát hiện. Lập luận §1.1 đúng, bản exo là bản dùng.
- `LEVEL` thuần **không thắng ở bản endo** → lập luận §1.1 sai hoặc yếu hơn tôi nghĩ. Ghi lại, và trọng số của E1b tăng lên.

Tốn thêm gần như bằng không, và nó kiểm định chính lập luận đã dựng nên doc này. Không chạy bản endo = tự miễn cho mình khỏi bị bác bỏ.

### 2.6. Ràng buộc kế thừa từ E1b

- KHÔNG chạm holdout
- KHÔNG hồi quy outcome macro (tránh circular với lưới SCA)
- Report versioned, `FileExistsError` chặn ghi đè
- Metadata: `data_version`, git commit, `generated_at`, seed, B, phiên bản gold set
- **Guard P1**: mọi số trong narrative tính từ `stats`, không hard-code

> Nhắc lại lỗi đã xảy ra: `run_e1_diagnosis.py` ghi "~1.8×" trong khi hai trường tính được cho 1.07/0.386 = **2.77×**. Test tự động phải chặn được loại này.

### 2.7. Đầu ra

- `docs/reports/E1c_shock_detection_<data_version>_<git_commit>.md`
- `docs/reports/figs/` — AUC + CI theo thước đo × sub-sample, hai bản endo/exo cạnh nhau
- `data/gold_events.csv` (versioned)
- `tests/test_e1c_detection.py` — test logic AUC không gọi mạng (giống cách `test_e0_replication.py` đã làm)

---

## 3. QUYẾT ĐỊNH Ô CHÍNH SAU E1c

| Kết quả E1c-exo | Hành động |
|---|---|
| Một thước đo thắng rõ, ổn định qua sub-sample, CI không chồng lấn | Chốt `primary_cell.shock` = thước đo đó |
| AUC chồng lấn / không ổn định qua sub-sample | **Để SHOCK mở** — xem §3.1 |

### 3.1. Phương án "SHOCK mở" — hợp lệ, không phải thất bại

Toàn bộ tiền đề của SCA: specification curve cho phép cam kết trước sẽ chạy toàn bộ tập spec, thay vì **cam kết mù quáng** vào một kết luận khi các phân tích hợp lệ bất đồng.

Nếu E1c không phân biệt được, chỉ định ô chính trên ba chiều **có cơ sở lý thuyết vững**:

```
FREQ_OUTCOME = tháng × vĩ mô thực    # C-I 2022, Brignone, ECB LGPT, + E0 PASS
FUNCFORM     = quantile τ=0.10        # Brignone (phi tuyến ở đuôi), C-I (rủi ro đuôi dưới)
CHANNEL      = tách ACT/THREAT        # ECB LGPT (energy vs trade ngược dấu ở lãi suất)
JUMP_THRESH  = q95
SAMPLE       = đầy đủ
SHOCK        = MỞ — báo cáo cả 4 mức, dashboard chart cho biết nó có hệ trọng không
```

**Hiệu chỉnh Holm khi SHOCK mở:** bốn ô chính (một cho mỗi mức SHOCK), Holm trên $4 \times H$ thay vì $H$. Ghi rõ trong registry.

---

## 4. BA VIỆC GOVERNANCE CÒN NỢ

`SCA-01.blockers` hiện còn các cổng E1c/gold set trước khi chạy lưới; E0 alignment đã PASS.

### 4.1. Quyết định holdout — tách chính sách theo track

**Số học quyết định vấn đề, không phải A/B/C:**

| | 2026-H1 cho ra bao nhiêu quan sát dùng được |
|---|---|
| Track ngày, h=30 | ~95 phiên — **dùng được** |
| Track tháng, h=1 | ~5 tháng |
| Track tháng, h=6 | **0** |
| Track tháng, h=24 (ô chính) | **0** |

Tại horizon $h$, cú sốc cuối dùng được là (ngày cuối dữ liệu − $h$). Dữ liệu kết thúc ~2026-06 → với h=6 sốc phải trước 2025-12; toàn bộ 2026-H1 đóng góp **bằng không**. Ô chính là tháng × h=0..24 → **holdout rỗng theo cấu tạo**.

A/B/C đều giả định holdout là lát cắt thời gian có thể tranh luận về *chất lượng*. Vấn đề không phải chất lượng, là **không tồn tại**.

**Quyết định đề nghị, ghi vào `g0_governance.md` §2:**

| Track | Chính sách | Lý do |
|---|---|---|
| **Ngày** | Giữ `final_holdout: 2026-01-01…2026-06-30`, chạm ĐÚNG 1 LẦN, báo cáo kèm cảnh báo chế độ đơn lẻ | ~95 quan sát dùng được. Giả thuyết đang test là giả thuyết **đuôi** → cửa sổ chứa sự kiện đuôi lớn nhất lịch sử là **đúng loại dữ liệu**, không phải sai loại |
| **Tháng** | **Chưa có holdout.** Pseudo-OOS 2024–2025 là trần bằng chứng. Claim ceiling = `predictive, chưa xác nhận holdout`. Hoãn final holdout tới khi đủ ~24 tháng dữ liệu hậu 2026 (≈2028-H2) | Holdout rỗng theo cấu tạo (bảng trên) |

**Vì sao KHÔNG dời holdout sang 2026-H2** (phương án B/C cũ): ở đó (a) không có sự kiện đuôi để test giả thuyết đuôi, và (b) `jump()` dùng sd + ngưỡng q95 rolling 250 phiên nên JUMP **bị nén cơ học** đúng khoảng đó. Test giả thuyết đuôi trên mẫu không có đuôi, bằng thước đo đang bị bóp, mà vẫn tiêu mất lần chạm duy nhất.

**Trần claim thấp hơn có chấp nhận được không?** Có — `docs/11` §13.3 đề nghị **bỏ tín hiệu giao dịch**, và đó là use case duy nhất thực sự đòi hỏi bằng chứng cấp holdout. Sản phẩm phân phối + đo lường chỉ cần pseudo-OOS + tính bền qua specification curve + danh sách episode kiểm chứng được. Trần thấp hơn không hỏng sản phẩm; nó chỉ phải được **ghi ra** thay vì ngầm hiểu.

**Về holdout theo episode:** có cân nhắc thay holdout theo lịch bằng holdout theo tập episode để có đủ quan sát đuôi. **Không đề nghị** — việc chọn episode nào giữ lại tự nó là một bậc tự do mới, không khóa đủ chặt để đáng đánh đổi. Đánh giá trung thực hơn: sự kiện đuôi quá hiếm để bất kỳ holdout nào có power. Nói thế trong report, thay vì dựng cơ chế trông nghiêm ngặt mà không xác nhận được gì.

### 4.2. Thêm `LEVEL` vào chiều SHOCK của lưới

`docs/12` §2.1 dòng 54: `INNOVATION · JUMP · LEVEL+JUMP` → thêm `LEVEL`.

Lưới: 4 × 2 × 6 × 2 × 2 × 2 = **384 spec** (trước khi loại trùng lặp).

Ghi lý do vào registry: *"Thêm sau E0 PASS — LEVEL thuần là spec headline C-I 2022 và là spec duy nhất đã cho kết quả có ý nghĩa trong pipeline này. Thêm TRƯỚC khi lưới chạy."* Mốc thời gian quan trọng: thêm sau khi thấy kết quả lưới sẽ là dò.

### 4.3. Sửa ba chỗ trong `docs/12`

**Tham chiếu sai:** `docs/11` §8 **không hề chứa** Romano–Wolf (đã kiểm). Nó được nói trong hội thoại, chưa bao giờ viết vào doc 11.

Dòng 5 — bỏ mệnh đề `Thay thế đề xuất "hiệu chỉnh Romano–Wolf" ở doc 11 §8 — xem §1.2.`

Dòng 30 — thay bằng:
> **Hiệu chỉnh đa kiểm định kiểu Bonferroni/Holm/Romano–Wolf không phải khung phù hợp cho họ lưới; doc này thay thế cách tiếp cận đó. Holm vẫn áp cho họ horizon trong ô chính (§5.2).**

Dòng 293–294 — thay bằng:
```yaml
  supersedes_note: >
    Suy diễn cho họ lưới dùng SCA thay vì hiệu chỉnh đa kiểm định. Holm vẫn áp
    cho họ horizon trong ô chính. Không thay thế mục nào của docs/11.
```

Dòng 267 — điền `protocol_commit` bằng hash thật.

### 4.4. Trôi nhỏ: `config/backtest.yaml`

File viết hoàn toàn cho use case alpha (`metrics_horizons_days`, cổng G3, deflated Sharpe, Hansen SPA, danh sách benchmark). Nếu chốt bỏ tín hiệu giao dịch (`docs/11` §13.3), đánh dấu file **ngủ đông** kèm ghi chú rằng split 4 tầng trong đó **vẫn còn hiệu lực** cho track econometrics. Để nguyên không ghi chú thì sáu tháng nữa sẽ có người tưởng G3 đang chờ.

---

## 5. TRÌNH TỰ THI CÔNG

### 5.1. Đường găng (tuần tự thật)

```
gold_events.csv  →  E1c  →  chốt primary_cell.shock (hoặc để mở)  →  LƯỚI SCA
```

**Gold set giờ nằm trên đường găng**, không còn là việc phụ. Nó chặn E1c, E1c chặn ô chính, ô chính chặn lưới.

Gold set phục vụ **hai** mục đích, nên đằng nào cũng phải làm: đầu vào E1c (§2.2) và metric "phát hiện" của sản phẩm (`docs/11` §11).

**Ràng buộc nhân sự:** gold set cần 2 người dựng độc lập (§2.2). Cùng ràng buộc với G-B1 (Krippendorff α). Giải một lần, dùng cho cả hai.

### 5.2. Song song, không chặn

| Việc | Ghi chú |
|---|---|
| `build_monthly_panel()` | **Đã tồn tại và có test.** GPR tháng M được canh vào bucket M+1; chưa xử lý rolling orthogonalization/vintage ở Phase 2 |
| Ingest cước vận tải biển | Biến tầng 2 mới (`docs/11` §5.3) |
| Ba việc governance §4.1–4.3 | Quyết định + sửa doc, không phụ thuộc E1c |
| `panel_var.py` block-exogenous + Granger test khối | Track VN, độc lập |

### 5.3. Sau khi hết chặn

Xây lưới SCA theo `docs/12`: moving-block bootstrap (ℓ=12 tháng / 60 ngày, B=1000), ba thống kê T1/T2/T3, dải sup-t, descriptive + inferential curve, dashboard chart.

---

## 6. CỔNG

| Cổng | Điều kiện |
|---|---|
| **G-Gold** | Gold set ≥40 sự kiện, 2 người dựng độc lập, bất đồng ghi lại, không dùng GPRD để lọc |
| **G-E1c** | AUC + CI cho 4 thước đo × 4 sub-sample, cả bản endo và exo. Phép thử §2.5 đã chạy |
| **G-Primary** | `primary_cell.shock` chốt **hoặc** để mở có lý do ghi rõ; registry cập nhật |
| **G-Gov** | §4.1–4.3 xong: holdout ghi `g0`, LEVEL vào lưới, `docs/12` sửa + `protocol_commit` điền |
| **G-Panel** | `build_monthly_panel()` viết xong + test |
| → | **Lưới SCA được phép chạy** |

---

## 7. RỦI RO

| Rủi ro | Mức | Xử lý |
|---|---|---|
| **Gold set bị nhiễm bởi GPRD** (người dựng tra chỉ số để quyết định "đủ lớn") | 🔴 | Quy tắc §2.2 ghi trước; người dựng không có quyền truy cập chuỗi GPR trong lúc dựng |
| E1c cũng không phân biệt được các thước đo | 🟡 | Đã có phương án: SHOCK mở (§3.1). Hợp lệ, không phải thất bại |
| Gold set quá ít sự kiện → AUC CI rộng | 🟡 | Mở rộng ngược tới 1990 bằng niên biểu công khai; hoặc chấp nhận CI rộng và ghi rõ |
| Lập luận §1.1 của tôi sai | 🟡 | Chính xác là thứ §2.5 kiểm định. Nếu sai, E1b đứng vững và ô chính giữ nguyên |
| Thêm `LEVEL` bị coi là nới lỏng sau khi thấy E0 | 🟡 | Thêm **trước** khi lưới chạy, ghi lý do + mốc thời gian vào registry. Đây là ranh giới hợp lệ/dò |
| Trần claim track tháng làm yếu sản phẩm | 🟢 | Đã phân tích §4.1 — sản phẩm phân phối không cần bằng chứng cấp holdout |

---

## 8. VIỆC TUẦN NÀY

- [ ] Chốt quy tắc dựng gold set (§2.2), bắt đầu dựng — **đường găng**
- [ ] Ba việc governance §4.1–4.3 (quyết định + sửa doc, không cần chờ gì)
- [x] `build_monthly_panel()` — đã viết, test và canh information-time M→M+1
- [ ] Viết `scripts/run_e1c_shock_detection.py` khung + test AUC (chạy được ngay khi có gold set)
