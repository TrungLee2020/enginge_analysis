"""run_e0_replication.py — E0: replication harness Caldara-Iacoviello 2022. 🔬

docs/11 §5.8, docs/12 §9 (checklist) — CHẶN lưới SCA: nếu pipeline không tái lập
được kết quả đã publish thì cả 288 ô của lưới vô nghĩa. Đây là UNIT TEST CẤP HỆ
THỐNG cho toàn bộ đường nạp + LP.

Nguyên tắc (docs/11 §5.8): chạy lại ĐÚNG spec headline của paper (tần suất, mẫu,
biến, phương pháp NHƯ paper) trên CHÍNH pipeline của mình. KHÔNG "cải tiến" spec —
mục đích là kiểm pipeline, không phải tìm kết quả đẹp.

Spec C-I 2022 headline tái lập:
  - Tần suất THÁNG, mẫu ~1985-2019 (như paper, tránh COVID + 2026 Hormuz).
  - y = tăng trưởng industrial production (100·Δln INDPRO, FRED).
  - shock = log(GPR) LEVEL — ĐÚNG như paper (C-I dùng level, KHÔNG innovation).
    (Đây là ngoại lệ có chủ đích với #9: replication phải theo paper. Nguyên tắc #9
     áp cho spec CỦA TA, không áp khi tái lập spec người khác.)
  - Local Projection Jordà, controls: lag IP growth, lag log(GPR), VIX. HAC SE.

Kết quả kỳ vọng (C-I headline): GPR shock → IP GIẢM có ý nghĩa ở horizon ngắn.

TIÊU CHÍ PASS (chốt TRƯỚC khi chạy, docs/12 §5.8):
  PASS  = có >= 1 horizon trong h=1..6 với beta < 0 VÀ p < 0.10 (IP giảm, đúng hướng).
  FAIL  = không horizon ngắn nào âm-có-ý-nghĩa → nghi pipeline có bug, DỪNG lưới SCA.

Chạy:  .venv/bin/python scripts/run_e0_replication.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import DEFAULT_GPR_MONTHLY, load_gpr_monthly  # noqa: E402
from gpr_engine.econometrics.local_projection import run_local_projection  # noqa: E402

REPORTS = Path("docs/reports")
SAMPLE = ("1985-01-01", "2019-12-31")   # như C-I, tránh COVID + 2026
HORIZONS = range(0, 13)                 # 0..12 tháng
SHORT_HORIZONS = range(1, 7)            # 1..6: nơi tiêu chí PASS soi


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _data_version(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def build_ci_panel() -> pd.DataFrame:
    """Panel tái lập C-I: IP growth, log(GPR), VIX + lags. Mẫu 1985-2019."""
    from pandas_datareader import data as pdr

    gpr = load_gpr_monthly()["GPR"].loc[SAMPLE[0]:SAMPLE[1]]
    ip = pdr.DataReader("INDPRO", "fred", *SAMPLE)["INDPRO"]
    vix = pdr.DataReader("VIXCLS", "fred", *SAMPLE)["VIXCLS"].resample("MS").last()

    df = pd.DataFrame({
        "ip_g": 100 * np.log(ip).diff(),   # tăng trưởng IP tháng (%)
        "lgpr": np.log(gpr),               # shock = log(GPR) LEVEL (như paper)
        "vix": vix,
    }).dropna()
    df["ip_g_l1"] = df["ip_g"].shift(1)
    df["lgpr_l1"] = df["lgpr"].shift(1)
    return df.dropna()


def evaluate(irf: pd.DataFrame) -> dict:
    """Chấm PASS/FAIL theo tiêu chí đã chốt + thu số cho report (Guard P1)."""
    short = irf.loc[[h for h in SHORT_HORIZONS if h in irf.index]]
    neg_sig = short[(short["beta"] < 0) & (short["pvalue"] < 0.10)]
    passed = len(neg_sig) >= 1
    trough_h = int(irf["beta"].idxmin())
    return {
        "passed": passed,
        "n_neg_sig_short": int(len(neg_sig)),
        "neg_sig_horizons": [int(h) for h in neg_sig.index],
        "trough_horizon": trough_h,
        "trough_beta": round(float(irf.loc[trough_h, "beta"]), 4),
        "trough_pvalue": round(float(irf.loc[trough_h, "pvalue"]), 4),
    }


def build_report(irf: pd.DataFrame, ev: dict, meta: dict) -> list[str]:
    verdict = "✅ PASS — pipeline tái lập được C-I 2022" if ev["passed"] \
        else "🛑 FAIL — pipeline KHÔNG tái lập; nghi có bug, DỪNG lưới SCA"
    parts = [
        "# E0 — Replication harness: Caldara-Iacoviello 2022\n",
        "> 🔬 Unit test cấp hệ thống (docs/11 §5.8, docs/12 §9). Tái lập ĐÚNG spec "
        "headline của paper trên pipeline của ta — KHÔNG cải tiến spec. Sinh bởi "
        "`scripts/run_e0_replication.py`.\n",
        "## Metadata\n",
        f"- **data_version** (sha256 GPR monthly): `{meta['dv']}`",
        f"- **git commit**: `{meta['commit']}`",
        f"- **generated_at**: {meta['now']}",
        f"- **mẫu**: {SAMPLE[0][:7]} → {SAMPLE[1][:7]} ({meta['nobs']} tháng, "
        "như C-I, tránh COVID + 2026)\n",
        "## Spec tái lập (ĐÚNG như paper)\n",
        "- y = 100·Δln(INDPRO) — tăng trưởng industrial production tháng (FRED).",
        "- shock = **log(GPR) LEVEL** — như C-I dùng (KHÔNG innovation; ngoại lệ có "
        "chủ đích với #9 vì đang tái lập spec người khác).",
        "- Local Projection Jordà, controls: lag IP growth, lag log(GPR), VIX; HAC SE.\n",
        f"## Kết quả: **{verdict}**\n",
        f"Tiêu chí (chốt trước khi chạy): PASS nếu ≥1 horizon h∈1..6 có β<0 và p<0.10 "
        "(IP giảm, đúng hướng C-I).\n",
        f"- Horizon ngắn âm-có-ý-nghĩa: **{ev['neg_sig_horizons']}** "
        f"({ev['n_neg_sig_short']} cái).",
        f"- Đáy IRF tại h={ev['trough_horizon']}: β={ev['trough_beta']} "
        f"(p={ev['trough_pvalue']}) — GPR shock đẩy IP growth xuống mạnh nhất ở đây.",
        f"- **Kết luận: {'pipeline ĐÚNG — kết quả null sau này là phát hiện thật' if ev['passed'] else 'pipeline NGHI CÓ BUG — mọi kết luận G2a/lưới vô nghĩa cho tới khi sửa'}.**\n",
        "## Bảng IRF: log(GPR) → IP growth (%)\n",
        "| h (tháng) | β | SE | p-value | 90% CI |",
        "|---|---|---|---|---|",
    ]
    for h in irf.index:
        r = irf.loc[h]
        star = "**" if r["pvalue"] < 0.10 else ""
        parts.append(
            f"| {h} | {star}{r['beta']:.4f}{star} | {r['se']:.4f} | "
            f"{r['pvalue']:.4f} | [{r['ci_low']:.4f}, {r['ci_high']:.4f}] |")
    parts += [
        "",
        "## Ý nghĩa cho lưới SCA (docs/12 §9)\n",
        ("Pipeline tái lập được C-I → đường nạp (GPR file + FRED + align tháng) và "
         "LP/HAC đúng. Kết quả null của G2a (daily/giá tài sản) và của lưới SCA sau "
         "này là **phát hiện thật**, không phải artifact pipeline. Gỡ blocker "
         "E0_replication của SCA-01." if ev["passed"] else
         "Pipeline KHÔNG tái lập → CÓ BUG ở đâu đó (đọc dữ liệu / align / LP). "
         "DỪNG lưới SCA, tìm bug trước — mọi kết luận G2a cũng vô nghĩa."),
    ]
    return parts


def main() -> None:
    df = build_ci_panel()
    irf = run_local_projection(
        df, y="ip_g", shock="lgpr",
        controls=["ip_g_l1", "lgpr_l1", "vix"], horizons=HORIZONS)
    ev = evaluate(irf)
    dv = _data_version(DEFAULT_GPR_MONTHLY)
    meta = {"dv": dv, "commit": _git_commit(),
            "now": dt.datetime.now().isoformat(timespec="seconds"),
            "nobs": int(len(df))}
    parts = build_report(irf, ev, meta)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E0_replication_CI2022_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    print(f"  VERDICT: {'PASS' if ev['passed'] else 'FAIL'}")
    for k, v in ev.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
