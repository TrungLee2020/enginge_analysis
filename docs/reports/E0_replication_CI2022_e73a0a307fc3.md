# E0 — Replication harness: Caldara-Iacoviello 2022

> 🔬 Unit test cấp hệ thống (docs/11 §5.8, docs/12 §9). Tái lập ĐÚNG spec headline của paper trên pipeline của ta — KHÔNG cải tiến spec. Sinh bởi `scripts/run_e0_replication.py`.

## Metadata

- **data_version** (sha256 GPR monthly): `e73a0a307fc3`
- **git commit**: `541d60f`
- **generated_at**: 2026-07-19T07:40:00
- **mẫu**: 1985-01 → 2019-12 (359 tháng, như C-I, tránh COVID + 2026)

## Spec tái lập (ĐÚNG như paper)

- y = 100·Δln(INDPRO) — tăng trưởng industrial production tháng (FRED).
- shock = **log(GPR) LEVEL** — như C-I dùng (KHÔNG innovation; ngoại lệ có chủ đích với #9 vì đang tái lập spec người khác).
- Local Projection Jordà, controls: lag IP growth, lag log(GPR), VIX; HAC SE.

## Kết quả: **✅ PASS — pipeline tái lập được C-I 2022**

Tiêu chí (chốt trước khi chạy): PASS nếu ≥1 horizon h∈1..6 có β<0 và p<0.10 (IP giảm, đúng hướng C-I).

- Horizon ngắn âm-có-ý-nghĩa: **[1, 2]** (2 cái).
- Đáy IRF tại h=2: β=-0.3748 (p=0.0083) — GPR shock đẩy IP growth xuống mạnh nhất ở đây.
- **Kết luận: pipeline ĐÚNG — kết quả null sau này là phát hiện thật.**

## Bảng IRF: log(GPR) → IP growth (%)

| h (tháng) | β | SE | p-value | 90% CI |
|---|---|---|---|---|
| 0 | -0.1173 | 0.1180 | 0.3202 | [-0.3114, 0.0768] |
| 1 | **-0.2311** | 0.1361 | 0.0895 | [-0.4550, -0.0072] |
| 2 | **-0.3748** | 0.1420 | 0.0083 | [-0.6083, -0.1412] |
| 3 | 0.0558 | 0.1349 | 0.6789 | [-0.1660, 0.2777] |
| 4 | 0.0536 | 0.1277 | 0.6745 | [-0.1564, 0.2636] |
| 5 | -0.0405 | 0.1126 | 0.7188 | [-0.2258, 0.1447] |
| 6 | 0.0602 | 0.1288 | 0.6402 | [-0.1516, 0.2720] |
| 7 | 0.0014 | 0.1212 | 0.9908 | [-0.1979, 0.2007] |
| 8 | **0.2667** | 0.1160 | 0.0215 | [0.0759, 0.4576] |
| 9 | 0.0688 | 0.1211 | 0.5701 | [-0.1305, 0.2680] |
| 10 | 0.0614 | 0.1269 | 0.6286 | [-0.1474, 0.2701] |
| 11 | -0.1029 | 0.1266 | 0.4165 | [-0.3112, 0.1054] |
| 12 | -0.0791 | 0.1176 | 0.5016 | [-0.2726, 0.1145] |

## Ý nghĩa cho lưới SCA (docs/12 §9)

Pipeline tái lập được C-I → đường nạp (GPR file + FRED + align tháng) và LP/HAC đúng. Kết quả null của G2a (daily/giá tài sản) và của lưới SCA sau này là **phát hiện thật**, không phải artifact pipeline. Gỡ blocker E0_replication của SCA-01.