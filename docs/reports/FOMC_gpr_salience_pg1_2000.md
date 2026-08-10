# Độ hiện diện của rủi ro địa chính trị trong văn bản Fed

> 🔬 Research. Sinh tự động bởi `scripts/run_fomc_gpr_salience.py`. Văn bản THẬT từ federalreserve.gov, chấm bằng LLM theo rubric `scoring/policy_gpr_scorer.py`.

**Claim tối đa: `measurement`.** Bảng này mô tả VĂN BẢN NÓI GÌ. Câu "GPR đi vào hàm phản ứng chính sách" là mức `association`, cần hồi quy — không có trong report này.

**KHÔNG phải cú sốc chính sách tiền tệ.** Cú sốc đó đã có bản đo sạch hơn từ giá phái sinh quanh cửa sổ FOMC (Kuttner 2001; Gürkaynak-Sack-Swanson 2005; Nakamura-Steinsson 2018). Đây là chiều ngược lại: địa chính trị hiện diện đến đâu trong phát ngôn Fed.

## Metadata

- **model**: `Qwen3-14B-AWQ` (rubric `pg1`, prompt `pg1`, temperature 0.1)
- **training_cutoff**: 2026-01-01
- **git commit**: `ac99a5d`
- **generated_at**: 2026-08-09T15:34:15
- **phạm vi**: 2000-03-23 → 2026-07-29 (403 văn bản: 192 statement + 211 minutes, 1147 đoạn chấm)
- **thời gian chạy**: 6553.7 giây

## Kết quả

Trung bình `gpr_salience` = **0.0709** (statement 0.0484 · minutes 0.0914); đỉnh 0.9. **0.3176** tỉ lệ văn bản có ít nhất một đoạn `binding` (địa chính trị được trình bày như yếu tố ảnh hưởng quyết định/triển vọng); 0.6675 tỉ lệ hoàn toàn không có nội dung địa chính trị. 121/403 văn bản nêu một kênh truyền dẫn cụ thể.

⚠️ **statement và minutes không so trực tiếp được**: statement dài ~1.000-1.300 ký tự và thuần thủ tục, minutes dài 36.000-46.000 ký tự có hẳn mục thảo luận. Chênh lệch salience giữa hai loại phần lớn là chênh lệch THỂ LOẠI, không phải chênh lệch mức độ quan tâm.

## Top 15 văn bản theo `gpr_salience`

| Ngày công bố | Loại | salience | max | binding | kênh | trích dẫn |
|---|---|---|---|---|---|---|
| 2022-03-16 | statement | 0.700 | 0.70 | ✓ | energy | The invasion of Ukraine by Russia is causing tremendous human and economic hards |
| 2022-05-04 | statement | 0.700 | 0.70 | ✓ | energy | The invasion of Ukraine by Russia is causing tremendous human and economic hards |
| 2001-11-08 | minutes | 0.653 | 0.90 | ✓ | financial | The confluence of worldwide economic weakness added to current uncertainties and |
| 2003-05-08 | minutes | 0.642 | 0.90 | ✓ | energy | Uncertainty about the effects of the war had contributed to higher energy prices |
| 2003-06-26 | minutes | 0.639 | 0.70 | ✓ | energy | sharp run-up in energy prices, however, pushed up overall consumer prices |
| 2003-03-18 | statement | 0.600 | 0.60 | ✓ | energy | However, the hesitancy of the economic expansion appears to owe importantly to o |
| 2022-06-15 | statement | 0.600 | 0.60 | ✓ | energy | The invasion of Ukraine by Russia is causing tremendous human and economic hards |
| 2022-09-21 | statement | 0.600 | 0.60 | ✓ | energy | Russia's war against Ukraine is causing tremendous human and economic hardship.  |
| 2022-04-06 | minutes | 0.597 | 0.90 | ✓ | energy | The Russian invasion of Ukraine led to periods of particularly elevated volatili |
| 2026-05-20 | minutes | 0.554 | 0.60 | ✓ | energy | The conflict in the Middle East had continued to be a key factor driving asset p |
| 2005-10-11 | minutes | 0.546 | 0.70 | ✓ | energy | damage to infrastructure for extracting and processing oil and natural gas was e |
| 2026-07-08 | minutes | 0.527 | 0.60 | ✓ | energy | Optimism around a near-term resolution of the conflict in the Middle East and th |
| 2026-04-08 | minutes | 0.467 | 0.60 | ✓ | energy | The conflict in the Middle East—resulted in sharp increases in energy prices, ra |
| 2003-01-29 | statement | 0.400 | 0.40 | ✓ | energy | Oil price premiums and other aspects of geopolitical risks have reportedly foste |
| 2003-05-06 | statement | 0.400 | 0.40 | ✓ | energy | the ebbing of geopolitical tensions has rolled back oil prices, bolstered consum |

## Giới hạn — đọc trước khi trích số

- **Chưa hiệu chuẩn với người chấm.** Không có mẫu vàng do người dựng, nên chưa biết LLM chấm lệch bao nhiêu. Đây là điều kiện của cổng docs/14 §6.2 (người chấm thứ hai) — vẫn đang mở.
- **Chuỗi tháng bỏ trống tháng không họp FOMC**, không điền 0: "không họp" khác "họp và không nhắc gì". Forward-fill là vi phạm #10.
- **Văn bản dài được CHIA ĐOẠN chấm rồi gộp** (trung bình có trọng số theo độ dài), không cắt. Cắt sẽ làm salience của minutes lệch xuống có hệ thống vì phần bàn về rủi ro nằm giữa/cuối văn bản.
- **Bao phủ không đều theo thời kỳ**: URL statement đổi dạng nhiều lần; script đọc đúng những gì trang mục lục của Fed liệt kê, không suy ra URL. Số văn bản tìm được ghi ở Metadata.
- **`evidence` là trích dẫn do LLM trả về** — đã yêu cầu nguyên văn trong prompt nhưng CHƯA đối chiếu máy với văn bản gốc. Trước khi trích vào bất kỳ đâu, kiểm lại bằng tay.

## Human review (điền tay sau khi đọc)

- Điểm cao có khớp giai đoạn căng thẳng thật không: _chưa điền_
- `evidence` có đúng nguyên văn không (soi ngẫu nhiên 10 văn bản): _chưa điền_
- **Kết luận (GO/NO-GO + lý do + ngày + người):** _chưa điền_
