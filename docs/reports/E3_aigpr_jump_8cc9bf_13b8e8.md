# E3 — AI-GPR làm nguồn JUMP chân A: đo trước khi nối

**Ngày chạy:** 2026-08-08 · **git:** `e872f89` · **data_version:** `8cc9bf_13b8e8`
**Mẫu chung:** 1985-01-01 → 2026-06-29, 15155 ngày · **Trần claim:** `measurement`

## 0. Câu hỏi

`service/store.py::load_jump_series` truy vấn cứng `series_id='GPRD'`. AI-GPR đã ingest nhưng không chạm đường serving. `docs/16` §5 khẳng định đổi sang AI-GPR **phải hiệu chuẩn lại** ngưỡng q95/q99 vì AI-GPR mượt hơn/đuôi mỏng hơn/không có ngày bằng 0. Báo cáo này kiểm khẳng định đó.

## 1. ✅ Kết luận chính: KHÔNG cần hiệu chuẩn lại ngưỡng — `docs/16` §5 sai ở điểm này

Mức (level) hai chuỗi đúng là khác nhau như `docs/16` mô tả:

- độ lệch chuẩn 61.62 (GPRD) so với 47.54 (AI-GPR)
- skew 3.74 so với 2.1
- giá trị nhỏ nhất 0.0 so với 21.27 — AI-GPR thật sự không bao giờ chạm 0
- tương quan mức: 0.678

**Nhưng khác biệt đó bị `jump()` triệt tiêu.** JUMP dựng trên **z-score rolling** (`z = (x − mean_roll)/std_roll`) rồi trừ **phân vị q của chính z** — cả hai bước đều **bất biến theo thang đo**. Mức và độ lệch chuẩn bị chuẩn hóa đi trước khi ngưỡng được áp. Đo trên dữ liệu thật, dùng ĐÚNG tham số production:

| Chuỗi | % ngày kích S4 (`jump_pct > 95`) |
|---|---|
| GPRD | 5.24% |
| AI-GPR | 5.14% |

Ổn định qua ba giai đoạn, không phải trùng hợp một lần:

| Giai đoạn | GPRD | AI-GPR |
|---|---|---|
| 1986–1999 | 5.32% | 5.14% |
| 2000–2014 | 5.46% | 5.33% |
| 2015–2026 | 5.07% | 5.07% |

→ Ngưỡng q95/q99 **giữ nguyên được**. Cảnh báo của `docs/16` §5 đúng cho bất kỳ thứ gì đọc **mức thô** (ví dụ ngưỡng cố định trên level), nhưng **không áp cho JUMP** — cần đính chính trong doc đó.

## 2. ⚠️ Nhưng KHÔNG được đọc thành 'hai chuỗi thay thế nhau được'

Cùng tần suất **không phải** cùng ngày:

- kích ở cả hai chuỗi: 263 ngày
- chỉ GPRD kích: 525 ngày
- chỉ AI-GPR kích: 510 ngày
- **Jaccard = 0.203** (cửa sổ dự án 2015–2023: 0.189)

Nói cách khác: khoảng bốn phần năm số ngày kích của chuỗi này thì chuỗi kia im lặng. Đổi nguồn JUMP **là đổi thước đo**, không phải đổi cách đọc cùng một thước đo — dù tần suất trùng khớp.

## 3. Hành vi quanh sự kiện lớn (mô tả, KHÔNG phải cổng E1c)

⚠️ **Đây không phải `data/gold_events.csv`.** Gold set của `docs/13` §2.2 do hai người dựng tay, không tra GPRD, và là thứ quyết định `primary_cell.shock`; Claude tự dựng danh sách rồi coi là gold set là vi phạm chính nguyên tắc ngoại sinh. Danh sách dưới chỉ gồm vài mốc lịch sử có ngày khách quan, n nhỏ, đọc như **mô tả** chứ không phải kiểm định.

Cửa sổ đối xứng [D−3, D+3]: GPRD phát hiện 8/8, AI-GPR 8/8.

**Đính chính một kết quả trung gian của chính phiên này:** với cửa sổ *một phía* [D, D+3], AI-GPR trông như trượt Crimea 2014 (phân vị 0). Sai — nó kích **trước** ngày sáp nhập (quanh trưng cầu dân ý 16/03), tức nằm ngoài cửa sổ một phía. Artifact của cách đặt cửa sổ, không phải của dữ liệu. Bảng dưới dùng cửa sổ đối xứng.

| Ngày | Sự kiện | GPRD (ngày lệch) | AI-GPR (ngày lệch) |
|---|---|---|---|
| 1990-08-02 | Iraq xâm lược Kuwait | -1 | +1 |
| 1991-01-17 | Chiến dịch Desert Storm | -2 | -2 |
| 2001-09-11 | Tấn công 11/9 | +0 | +0 |
| 2003-03-20 | Mỹ xâm lược Iraq | -2 | -3 |
| 2011-03-19 | Can thiệp Libya | -3 | +0 |
| 2014-03-18 | Nga sáp nhập Crimea | +0 | -3 |
| 2022-02-24 | Nga xâm lược Ukraine | -2 | -3 |
| 2023-10-07 | Hamas tấn công Israel | +2 | -1 |

Số sự kiện mỗi chuỗi kích sớm hơn: GPRD 2, AI-GPR 4, bằng nhau 2. Gợi ý AI-GPR nhạy sớm hơn — **gợi ý, không phải kết luận**: n quá nhỏ, không có kiểm định, và chọn sự kiện nào cũng là một bậc tự do.

## 4. Chi phí của phương án 'dùng cả hai'

| Cách kết hợp | % ngày kích S4 |
|---|---|
| chỉ GPRD (hiện tại) | 5.24% |
| chỉ AI-GPR | 5.14% |
| hợp (kích nếu **bất kỳ** chuỗi nào vượt) | 8.64% |
| giao (kích khi **cả hai** vượt) | 1.75% |

Hợp làm S4 kích **gần gấp đôi** — đổi ý nghĩa của bậc S4, không phải nâng cấp miễn phí. Giao thì chặt hơn nhiều nhưng cũng là một thước đo mới. Cả hai đều là **thay đổi spec**, phải qua governance, không phải việc nối dây.

## 5. Lợi ích vận hành THẬT và đo được: độ tươi

- GPRD mới nhất: 2026-06-29
- AI-GPR mới nhất: 2026-07-31
- AI-GPR mới hơn **32 ngày**

Đây không phải chi tiết vụn: ngưỡng `chain_a_stale` của pipeline là 35 ngày, và chạy thật ngày 2026-08-08 đã bị gắn cờ stale đúng vì GPRD dừng ở 2026-06-29. Với cùng ngày đó, AI-GPR **không** stale.

## 6. Khuyến nghị

1. **Giữ GPRD làm nguồn JUMP mặc định.** Không có bằng chứng AI-GPR dự báo tốt hơn — câu đó thuộc KĐ-E1c (AUC trên gold set) và vẫn bị chặn bởi `data_blockers.gold_events_csv`. Đổi mặc định lúc này là chọn bằng cảm tính.
2. **Gỡ hard-code `series_id='GPRD'`** thành tham số cấu hình được, mặc định vẫn GPRD (hành vi không đổi). Hiện tại muốn thử AI-GPR phải sửa mã nguồn — đó mới là thứ đáng sửa ngay.
3. **Fallback khi GPRD stale**: chuỗi chính stale thì đọc AI-GPR thay vì trả chuỗi rỗng, và ghi rõ đã dùng chuỗi nào. Giải đúng vấn đề vận hành ở §5 mà không đụng thước đo khi GPRD còn tươi.
4. **KHÔNG dùng hợp/giao** cho tới khi có gold set — §4 cho thấy đó là đổi spec, và ta chưa có tiêu chí để nói bản nào tốt hơn.
5. **Đính chính `docs/16` §5**: khẳng định 'phải hiệu chuẩn lại q95/q99' sai với JUMP (§1). Giữ cảnh báo cho các dùng khác đọc mức thô.

## 7. Điều báo cáo này KHÔNG trả lời

- Chuỗi nào **dự báo** outcome vĩ mô tốt hơn — cần hồi quy outcome, ngoài trần `measurement`.
- Chuỗi nào phát hiện sốc **đúng hơn** — cần gold set ngoại sinh (KĐ-E1c), vẫn bị chặn.
- Ảnh hưởng của việc đổi nguồn lên bảng γ tầng 2 — γ hiện ước lượng trên GPRD; đổi shock thì phải chạy lại `run_t2_full.py`, chưa làm.
