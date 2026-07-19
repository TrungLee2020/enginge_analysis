# E0 — Monthly information-time alignment diagnostic

> Diagnostic riêng cho pipeline dự án; không thay thế replication C-I headline.

## Metadata

- data_version: `e73a0a307fc3`
- git commit: `c93a877`
- generated_at: 2026-07-19T13:33:17
- raw observations: 359
- aligned observations: 359
- timing: raw GPR tháng M so với aligned GPR tháng M → bucket M+1
- anchor đăng ký trước: raw h=2 → aligned h=1

## Kết quả: **PASS**

| Panel | Horizon | beta | p-value | Anchor đạt? |
|---|---:|---:|---:|---|
| C-I raw | 2 | -0.3748 | 0.0083 | True |
| M+1 aligned | 1 | -0.3783 | 0.0087 | True |

PASS yêu cầu cả hai hệ số neo âm và p<0.10. Không yêu cầu beta bằng nhau vì control VIX và biên mẫu hữu hiệu thay đổi sau khi dịch thời điểm thông tin.

Nếu FAIL, dừng specification curve và kiểm tra index/join/control timing; không tự động kết luận loader hoặc LP sai chỉ từ riêng diagnostic này.
