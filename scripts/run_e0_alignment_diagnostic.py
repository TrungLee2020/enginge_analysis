"""E0 timing diagnostic: đối chiếu paper timing với GPR monthly aligned M+1.

Đây không phải bản replication headline. Nó kiểm tra riêng đường dữ liệu mà
specification curve sẽ dùng. Chạy: python scripts/run_e0_alignment_diagnostic.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_e0_replication as e0  # noqa: E402
from gpr_engine.econometrics.local_projection import run_local_projection  # noqa: E402

REPORTS = Path("docs/reports")
RAW_ANCHOR_HORIZON = 2
ALIGNED_ANCHOR_HORIZON = 1


def evaluate_shift(raw_irf: pd.DataFrame, aligned_irf: pd.DataFrame) -> dict:
    """Kiểm tra dấu/threshold tại cặp horizon neo đã đăng ký trước.

    Không đòi hỏi hai beta bằng nhau: khi dịch information time, VIX control và
    mẫu hữu hiệu cũng dịch. Diagnostic chỉ PASS nếu tín hiệu âm-có-ý-nghĩa tại
    h=2 của replication vẫn xuất hiện tại h=1 của panel aligned.
    """
    raw = raw_irf.loc[RAW_ANCHOR_HORIZON]
    aligned = aligned_irf.loc[ALIGNED_ANCHOR_HORIZON]
    raw_ok = bool(raw["beta"] < 0 and raw["pvalue"] < 0.10)
    aligned_ok = bool(aligned["beta"] < 0 and aligned["pvalue"] < 0.10)
    return {
        "passed": raw_ok and aligned_ok,
        "raw_anchor_ok": raw_ok,
        "aligned_anchor_ok": aligned_ok,
        "raw_beta_h2": float(raw["beta"]),
        "raw_pvalue_h2": float(raw["pvalue"]),
        "aligned_beta_h1": float(aligned["beta"]),
        "aligned_pvalue_h1": float(aligned["pvalue"]),
    }


def _estimate(aligned: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = e0.build_ci_panel(aligned=aligned)
    irf = run_local_projection(
        panel,
        y="ip_g",
        shock="lgpr",
        controls=["ip_g_l1", "lgpr_l1", "vix"],
        horizons=e0.HORIZONS,
    )
    return panel, irf


def build_report(raw_irf: pd.DataFrame, aligned_irf: pd.DataFrame,
                 result: dict, meta: dict) -> str:
    verdict = "PASS" if result["passed"] else "FAIL/INVESTIGATE"
    lines = [
        "# E0 — Monthly information-time alignment diagnostic",
        "",
        "> Diagnostic riêng cho pipeline dự án; không thay thế replication C-I headline.",
        "",
        "## Metadata",
        "",
        f"- data_version: `{meta['dv']}`",
        f"- git commit: `{meta['commit']}`",
        f"- generated_at: {meta['now']}",
        f"- raw observations: {meta['n_raw']}",
        f"- aligned observations: {meta['n_aligned']}",
        "- timing: raw GPR tháng M so với aligned GPR tháng M → bucket M+1",
        "- anchor đăng ký trước: raw h=2 → aligned h=1",
        "",
        f"## Kết quả: **{verdict}**",
        "",
        "| Panel | Horizon | beta | p-value | Anchor đạt? |",
        "|---|---:|---:|---:|---|",
        f"| C-I raw | 2 | {result['raw_beta_h2']:.4f} | "
        f"{result['raw_pvalue_h2']:.4f} | {result['raw_anchor_ok']} |",
        f"| M+1 aligned | 1 | {result['aligned_beta_h1']:.4f} | "
        f"{result['aligned_pvalue_h1']:.4f} | {result['aligned_anchor_ok']} |",
        "",
        "PASS yêu cầu cả hai hệ số neo âm và p<0.10. Không yêu cầu beta bằng nhau vì "
        "control VIX và biên mẫu hữu hiệu thay đổi sau khi dịch thời điểm thông tin.",
        "",
        "Nếu FAIL, dừng specification curve và kiểm tra index/join/control timing; không "
        "tự động kết luận loader hoặc LP sai chỉ từ riêng diagnostic này.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_panel, raw_irf = _estimate(aligned=False)
    aligned_panel, aligned_irf = _estimate(aligned=True)
    result = evaluate_shift(raw_irf, aligned_irf)
    commit = e0._git_commit()
    meta = {
        "dv": e0._data_version(e0.DEFAULT_GPR_MONTHLY),
        "commit": commit,
        "now": dt.datetime.now().isoformat(timespec="seconds"),
        "n_raw": len(raw_panel),
        "n_aligned": len(aligned_panel),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E0_alignment_diagnostic_{meta['dv']}_{commit}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại; không ghi đè artifact cũ.")
    out.write_text(build_report(raw_irf, aligned_irf, result, meta), encoding="utf-8")
    print(f"DONE. Report: {out}")
    print(f"  VERDICT: {'PASS' if result['passed'] else 'FAIL/INVESTIGATE'}")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
