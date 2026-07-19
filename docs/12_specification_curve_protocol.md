# 12 — GIAO THỨC SPECIFICATION CURVE (PRE-REGISTRATION)

**Phiên bản:** 1.2 — 2026-07-19 (khóa horizon theo E0/G2a; khóa weekend aggregation theo loại shock; thêm E0 aligned diagnostic)
**Trạng thái:** 🔒 ĐĂNG KÝ TRƯỚC. Doc này phải được commit và ghi vào `config/hypothesis_registry.yaml` **TRƯỚC** khi chạy bất kỳ ô nào của lưới. Commit hash của doc này là bằng chứng thời điểm.
**Quan hệ tài liệu:** thực thi §2 và §5 của `11_product_plan.md`. Ràng buộc governance: `g0_governance.md`. Suy diễn cho họ lưới dùng SCA thay vì hiệu chỉnh đa kiểm định (Bonferroni/Holm/Romano–Wolf) — xem §1.2. Không thay thế mục nào của `docs/11`.
**Cơ sở phương pháp:** Simonsohn, Simmons & Nelson (2020), *Nature Human Behaviour* 4:1208–1214 — Specification Curve Analysis (SCA). Suy diễn LP: Montiel Olea & Plagborg-Møller (2021), *Econometrica* 89:1789–1823; dải đồng thời: Montiel Olea & Plagborg-Møller (2019), *JAE* 34:1–17.

---

## 1. VÌ SAO SCA, KHÔNG PHẢI HIỆU CHỈNH ĐA KIỂM ĐỊNH

### 1.1. Vấn đề

Sau G2a có **ba lời giải thích cạnh tranh** cho kết quả gần null:

| # | Lời giải thích | Chiều/trục tương ứng |
|---|---|---|
| A | Sai thước đo shock (INNOVATION bị AR(5) nén) | SHOCK (chiều lưới) |
| B | Sai TẦN SUẤT (ngày thay vì tháng) và/hoặc sai BIẾN ĐÍCH (giá tài sản thay vì vĩ mô thực) | FREQ (chiều lưới) **×** outcome (trục báo cáo) — **tách riêng** sau §2.1 |
| C | Sai dạng hàm (tuyến tính & trung bình thay vì phi tuyến & đuôi) | FUNCFORM (chiều lưới) |

**Hàng B tách được sau tái cấu trúc §2.1:** trước đây FREQ và biến đích gộp làm một mức
nên nếu dashboard chỉ ra biến thiên ở đó, KHÔNG biết do tần suất hay do biến đích. Giờ:
FREQ là chiều lưới, outcome là trục báo cáo → với oil/dxy/vix/us10y (có ở cả 2 tần suất),
giữ biến đích + đổi FREQ = kiểm định trực tiếp "tần suất có quan trọng không"; so curve
giữa các outcome = "biến đích có quan trọng không". Hai câu hỏi giờ trả lời tách bạch.

Chạy tuần tự thì mỗi thí nghiệm **lẫn hai chiều còn lại**: E2 sửa chiều A rồi test trên chiều B sai. Kết quả null của nó không phân biệt được "JUMP không có tác dụng" với "JUMP có tác dụng nhưng không ở tần suất ngày trên giá tài sản".

### 1.2. Vì sao đây không phải bài toán đa kiểm định

Hiệu chỉnh đa kiểm định (Bonferroni, Holm, Romano–Wolf) trả lời: *"có ô nào sống sót sau khi phạt không?"*

Câu hỏi thật của dự án là: *"**chiều nào** quyết định kết quả?"*

SCA trả lời câu thứ hai. **Hiệu chỉnh đa kiểm định kiểu Bonferroni/Holm/Romano–Wolf không phải khung phù hợp cho họ lưới; doc này thay thế cách tiếp cận đó. Holm vẫn áp cho họ horizon trong ô chính (§5.2).**

### 1.3. SCA giải quyết gì

SSN2020 nêu vấn đề gần trùng khít tình huống này: kết quả thực nghiệm phụ thuộc vào các quyết định phân tích vừa biện minh được, vừa tùy tiện, vừa có động cơ; sai số chuẩn quanh hệ số phản ánh sai số lấy mẫu của **một** phân tích cụ thể, nhưng không phản ánh sai số do việc chọn spec một cách tùy tiện hoặc có động cơ.

Quy trình ba bước: (1) xác định tập spec có cơ sở lý thuyết, hợp lệ thống kê và không trùng lặp; (2) trình bày kết quả bằng đồ thị để người đọc nhận ra quyết định nào là hệ trọng; (3) tiến hành suy diễn chung trên toàn bộ spec.

### 1.4. Vì sao SCA **chặt hơn** G0 hiện tại, không lỏng hơn

SSN2020: specification curve cho phép nhà nghiên cứu **cam kết trước sẽ chạy toàn bộ tập spec** mà họ coi là hợp lệ, thay vì chỉ một tập con nhỏ và tùy tiện như hiện phải làm. Với kế hoạch đăng ký trước truyền thống, nếu các phân tích hợp lệ khác nhau dẫn tới kết luận khác nhau thì nhà nghiên cứu bị buộc phải **cam kết mù quáng** vào một kết luận; specification curve cho phép học được kết luận phụ thuộc vào spec nào.

Tuần tự nghe an toàn hơn nhưng **cho phép dừng khi ra kết quả đẹp** — đó mới là snooping. Lưới đăng ký trước không có chỗ để dừng chọn lọc.

> **Nguyên tắc bất biến của doc này:** báo cáo TOÀN BỘ đường cong, bất kể kết quả. Không ô nào bị bỏ khỏi report. Vi phạm điều này làm vô hiệu toàn bộ giao thức.

---

## 2. TẬP SPEC

### 2.1. Các chiều và mức

> **Tái cấu trúc 2026-07-19 (review docs/13-hậu §1):** bản trước có chiều `FREQ_OUTCOME`
> gộp tần suất VÀ biến đích vào một mức. Đó là **khiếm khuyết thiết kế**: (1) specification
> curve là MỘT hệ số cho mỗi spec — mà "tác động lên VIX" và "tác động lên IP" là hai
> câu hỏi khác nhau, không phải hai spec của cùng câu hỏi; trộn chúng lên một curve là
> xếp cạnh nhau các hệ số không cùng đơn vị lẫn không cùng ý nghĩa kinh tế. (2) Gộp tần
> suất với biến đích khiến dashboard KHÔNG tách được "biến thiên do tần suất" khỏi "do
> biến đích" — mà đó chính là câu hỏi hàng B §1.1. **Sửa: outcome là TRỤC BÁO CÁO (một
> curve mỗi outcome), KHÔNG phải chiều lưới. Tách riêng FREQ thành một chiều.**

**Chiều lưới** (định nghĩa tập spec cho MỖI outcome × MỖI curve):

| Chiều | Mức | Cơ sở |
|---|---|---|
| **SHOCK** | `INNOVATION` · `JUMP` · `LEVEL+JUMP` · `LEVEL` | Contract khóa: `LEVEL+JUMP := LEVEL + JUMP` (không phải `INNOVATION + JUMP`). E1/E1b/E1c: AR(5) có thể nén cú sốc. `LEVEL+JUMP` cho sốc dai dẳng. `LEVEL` thuần **thêm sau E0 PASS 2026-07-19** — spec headline C-I 2022, spec DUY NHẤT đã có ý nghĩa (β=−0.37, p=0.008); thêm TRƯỚC khi lưới chạy (docs/13 §4.2) |
| **FREQ** | ngày · tháng | Tách khỏi biến đích. Cho outcome có ở CẢ hai tần suất (oil/dxy/vix/us10y) → hỏi được câu SẠCH: giữ biến đích, đổi tần suất — kết quả đổi không? = kiểm định trực tiếp giả thuyết B (§1.1). Real macro + freight chỉ có ở tháng → FREQ 1 mức (ragged trung thực) |
| **FUNCFORM** | OLS (trung bình) · quantile τ∈{.10,.25,.50,.75,.90} | Brignone: tác động chỉ leo thang trên ~4σ. C-I: GPR cao đi kèm rủi ro đuôi dưới lớn hơn |
| **CHANNEL** | gộp · tách ACT/THREAT | ECB LGPT: sốc năng lượng và thương mại tác động **ngược dấu** lên lãi suất |
| **JUMP_THRESH** | q95 · q99 | Brignone ~4σ; q95 là mặc định D2, q99 gần ngưỡng literature hơn |
| **SAMPLE** | đầy đủ · loại 2026 | Hormuz là episode chi phối; cần biết kết quả có phụ thuộc nó không |

**Trục báo cáo — outcome** (KHÔNG phải chiều lưới; mỗi outcome một curve riêng):

| Outcome | Tần suất có | Loại |
|---|---|---|
| oil, dxy, vix, us10y | ngày + tháng | giá tài sản |
| IP, CPI, kỳ vọng lạm phát | tháng | vĩ mô thực (C-I/Brignone/ECB) |
| **freight** | tháng | kênh vật lý (Hormuz/Malacca — nhưng đo TRUYỀN DẪN CHI PHÍ, KHÔNG tắc nghẽn; xem docstring `transform_freight`) |

**Kích thước:** cơ sở mỗi curve = 4 (SHOCK) × 6 (FUNCFORM) × 2 (CHANNEL) × 2 (JUMP_THRESH) × 2 (SAMPLE) = **96 spec**, × FREQ tùy outcome:

| Outcome | FREQ | Spec/curve |
|---|---|---|
| oil, dxy, vix, us10y | 2 mức | 192 mỗi cái |
| freight, IP, CPI, kỳ vọng lạm phát | 1 mức | 96 mỗi cái |

→ **8 curve riêng, mỗi cái diễn giải được** — KHÔNG phải 576 gộp làm một. Freight không cần chiều mới; nó cần một curve.

Loại các tổ hợp không hợp lệ/trùng lặp trước khi chạy:
- `JUMP_THRESH` chỉ áp dụng khi shock có thành phần JUMP (`JUMP`, `LEVEL+JUMP`). Với `SHOCK ∈ {INNOVATION, LEVEL}` → giữ 1 mức (không nhân đôi)
- Đếm cuối cùng chốt trong script, ghi vào report

**Rủi ro chọn lọc cấp curve:** nhiều curve hơn tái tạo rủi ro báo cáo chọn lọc ở tầng curve. Xử lý bằng chính cam kết §1.4: **báo cáo TOÀN BỘ curve, không bỏ cái nào, kể cả curve ra null.**

### 2.2. Ô chính (chỉ định TRƯỚC khi chạy)

Ô chính là **một điểm neo trên curve của outcome vĩ mô thực chính** (IP — track tháng).

```
outcome      = IP (industrial production)   # curve nào là "chính"
SHOCK        = [kết quả E1c-exo quyết định — hoặc MỞ (docs/13 §3.1); điền TRƯỚC khi chạy]
FREQ         = tháng                          # tách khỏi biến đích (không còn FREQ_OUTCOME)
FUNCFORM     = quantile τ=0.10
CHANNEL      = tách ACT/THREAT
JUMP_THRESH  = q95
SAMPLE       = đầy đủ
focal_horizons = [1, 2, 6]                     # track tháng; bám tín hiệu E0 tại h=1,2
daily_focal_horizons = [5, 20, 30]             # gồm h≈29 của G2a, chốt trước (§5.1)
```

> ⚠️ Ô chính phải được điền và commit **trước** khi chạy. Trường `SHOCK` phụ thuộc **E1c-exo** (KHÔNG phải E1b — đã bị bác, docs/13 §1); nếu E1c-exo chưa xong, KHÔNG chạy lưới. Horizon tháng `[1,2,6]` giữ hai điểm duy nhất E0 đã phát hiện và một điểm bền hơn; horizon ngày `[5,20,30]` bao phủ vùng h≈29 từng xuất hiện ở G2a. Các mốc này được khóa trước lưới, không đổi sau khi xem curve.

### 2.2.1. Gộp information-time cuối tuần theo loại shock

Sau khi dịch GPR ngày D sang `available_at=D+1`, nhiều ngày lịch có thể cùng đi vào một
phiên giao dịch. Toán tử gộp được đăng ký trước như sau:

- `LEVEL`, `PERSISTENT`, `INNOVATION`: **mean**; không chọn cực trị của residual có dấu.
- `JUMP`: **max**; mean sẽ làm mượt có hệ thống đúng các tail event cuối tuần.
- `LEVEL+JUMP`: **mean(LEVEL) + max(JUMP)**; không lấy mean/max trực tiếp trên composite.

Code chuẩn là `align_daily_shock_measures_to_information_time()`. Mọi report phải ghi
`weekend_aggregation`; đổi toán tử sau khi lưới chạy được tính là một lần thử mới.

### 2.3. Cái gì KHÔNG được vào lưới

SSN2020 cảnh báo rõ: nếu một spec không hợp lý về mặt lý thuyết hoặc thống kê, hoặc rõ ràng kém hơn các lựa chọn khác, thì nó **không thuộc về** bài kiểm tra tính bền, cũng không thuộc về specification curve.

Loại trừ dứt khoát:
- Bất kỳ spec nào vi phạm `available_at` (`CLAUDE.md` #11)
- AR order khác p=5/5/2 đã khóa trong registry
- τ < 0.10 (mẫu tháng **~378 obs** thực tế — panel bắt đầu 1995-01 vì `innovation()` min_train=60 đốt 60 tháng đầu từ 1990, KHÔNG phải 490 obs/1985; tại τ=0.10 còn **~38 điểm đuôi**, không phải 49. Chật hơn → ràng buộc "không đi dưới τ=0.10" càng QUAN TRỌNG, không phải ít đi. Số 490/1985 ở bản trước viết sai từ đầu)
- Bất kỳ spec nào chạm holdout (§6)
- Độn spec để tăng N

---

## 3. SUY DIỄN

### 3.1. Ba thống kê kiểm định — báo cáo cả ba

| # | Thống kê | Nội dung |
|---|---|---|
| T1 | Trung vị hệ số | Trung vị hệ số ước lượng trên toàn bộ spec, kiểm định xem có cực đoan hơn mức kỳ vọng nếu mọi spec đều có tác động thật bằng 0 |
| T2 | Tỉ lệ có ý nghĩa | Số spec cho kết quả có ý nghĩa theo đúng chiều dự đoán |
| T3 | Stouffer Z | Gộp liên tục toàn bộ p-value bằng cách lấy trung bình giá trị Z tương ứng |

SSN2020 khuyến nghị: T3 hiệu quả hơn về mặt thống kê vì tránh nhị phân hoá tùy tiện, nhưng T2 trực giác hơn — **báo cáo cả hai**, không chọn.

### 3.2. Phân phối dưới null — resampling, không giải tích

Không có công thức giải tích, vì các spec **không độc lập thống kê** với nhau và cũng **không thuộc cùng một mô hình**.

Dữ liệu của dự án là quan sát (không phải thí nghiệm) → dùng quy trình sáu bước của SSN2020 cho dữ liệu phi thí nghiệm:

1. Ước lượng toàn bộ K spec trên dữ liệu thật → K hệ số $\hat b_k$
2. Tạo K biến phụ thuộc dưới null: $y^*_k = y_k - \hat b_k x_k$
3. Rút ngẫu nhiên **có hoàn lại** N hàng, **dùng cùng bộ hàng đó cho cả K spec**
4. Ước lượng K spec trên mẫu rút
5. Lặp bước 3–4 nhiều lần (**B = 1000**, chốt trước)
6. Tính % đường cong tái chọn mẫu cho thống kê tổng thể cực đoan ít nhất bằng đường cong quan sát

**Điều chỉnh cho chuỗi thời gian:** bước 3 rút hàng độc lập sẽ phá cấu trúc phụ thuộc thời gian. Dùng **moving-block bootstrap** với độ dài khối $\ell$.

**ℓ HIỆU CHỈNH TRÊN MÔ PHỎNG (2026-07-19, `run_sca_calibration.py`, report `SCA_calibration_*.md`):**
ℓ=12 tháng / 60 ngày ở bản trước là PHÁN ĐOÁN, và kiểm size cho thấy **cả hai lệch**:

| Track | ℓ cũ (phán đoán) | SIZE ở ℓ cũ | ℓ hiệu chỉnh | SIZE ở ℓ mới |
|---|---|---|---|---|
| tháng (n=378, ρ=0.85) | 12 | **0.117** (phình >2× danh nghĩa) | **18** | 0.083 |
| ngày (n=2000, ρ=0.95) | 60 | **0.0** (mất power) | **40** | 0.05 (đúng) |

ℓ tháng=12 quá nhỏ → phá autocorr → size phình; ℓ ngày=60 quá lớn → ít block → size về 0.
**ℓ khóa mới: tháng = 18, ngày = 40.** Hiệu chỉnh này HỢP LỆ (mô phỏng, không đụng dữ
liệu thật — docs/13 §5). ⚠️ Mô phỏng dùng AR(1); chuỗi thật có đuôi/regime phức tạp hơn,
tháng ℓ=18 vẫn còn size 0.083 (hơi cao) → coi là cận dưới độ tin cậy. Đây không phải tùy
chọn tự do; giá trị khóa ở đây + registry `block_length_*`, đổi = một lần thử mới.

Đây là **sai lệch có chủ ý so với SSN2020** (họ giả định quan sát trao đổi được). Ghi rõ trong report.

### 3.3. Lợi ích phụ: bền với vi phạm giả định

Vì dựa vào resampling, suy diễn này nhìn chung **bền với vi phạm giả định** của các spec nền — nếu một spec có tỉ lệ dương giả bị thổi lên, resampling kéo nó về mức danh nghĩa 5%.

Quan trọng với lưới này vì nó trộn OLS và quantile regression, hai họ có tính chất mẫu hữu hạn khác nhau.

### 3.4. Dấu trội (dominant sign)

Vì nhiều spec giống nhau, kết quả giữa các spec **không độc lập** — kể cả trên dữ liệu dưới null cũng không kỳ vọng một nửa dương một nửa âm; thực tế phần lớn spec sẽ cùng dấu.

→ Báo cáo theo **dấu trội** (dấu của đa số hệ số trong một mẫu) thay vì dương/âm tuyệt đối. Đây là kiểm định hai phía: 80% cùng dấu là kết cục cực đoan như nhau bất kể 80% dương hay 80% âm.

---

## 4. SUY DIỄN LP — SỬA HAI ĐIỂM Ở DOC 11

### 4.1. Bỏ block bootstrap cho phần dư LP; dùng lag-augmentation

Doc 11 §5.4 đề xuất block bootstrap cho phần dư tự tương quan. **Không cần.**

MO-PM 2021: local projection **có bổ sung lag** với giá trị tới hạn chuẩn là hợp lệ tiệm cận **đồng đều** trên cả dữ liệu dừng lẫn không dừng, và trên một dải rộng các horizon; hơn nữa việc bổ sung lag **làm mất nhu cầu hiệu chỉnh sai số chuẩn cho tự tương quan** trong phần dư hồi quy. Bài chứng minh LP xử lý bền vững đúng hai vấn đề: **dữ liệu dai dẳng cao** và **ước lượng ở horizon dài** — cả hai đều là vấn đề của dự án này.

**Yêu cầu thực thi:** đảm bảo LP là lag-augmentation đúng nghĩa (thêm **một lag ngoài** số cần thiết), rồi dùng sai số chuẩn White thường.

*Lưu ý:* block bootstrap ở §3.2 là để sinh phân phối null cho **thống kê toàn đường cong** — khác mục đích với CI cho từng hệ số. Cả hai cùng tồn tại.

### 4.2. Bỏ CI theo từng điểm trên 31 horizon; dùng dải sup-t

MO-PM 2019: trong mô hình tuyến tính, dải **sup-t** hẹp hơn các lựa chọn thông dụng như Bonferroni và projection band, và thứ hạng đó vẫn đúng tiệm cận cả trong mô hình phi tuyến như VAR; nó cũng là **lựa chọn mặc định tối ưu** khi không biết sở thích của người đọc. Trong ứng dụng SVAR, sup-t hẹp hơn **ít nhất 35%** so với các dải đồng thời có sẵn khác.

**Hệ quả trực tiếp cho G2a:** phát biểu "13/31 horizon có p<0.10" là suy diễn **theo từng điểm**, gần như vô nghĩa khi 31 horizon tương quan mạnh. Mọi report từ nay dùng dải sup-t và nêu rõ mức phủ đồng thời.

---

## 5. ĐẦU RA

### 5.1. Một curve cho MỖI outcome (không gộp)

**Mỗi outcome (oil/dxy/vix/us10y/IP/CPI/kỳ vọng lạm phát/freight) có descriptive +
inferential curve RIÊNG.** Không xếp hệ số của các outcome khác đơn vị/khác ý nghĩa
lên cùng một curve (§2.1). 8 outcome → 8 cặp curve. Báo cáo TOÀN BỘ (cam kết §1.4),
kể cả curve null.

Ba tạo tác **cho mỗi outcome**:

1. **Descriptive specification curve** — hệ số của từng spec, sắp theo độ lớn, kèm **dashboard chart** bên dưới chỉ ra quyết định phân tích đứng sau mỗi hệ số. Cho biết **chiều nào hệ trọng** với outcome đó.
2. **Inferential specification curve** — đường cong quan sát chồng lên phân vị 2.5/50/97.5 của các đường cong dưới null.
3. **Bảng ba thống kê** T1/T2/T3 kèm p-value từ resampling.

Nếu N quá lớn để nhìn: hiển thị 50 hệ số cao nhất, 50 thấp nhất và một mẫu ngẫu nhiên ở giữa — **nhưng suy diễn tính trên toàn bộ N**.

**Ràng buộc tính toán — focal_horizons, chốt trước:** bootstrap dưới null rút hàng một
lần rồi ước lượng cả K spec → mỗi lần lặp là K spec × H horizon. Với K=192, H=24, B=1000
= ~4.6 triệu hồi quy MỖI outcome × 8 outcome → hàng giờ–ngày. **Giảm bằng cách tính curve
tại focal_horizons đăng ký trước, KHÔNG toàn bộ 24.** Lý do không chỉ tiết kiệm: curve trả
lời "hiệu ứng có bền qua spec không" — câu hỏi về SPEC, không về hình dạng theo horizon
(hình dạng đã có dải sup-t lo ở ô chính). Chốt: **h ∈ {1, 2, 6} track tháng · {5, 20, 30}
track ngày**. Track tháng giữ đúng vùng tín hiệu E0 (h=1,2); track ngày thêm h=30 để bao
phủ phát hiện G2a quanh h≈29. Đây là bậc tự do → khóa ở đây, ghi registry.

### 5.2. Ô chính báo cáo riêng

Ô chính (§2.2) báo cáo tách, kèm dải sup-t trên các horizon. Hiệu chỉnh đa kiểm định (Holm) áp cho **họ horizon trong ô chính**, không áp cho lưới — lưới đã có suy diễn riêng ở §3.

### 5.3. Metadata (bắt buộc, theo `docs/10` F1)

`data_version` · `git commit` · `generated_at` · `B` · $\ell$ · số spec sau khi loại trùng · seed · `protocol_version` = commit hash của doc này · `focal_horizons` · **`freight_vintage`** khi outcome/kênh có freight (PPI có hiệu chỉnh hồi tố → `data_version` hash GPRD KHÔNG phủ được vintage FRED freight; `data_files.freight_vintage()`).

Report versioned, **không ghi đè** (`FileExistsError` như `run_e1_diagnosis.py`).

### 5.4. Guard P1 áp cho report generator

Mọi số trong narrative phải tính từ dict `stats`, **không hard-code**. Test tự động: mọi số trong văn bản khớp một trường trong payload.

> Lỗi này đã xảy ra thật trong `run_e1_diagnosis.py` — narrative ghi "~1.8×" trong khi hai trường tính được cho 1.07/0.386 = **2.77×**. Đây là chính xác cơ chế hỏng mà `docs/11` §1 P1 được viết ra để chặn, xuất hiện trong pipeline nghiên cứu thay vì pipeline sản phẩm.

---

## 6. RÀNG BUỘC HOLDOUT

**Lưới KHÔNG chạm holdout.** Toàn bộ spec (96/curve × FREQ, mỗi outcome một curve) chạy trên development + validation + pseudo-OOS theo `config/backtest.yaml`. Holdout tách track: xem `g0_governance.md` §2 (ngày giữ 2026-H1; tháng chưa có holdout — rỗng theo cấu tạo).

Quyết định §9 doc 11 (A/B/C cho 2026-H1) **phải chốt và ghi vào `g0_governance.md` trước khi chạy lưới** — vì mức `SAMPLE = loại 2026` của lưới tương tác trực tiếp với nó.

Nhắc lại ràng buộc kỹ thuật đã phát hiện: `jump()` dùng `sd` và ngưỡng q95 rolling 250 phiên → sau Hormuz, JUMP bị **nén cơ học** suốt ~250 phiên kế tiếp, tức đúng 2026-H2. Nếu shock chính là JUMP và holdout rơi vào 2026-H2, thước đo đang bị bóp đúng lúc đo. Điều này phải nằm trong bảng đánh đổi A/B/C.

---

## 7. PHƯƠNG ÁN XỬ LÝ THEO KẾT QUẢ

Ba kịch bản. **Không kịch bản nào là thất bại.**

### KB1 — Đường cong nằm hoàn toàn ngoài dải null; cả ba thống kê bác bỏ

Tác động thật, bền qua mọi spec.

**Xử lý:** ô chính vào sản phẩm; các chiều khác thành robustness section. Chuyển sang đóng gói phân phối (doc 11 §5.4) và tầng model của Model Brief. Đây là kịch bản dễ nhất và **ít khả năng nhất**.

### KB2 — Đường cong nằm trong dải null

Null thật, đã kiểm định trên toàn bộ curve (96 spec/curve × nhiều outcome) chứ không phải 1.

**Xử lý:**
- Đây là **kết quả đáng công bố**, mạnh hơn hẳn "chúng tôi chạy một hồi quy và không thấy gì".
- Sản phẩm rút về đo lường + analogue toàn cầu (doc 11 §2.2, §6). Vẫn launch được.
- Định vị nhà mô hình **vẫn đứng**: R2 (track record công khai) được phục vụ tốt hơn bởi một null trung thực có tài liệu đầy đủ hơn là một kết quả dương yếu ớt.
- Đóng cửa tầng 2 một cách hợp lệ; dồn nguồn lực sang chân B và tầng 3.

### KB3 — Đường cong cắt qua dải; kết quả phụ thuộc chiều cụ thể

**Khả năng cao nhất, và hữu ích nhất.** Dashboard chart chỉ ra chiều nào gây biến thiên → trả lời trực tiếp câu hỏi §1.1.

| Biến thiên tập trung ở | Kết luận | Sản phẩm đi theo hướng |
|---|---|---|
| FREQ (tần suất) | Tần suất quyết định; chuyển hẳn track tháng | Model Brief định kỳ |
| outcome (so giữa curve) | Biến đích quyết định; vĩ mô thực > giá tài sản | Vĩ mô thực là deliverable chính |
| SHOCK | E1c-exo đúng; thước đo thắng là thứ dùng | Trigger theo đuôi, kiến trúc doc 11 §2.1 giữ nguyên |
| FUNCFORM | Hiện tượng nằm ở đuôi, không ở trung bình | Sản phẩm phân phối (R1) là hướng đi chính |
| CHANNEL | ECB đúng; gộp kênh triệt tiêu tín hiệu | Tách kênh thành trục sản phẩm; đẩy nhanh chân B |
| SAMPLE | Kết quả phụ thuộc một episode | ⚠️ Cảnh báo nghiêm trọng — xem §8 |

**Ba kết luận đầu dẫn tới ba sản phẩm khác nhau**, và lưới chọn giúp thay vì để bạn tự chọn.

---

## 8. HẠN CHẾ — GHI NHẬN TRƯỚC, KHÔNG BIỆN MINH SAU

**8.1. Trọng số.** Suy diễn mặc định gán **trọng số bằng nhau** cho mọi spec, dù nhà nghiên cứu có thể coi một số spec là ưu việt hơn. Có thể dùng trung vị/tỉ lệ/Stouffer có trọng số, nhưng SSN2020 thừa nhận trên thực tế **nhìn chung khó xác định trọng số số học có ý nghĩa**.
→ Quyết định: báo cáo **không trọng số** làm chính; ô chính đánh dấu riêng trên đồ thị.

**8.2. Không loại bỏ được tính chủ quan.** Chỉ chuyên gia, không phải thuật toán, mới xác định được tập phân tích hợp lệ; các chuyên gia khác nhau sẽ vẽ vòng khác nhau và cho ra đường cong khác nhau; mục tiêu loại bỏ tính chủ quan là **không đạt được và cũng không đáng mong muốn**.
→ SCA không kết thúc tranh luận về spec — nó làm tranh luận đó diễn ra **công khai trên dữ liệu** thay vì ngầm trong lựa chọn báo cáo.

**8.3. Tập spec không bao giờ đầy đủ.** SCA chỉ **giảm**, không **loại bỏ** xu hướng báo cáo chọn lọc.

**8.4. Sai lệch so với SSN2020.** Moving-block bootstrap thay vì rút hàng độc lập (§3.2) — cần thiết cho chuỗi thời gian, nhưng là chệch khỏi giao thức gốc. Ghi trong mọi report.

**8.5. Nếu KB3 rơi vào hàng SAMPLE.** Kết quả phụ thuộc việc có hay không 2026 nghĩa là toàn bộ tín hiệu đến từ **một episode**. Đó không phải phát hiện — đó là một quan sát. Xử lý: hạ claim xuống `association`, báo cáo như case study, **không** đóng gói thành phân phối.

---

## 9. CHECKLIST TRƯỚC KHI CHẠY

- [ ] E1c-endo đã chạy lại bằng contract đúng; E1c-exo xong và nhánh SHOCK đã xác định
- [ ] Ô chính §2.2 đã điền đầy đủ và commit
- [x] `build_monthly_panel()` đã viết và test; GPR tháng M được canh theo information-time vào bucket M+1
- [x] E0 replication headline đã PASS — chỉ chứng nhận loader + LP theo timing của paper
- [x] E0 aligned diagnostic (`python scripts/run_e0_alignment_diagnostic.py`) đã PASS — report `docs/reports/E0_alignment_diagnostic_e73a0a307fc3_c93a877.md`
- [ ] Quyết định holdout A/B/C đã ghi vào `g0_governance.md` kèm ngày và lý do
- [ ] Doc này đã commit; hash ghi vào `config/hypothesis_registry.yaml` như **một entry duy nhất**
- [ ] Seed, B=1000, $\ell$ đã chốt trong config
- [ ] Guard P1 cho report generator đã có test

---

## 10. ENTRY REGISTRY

**Nguồn chân lý = `config/hypothesis_registry.yaml` → `specification_curves[SCA-01]`**
(single-source; KHÔNG lặp YAML ở đây để tránh hai bản lệch nhau). Entry đó đã phản
ánh tái cấu trúc §2.1 (2026-07-19): `grid_dimensions` (SHOCK/FREQ/FUNCFORM/CHANNEL/
JUMP_THRESH/SAMPLE), `report_axis_outcome` (asset_price/real_macro/physical_channel —
mỗi outcome 1 curve), `primary_cell` (outcome=IP, shock=UNRESOLVED chờ E1c-exo, freq=
monthly, focal_horizons=[1,2,6], daily_focal_horizons=[5,20,30]),
`blockers=[E1c_endo_rerun, gold_events_csv, E1c_exo, primary_cell_shock_resolved]`.

Còn phải điền khi commit: `protocol_commit` = commit hash của doc này.

---

## 11. NGUỒN

- Simonsohn, Simmons & Nelson (2020). Specification curve analysis. *Nature Human Behaviour* 4:1208–1214. doi:10.1038/s41562-020-0912-z
- Montiel Olea & Plagborg-Møller (2021). Local Projection Inference Is Simpler and More Robust Than You Think. *Econometrica* 89:1789–1823. doi:10.3982/ECTA18756
- Montiel Olea & Plagborg-Møller (2019). Simultaneous confidence bands: Theory, implementation, and an application to SVARs. *Journal of Applied Econometrics* 34:1–17.
- Caldara & Iacoviello (2022); Brignone, Gambetti & Ricci (ECB WP 2972 / BoE SWP 1118); Ioannou, Prioriello & Durrani (ECB WP 3250) — nguồn cho các chiều ở §2.1, đã trích trong `docs/11`.

> ⚠️ `usable_for_gate: false` cho toàn bộ mục này. Literature dùng để **sinh giả thuyết và diễn giải**, không dùng làm tiêu chí cổng (`docs/09` §2.5 — đã bỏ tiêu chí "đúng dấu literature" vì confirmation bias).
