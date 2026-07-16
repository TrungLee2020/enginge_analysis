"""tier2_global_macro.py — TANG 2 cascade: GLOBAL MACRO RESPONSE (G2a). 🔬 research

Xem docs/06 §2.3, docs/07 §3.

"1 cu soc dia chinh tri day dau / do / risk-off toan cau bao nhieu."
Day la deliverable DOC LAP ("Global Macro Impact") — generic, khong can VN.

Cong thuc (Local Projection Jorda, moi bien vi mo M, moi horizon h):
    M_{t+h} = a + Σ_j γ_{M,j} · shock_{j,t} + Σ_k ρ · M_{t-k} + η
Uoc luong tung (macro_var, shock) rieng bang run_local_projection (HAC SE).

Ket qua = IRF panel: (macro_var, shock, horizon) -> γ + dai tin cay.
Theo channel (khi co S-GPR): chay rieng shock kenh energy vs trade -> γ khac nhau.
"""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .local_projection import run_local_projection

DEFAULT_MACRO = ["oil", "dxy", "vix", "us10y"]
DEFAULT_SHOCKS = ["GPRD", "GPRD_ACT", "GPRD_THREAT"]


def estimate_tier2(
    df: pd.DataFrame,
    macro_vars: Iterable[str] = DEFAULT_MACRO,
    shocks: Iterable[str] = DEFAULT_SHOCKS,
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 31),
    macro_lags: int = 1,
) -> pd.DataFrame:
    """Uoc luong tang 2 cho moi (macro_var, shock).

    df : da align + transform (dataset.transform_global_macro cho macro; log1p_gpr cho shock).
    macro_lags : so lag cua chinh bien vi mo dua vao controls (rho trong cong thuc).

    Returns
    -------
    DataFrame long: [macro_var, shock, horizon, beta, se, tstat, pvalue,
                     ci_low, ci_high, nobs]. beta = γ (impulse response).
    """
    macro_vars = list(macro_vars)
    shocks = list(shocks)
    controls = list(controls)
    horizons = list(horizons)

    missing = [c for c in [*macro_vars, *shocks, *controls] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    frames = []
    for M in macro_vars:
        # Them lag cua chinh M vao controls (autoregressive term ρ)
        work = df.copy()
        lag_cols = []
        for k in range(1, macro_lags + 1):
            col = f"__{M}_lag{k}"
            work[col] = work[M].shift(k)
            lag_cols.append(col)

        for shock in shocks:
            irf = run_local_projection(
                work, y=M, shock=shock,
                controls=[*controls, *lag_cols],
                horizons=horizons,
            )
            irf = irf.reset_index()  # horizon la cot
            irf.insert(0, "shock", shock)
            irf.insert(0, "macro_var", M)
            frames.append(irf)

    out = pd.concat(frames, ignore_index=True)
    return out[["macro_var", "shock", "horizon", "beta", "se", "tstat",
                "pvalue", "ci_low", "ci_high", "nobs"]]


def global_macro_impact_index(irf: pd.DataFrame, shock: str = "GPRD") -> pd.DataFrame:
    """Tom tat IRF thanh chi so 'Global Macro Impact' cho 1 shock:
    voi moi macro_var lay γ tai h=0 (tac dong tuc thoi) — dung de xuat sang gpr_indices.
    """
    sub = irf[(irf["shock"] == shock) & (irf["horizon"] == 0)]
    return sub[["macro_var", "beta", "ci_low", "ci_high"]].reset_index(drop=True)
