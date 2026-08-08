# E4 — AI-GPR độc quyền có gì, và nhịp cập nhật chậm có sao không?

**Ngày chạy:** 2026-08-08 · **git:** `2143fba` · **data_version:** `13b8e8_a429b2`
**Mẫu:** 2015-01-01 → 2026-07-31 · **Trần claim:** `measurement`

## 0. Câu hỏi

E3 kết luận **không** thay GPRD bằng AI-GPR cho JUMP. Vậy AI-GPR — dữ liệu kèm paper, cập nhật theo nhịp nghiên cứu nên chậm hơn GPRD gốc — nên dùng vào đâu để không lãng phí?

**Giả thuyết kiểm ở đây:** phân công theo **TỐC ĐỘ BIẾN ĐỔI của đại lượng**, không theo nguồn. Đại lượng đổi nhanh cần dữ liệu tươi; đại lượng đổi chậm thì một bản chậm vài tuần vẫn còn nguyên giá trị.

## 1. AI-GPR có gì mà GPRD hoàn toàn không có

GPRD daily chỉ có **3 cột**: `GPRD, GPRD_ACT, GPRD_THREAT` — không có bất kỳ phân rã theo vùng/kênh nào. AI-GPR daily có **14 cột**, trong đó **8 chỉ số dầu theo vùng** (Middle East, Russia, USA, Venezuela, Africa, Americas, Asia, North Sea) — ở tần suất NGÀY.

Đây là điểm quan trọng: với những chuỗi này **không tồn tại nguồn thay thế**. Câu hỏi 'GPRD hay AI-GPR' không áp dụng — GPRD đơn giản là không có.

## 2. Các vùng có mang thông tin RIÊNG không, hay chỉ là bản sao có tỷ lệ?

Nếu 8 vùng chỉ là chuỗi tổng nhân hệ số thì tương quan cặp phải gần 1 và chẳng khai thác thêm được gì. Đo trên mẫu:

- tương quan trung bình giữa các cặp vùng: **0.132**
- thấp nhất -0.025, cao nhất 0.763

→ Các vùng **gần như độc lập nhau**. Một cú sốc Trung Đông và một cú sốc Nga là hai tín hiệu khác nhau, không phải cùng một tín hiệu ở hai mức độ. Đây là thông tin thật, và hiện đang bị bỏ không hoàn toàn.

## 3. ⚠️ Đính chính một cách đọc SAI (tôi mắc trong chính phiên này)

`AIGPR_OIL` trông như 'phần năng lượng của AI-GPR' nhưng **KHÔNG PHẢI**:

- có **41.1%** số ngày `AIGPR_OIL` **lớn hơn** `AIGPR`
- `AIGPR_OIL + AIGPR_NONOIL` **không** cộng về `AIGPR`
- tương quan với chuỗi tổng: OIL 0.585, NONOIL 0.958

Mỗi chỉ số được **chuẩn hóa riêng** (mỗi cái ~100 ở kỳ gốc của nó), nên tỷ số giữa chúng **không phải tỷ trọng phần trăm**. Gọi `AIGPR_OIL/AIGPR` là 'tỷ trọng năng lượng' là sai — nó là **tỷ số cường độ tương đối** (năng lượng đang căng thế nào so với nền chung), không cộng về 100%. Cách đọc này phải ghi rõ ở mọi chỗ dùng, nếu không sẽ có người cộng các vùng lại rồi thắc mắc vì sao vượt 100%.

## 4. Kết quả chính: đại lượng cấu trúc đổi CHẬM, trigger đổi NHANH

Tự tương quan theo THÁNG (giá trị tháng này dự đoán được tháng sau bao nhiêu):

| Đại lượng | Vai trò | Tự tương quan lag-1 tháng |
|---|---|---|
| `AIGPR_OIL/AIGPR` (cường độ tương đối kênh năng lượng) | cấu trúc | **0.757** (lag-3: 0.596) |
| JUMP trên `AIGPR` | trigger | **-0.054** |

→ **Giả thuyết §0 được ủng hộ.** Đại lượng cấu trúc dai: giá trị tháng trước vẫn nói được nhiều về tháng này. Trigger thì gần như không tự tương quan — giá trị tháng trước gần như vô dụng cho tháng này, đúng bản chất 'cú sốc'.

**Hệ quả trực tiếp cho câu hỏi nhịp cập nhật:** AI-GPR trễ vài tuần làm hỏng một trigger (thứ cần đúng NGÀY), nhưng gần như không làm suy giảm một đại lượng cấu trúc dai như trên. Nói cách khác **nhịp chậm của AI-GPR không phải nhược điểm cho đúng nhóm việc mà nó độc quyền.**

## 5. Ổn định của từng vùng (tỷ số so với `AIGPR_OIL`)

| Vùng | Trung bình | Độ lệch chuẩn | Tự tương quan lag-1 |
|---|---|---|---|
| MIDDLEEAST | 0.524 | 0.242 | 0.622 |
| RUSSIA | 0.323 | 0.267 | 0.786 |
| AFRICA | 0.104 | 0.098 | 0.206 |
| ASIA | 0.102 | 0.090 | -0.033 |
| VENEZUELA | 0.086 | 0.134 | 0.664 |
| USA | 0.076 | 0.073 | 0.335 |
| AMERICAS | 0.050 | 0.069 | 0.334 |
| NORTHSEA | 0.003 | 0.014 | 0.364 |

Middle East và Russia chi phối, và là hai vùng dai nhất — hợp lý về cơ chế. Các vùng nhỏ (North Sea) tỷ số thấp và nhiễu; đừng đọc chúng như tín hiệu độc lập khi chưa kiểm.

## 6. Khuyến nghị — phân công theo tốc độ, không theo nguồn

| Việc | Nguồn | Lý do |
|---|---|---|
| JUMP / trigger S4 (chân A realtime) | **GPRD** | cần đúng ngày; E3 cho thấy hai chuỗi khác ngày nên không thay thế được nhau |
| Cường độ kênh năng lượng | **AI-GPR** (`AIGPR_OIL`, 8 vùng) | GPRD không có; đại lượng dai nên trễ vài tuần không sao |
| Phơi nhiễm VN theo cặp nước | **AI-GPR** bilateral (monthly) | GPRD/GPRC không có chiều song phương |
| Vai trò VN (spillover/respondent) | **AI-GPR** country×role (monthly) | GPRC chỉ có mức nước, không tách vai |

**Việc code đề xuất (CHƯA làm trong report này):** chuỗi 8 vùng oil đã nằm trong `ext_series` sau `ingest/ai_gpr.py` nhưng chưa có đường đọc ra. Bước nhỏ nhất có ích: hàm đọc cường độ kênh năng lượng tại `as_of` (point-in-time, cùng quy ước `available_at` với `load_jump_series`), để `transmission_channel='energy'` có số kèm theo thay vì chỉ là nhãn.

## 7. Đối chiếu PHƯƠNG PHÁP trong paper — cái nào đã được tác giả kiểm, cái nào là rủi ro thật

Đọc lại `AI_GPR_PAPER.pdf` sau khi user đặt vấn đề cẩn trọng. Kết quả: mấy nghi ngại hiển nhiên nhất **đã được chính tác giả đo**, không phải lỗ hổng bỏ ngỏ:

| Nghi ngại | Tác giả xử lý thế nào | Còn là rủi ro? |
|---|---|---|
| Lọc từ khóa giai đoạn 1 bỏ sót bài (chỉ số không thật sự 'ngữ nghĩa') | Đo trực tiếp: chấm LLM trên mẫu ngẫu nhiên các bài KHÔNG khớp từ khóa — chỉ **0.9%** có điểm dương, và đều điểm thấp | Nhỏ, đã đo |
| Cắt bài còn 2.000 ký tự làm sai điểm | Chấm lại toàn văn để đối chiếu: tương quan rất cao, thứ hạng gần như không đổi, toàn văn chỉ cao hơn chút | Nhỏ, đã đo |
| Chia cho `A_t` (tổng số bài báo) | Có chủ đích, kế thừa Caldara-Iacoviello (2022) để khử biến động sản lượng báo | Là lựa chọn thiết kế, không phải lỗi |

**Rủi ro THẬT còn lại, và nó ảnh hưởng trực tiếp tới cách ta dùng:**

1. **Công thức (2) của Oil GPR KHÔNG có hằng số chuẩn hóa `S̄`** mà công thức (1) của AI-GPR tổng thì có. Đây chính là lý do gốc của §3: hai chỉ số nằm trên hai thang khác nhau, nên **mọi tỷ số giữa chúng không phải phần trăm**. Phát hiện thực nghiệm ở §3 và công thức trong paper xác nhận lẫn nhau.
2. **Oil GPR có điều kiện lồng**: chỉ xét bài đã có điểm GPR > 0.5 *và* chứa từ khóa dầu/năng lượng. Nên `AIGPR_OIL` **không độc lập** với `AIGPR` — nó là tập con đã lọc. Tính độc lập đo ở §2 là **giữa các VÙNG với nhau**, không phải giữa oil và chuỗi tổng (tương quan hai cái đó là 0.585). Đừng đọc lẫn hai điều này.
3. **Phụ thuộc GPT-4o mini** (temperature 0). Model bị deprecate là mất khả năng tái lập y hệt — `docs/16` §4.2 đã ghi, vẫn còn nguyên.
4. **Chỉ 3 tờ báo**, so với 10–11 tờ của GPRD gốc. Nền nguồn hẹp hơn.

## 8. Ranh giới với chân B của DỰ ÁN NÀY — đừng để lẫn

AI-GPR đo **tỷ lệ đưa tin về rủi ro trong báo chí**. Chân B của ta đo **mức leo thang trong MỘT phát ngôn chính thức**. Hai thứ khác nhau về bản chất:

| | AI-GPR | Chân B (`statement_scorer` + `s_gpr`) |
|---|---|---|
| Đầu vào | bài báo | phát ngôn chính thức |
| Thang điểm | 0.0…1.0, MỘT chiều | −1.0…+1.0, HAI chiều (có hòa giải) |
| Tổng hợp | `Σ Sᵢ / Aₜ` (tỷ lệ đưa tin) | `Σ w(role)·max(v,0)·specificity` |
| Trọng số người nói | không có | có (`w(role)`) |
| Nhịp | chỉ số ngày | theo từng tin, realtime |

→ **AI-GPR không thay được chân B, và chân B không tái lập AI-GPR.** Chiều hòa giải (v < 0) và trọng số vai người phát ngôn là hai thứ AI-GPR **không có** — đó đúng là phần giá trị tự xây mà CLAUDE.md #2 chỉ ra. Nếu sau này ai đó kéo chân B về phía chấm bài báo 0–1 một chiều thì đó là **đánh mất khác biệt**, không phải nâng cấp.

## 9. Điều report này KHÔNG trả lời

- Cường độ kênh năng lượng có **dự báo** được outcome không — cần hồi quy outcome, vượt trần `measurement`. Phải qua cổng IC gia tăng (CLAUDE.md #6) trước khi vào production.
- Trọng số nên gán cho từng vùng — đó là ước lượng, không phải mô tả.
- Có nên thay `AIGPR_OIL` bằng tổng 8 vùng không — chúng **không cộng về** chuỗi tổng (một bài báo gắn nhiều vùng, `docs/16` §1), nên là hai đại lượng khác nhau, phải chọn có chủ đích.
