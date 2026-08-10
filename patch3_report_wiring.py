"""PATCH 3 — noi hai patch tren vao report cua scripts/run_t2_full.py.

Guard P1: moi so o day tinh tu bien, khong go tay.
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# THEM vao ham dung report, NGAY TREN bang "so o song sot Holm"
# ---------------------------------------------------------------------------
def render_grid_null_section(gamma: pd.DataFrame, focal_horizons, alpha: float) -> str:
    """Doi chieu muc luoi. DAT TREN bang Holm, khong phai duoi.

    Thu tu quan trong: doc "15 o song sot" truoc roi moi doc "34 < 43.2" thi
    an tuong dau da hinh thanh. Ket luan muc luoi phai den truoc ket luan muc o.
    """
    from gpr_engine.econometrics.multiplicity import grid_null_check

    focal = gamma[gamma["horizon"].isin(focal_horizons)]
    chk = grid_null_check(focal["pvalue"], alpha=alpha)

    parts = ["## Doi chieu muc luoi (doc TRUOC bang Holm)\n", chk.to_markdown()]

    # Tach theo ban battery: neu ban a bac bo nhieu hon han ban b thi phan
    # "rieng cua GPR" chinh la thu battery hap thu — doc duoc ngay o day.
    if "battery" in focal.columns:
        rows = []
        for b, sub in focal.groupby("battery"):
            c = grid_null_check(sub["pvalue"], alpha=alpha)
            rows.append(f"| {b} | {c.n_tests} | {c.expected:.1f} | {c.observed} "
                        f"| {c.ratio:.2f}x |")
        parts.append(
            "\n| Ban battery | n | Ky vong null | Quan sat | Ti le |\n"
            "|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# THEM vao muc Metadata cua report
# ---------------------------------------------------------------------------
def render_sample_section(panel: pd.DataFrame, requested_start: str,
                          battery_mode: str) -> str:
    """Chi phi mau — in ra de lan sau khong mat 17 nam ma khong ai thay."""
    from run_t2_full import sample_binding_report, sample_cost   # patch 2

    cost = sample_cost(panel, requested_start)
    binding = sample_binding_report(panel, top=5)

    lines = [
        "## Chi phi mau (complete-case toan cuc)\n",
        f"- `--start` yeu cau: **{cost['requested_start']}**",
        f"- mau thuc te: **{cost['actual_start']}**",
        f"- **mat {cost['months_lost']} thang** vi cot "
        f"`{cost['binding_column']}` (hop le tu {cost['binding_first_valid']})",
        f"- `battery_mode` = `{battery_mode}`",
        "",
        "5 cot bat dau muon nhat:\n",
        "| Cot | Hop le tu | n |",
        "|---|---|---|",
    ]
    for _, r in binding.iterrows():
        lines.append(f"| `{r['column']}` | {r['first_valid']} | {r['n_obs']} |")

    if battery_mode == "level_lags":
        lines += [
            "",
            "> `level_lags`: control EPU vao dang LEVEL + lag thay vi cung thuoc "
            "do voi shock. Span cua {LEVEL, lag} chua tron INNOVATION nen hap thu "
            "khong kem hon o hai thuoc do LEVEL/INNOVATION. **Danh doi**: JUMP la "
            "phi tuyen, khong nam trong span do — o thuoc do LEVEL+JUMP, control "
            "hap thu IT HON che do `same_measure`. Doc ket qua LEVEL+JUMP ban b "
            "voi luu y nay.",
        ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# GOI TRONG main(), theo thu tu nay
# ---------------------------------------------------------------------------
def report_body_order_example(panel, gamma, args, battery_mode, focal_horizons,
                              alpha) -> list[str]:
    """Thu tu muc trong report — khong phai tuy y."""
    return [
        # ... tieu de + claim ceiling + Metadata da co ...
        render_sample_section(panel, args.start, battery_mode),
        render_grid_null_section(gamma, focal_horizons, alpha),
        # ... roi moi den bang "so o song sot Holm" va cac bang γ ...
    ]
