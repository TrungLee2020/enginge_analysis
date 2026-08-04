# E2 — Phân rã persistent/shock: hệ số thô có so được không?

> 🔬 Diagnostic. Kiểm luận điểm `docs/16` §2.1 trên dữ liệu của chính dự án. Sinh bởi `scripts/run_e2_component_check.py`.

**Claim ceiling: `measurement`.** Đây là thuộc tính của phép SO SÁNH HỆ SỐ, không phải claim về tác động. Không quyết định gate nào.

## Metadata

- **data_version**: `e73a0a307fc3` · **commit**: `72c4704` · **generated_at**: 2026-08-03T13:49:25
- **panel**: 2000-02-01 → 2026-06-01, n=313 tháng dùng được tại h=2
- **phân rã**: AR(4) trên Δlog1p(GPR) — đúng bậc `docs/16` §2.1 dùng, để so sánh được

## Câu hỏi

`docs/16` §2.1 đọc bảng của bài AI-GPR (persistent −0.271 vs shock −0.119) và kết luận: phần dai dẳng tác động **hơn gấp đôi**, nên partial-out nó (lag augmentation / INNOVATION) là vứt đi tín hiệu mạnh nhất. Câu hỏi ở đây: **hai hệ số đó có so được với nhau không?**

## Kết quả 1 — thô so với chuẩn hóa

AR(4) trên chuỗi **sai phân** giải thích được rất ít: R²=0.0998 (kênh pooled). Hệ quả là phần fitted có phương sai chỉ bằng **0.1109** lần phần residual — biên độ nhỏ hơn khoảng ba lần.

| GPR → IP, h=2 | β_persistent | β_shock |
|---|---|---|
| **Thô** | -1.1865 | -0.6112 |
| **Chuẩn hóa** (×sd) | -0.0882 | **-0.1389** |

Thô thì persistent lớn gấp đôi — **tái lập đúng pattern của bài**. Chuẩn hóa thì **thứ tự đảo ngược**.

Trên toàn bộ 45 ô (kênh × outcome × horizon focal): 34 ô có |β_P| > |β_S| theo thô, nhưng chỉ 12 ô giữ được sau chuẩn hóa. **22 ô đảo chiều kết luận** (48.9% tổng số ô).

## Kết quả 2 — ô chính của T2-full

`GPR_ACT → IP` tại h=2 (ô duy nhất đồng thuận cả ba thước đo trong bảng γ), n=313:

| | β | p | β×sd |
|---|---|---|---|
| Persistent | -0.4975 | 0.180 | -0.0480 |
| Shock | -0.4102 | **0.042** | **-0.1194** |

Ở ô này thành phần **shock** mới là cái mang tín hiệu: nó có ý nghĩa thống kê còn persistent thì không, và đóng góp chuẩn hóa cũng lớn hơn.

## Kết quả 3 (E2b) — LEVEL và INNOVATION dưới lag augmentation

Trên 45 ô: corr(β_LEVEL, β_INNOVATION) = **0.9985**, lệch tương đối trung vị **6.0%**.

→ **Xác nhận cơ chế mà `docs/16` §2.1 mô tả**: dưới lag augmentation, LEVEL bị residual hóa thành đúng phần bất ngờ (FWL), nên nó và INNOVATION cho gần như cùng một hệ số.

→ Nhưng đúng vì thế, **hệ quả "dùng INNOVATION là dùng nửa yếu nên kết quả mới yếu" không đứng**: nếu vậy thì LEVEL phải cứu được. Trong `T2_full` LEVEL cũng cho **0/4 giá tài sản**, y hệt INNOVATION — vì dưới lag-aug hai cái là cùng một thứ.

## Chẩn đoán phân rã theo kênh

| Kênh | R² của AR | Var(P)/Var(S) | sd(P) | sd(S) |
|---|---|---|---|---|
| pooled | 0.0998 | 0.1109 | 0.0758 | 0.2275 |
| act | 0.1036 | 0.1155 | 0.0989 | 0.2911 |
| threat | 0.1298 | 0.1492 | 0.0932 | 0.2413 |

## Kết luận máy đọc được

1. **Cơ chế của §2.1 đúng** và đã tái lập: lag-augmented LP trả về hệ số của thành phần bất ngờ.
2. **Kết luận định lượng của §2.1 chưa đứng được** trên dữ liệu này: "hơn gấp đôi" là so sánh hệ số thô của hai regressor khác phương sai — cùng loại tai nạn thang đo mà registry đã ghi cho `LEVEL+JUMP`. Chuẩn hóa xong thì thứ tự đảo.
3. **Đề xuất §2.2 (spec kép) không bị ảnh hưởng — nó là lối ra đúng**: đưa cả hai thành phần vào cùng lúc thì không phải chọn, và báo cáo được cả hai. Điều kiện: **đóng góp phải báo cáo chuẩn hóa**, và β_P phải gọi đúng tên là phản ứng với thành phần *đã dự báo được* — gọi nó là "tác động của cú sốc" vẫn là vi phạm #9.

## ⚠️ Giới hạn — đọc trước khi dùng kết luận này

- **Chuỗi khác bài.** Đây là GPRD tháng; bài chạy AI-GPR tuần. AI-GPR **dai hơn** (`docs/16` §5: tự tương quan 0.73 vs 0.62), nên R² của AR(4) trên nó sẽ cao hơn 0.0998, phần fitted có biên độ lớn hơn, và khoảng cách chuẩn hóa **có thể không đảo**. Kết quả này KHÔNG bác bảng của bài — nó bác cách *đọc* bảng đó khi chưa chuẩn hóa.
- **Việc cần làm để khép lại:** hỏi bài báo cáo hệ số thô hay chuẩn hóa, và Var(fitted)/Var(resid) của họ bằng bao nhiêu. Nếu họ đã chuẩn hóa thì §2.1 đúng nguyên và mục này chỉ còn giá trị cho chuỗi GPRD.
- Chạy lại E2 trên AI-GPR ngay khi `load_ai_gpr()` có dữ liệu.

## Human review

- Có chấp nhận sửa `docs/16` §2.1 theo mục Kết luận không: _chưa điền_
- **Kết luận (người + ngày):** _chưa điền_
