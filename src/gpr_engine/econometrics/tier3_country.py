"""tier3_country.py — TANG 3 cascade: COUNTRY TRANSMISSION (G2b). 🔬 research

Xem docs/06 §2.4, docs/07 §4-5.

Phuong trinh (docs/07 §5.1, Local Projection horizon h):
    r^c_{t+h} = α + [θ_oil·oil + θ_dxy·dxy + θ_vix·vix + θ_rate·us10y]   (INDIRECT, qua tang 2)
               + λ · GPR^{c,⊥}_t                                        (DIRECT, danh thang)
               + Φ·X^c + ε

Ba thanh phan:
  1. orthogonalize()      — tach GPR^{c,⊥} (phan rieng nuoc c) khoi global (§4.1, FWL).
  2. estimate_tier3()     — uoc luong θ_* va λ theo horizon.
  3. mediation_analysis() — Total = Direct(λ·∂orth/∂shock) + Indirect(Σ γ_{M,j}·θ_M).

Params doc tu config/params/<country>.yaml. Khong dien θ tay.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .local_projection import run_local_projection


def orthogonalize(df: pd.DataFrame, target: str, on: Iterable[str]) -> pd.Series:
    """Tach phan rieng nuoc c: hoi quy target len cac regressor global, tra ve phan du.

    GPR^c = f(GPR_global, GPR_US, GPR_CN, Oil) + GPR^{c,⊥}   (docs/07 §4.1, FWL).
    Phan du GPR^{c,⊥} chinh la DIRECT shock cho tang 3.
    """
    on = list(on)
    missing = [c for c in [target, *on] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co: {missing}")
    data = df[[target, *on]].dropna()
    X = sm.add_constant(data[on], has_constant="add")
    res = sm.OLS(data[target], X).fit()
    resid = pd.Series(res.resid, index=data.index, name=f"{target}_ORTH")
    return resid.reindex(df.index)


def estimate_tier3(
    df: pd.DataFrame,
    market_ret: str,
    macro_channels: Iterable[str],
    direct_shock: str,
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 61),
) -> pd.DataFrame:
    """Uoc luong tang 3: θ_* (INDIRECT, moi kenh macro) + λ (DIRECT) theo horizon.

    Dung run_local_projection nhung o day "shock" chinh la direct_shock, con cac
    kenh macro dua vao controls — moi he so lay ra tu cung mo hinh LP (HAC SE).

    Returns
    -------
    DataFrame index-free, cot: horizon, lambda, se_lambda, p_lambda,
    theta_<ch> (moi kenh), nobs.
    """
    macro_channels = list(macro_channels)
    controls = list(controls)
    horizons = list(horizons)

    need = [market_ret, direct_shock, *macro_channels, *controls]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    base = df.reset_index(drop=True)
    x_cols = [direct_shock, *macro_channels, *controls]
    hac = max(horizons) if horizons else 0

    rows = []
    for h in horizons:
        y_h = base[market_ret].shift(-h)
        data = pd.concat([y_h.rename("__y__"), base[x_cols]], axis=1).dropna()
        if len(data) <= len(x_cols) + 1:
            continue
        Xc = sm.add_constant(data[x_cols], has_constant="add")
        res = sm.OLS(data["__y__"], Xc).fit(
            cov_type="HAC", cov_kwds={"maxlags": max(hac, h)})
        row = {
            "horizon": h,
            "lambda": res.params[direct_shock],
            "se_lambda": res.bse[direct_shock],
            "p_lambda": res.pvalues[direct_shock],
            "nobs": int(res.nobs),
        }
        for ch in macro_channels:
            row[f"theta_{ch}"] = res.params[ch]
            row[f"p_theta_{ch}"] = res.pvalues[ch]
        rows.append(row)

    return pd.DataFrame(rows)


def mediation_analysis(
    gamma: pd.DataFrame,
    theta: Mapping[str, float],
    lam: float,
    d_orth_d_shock: float,
    shock: str,
    horizon: int = 0,
) -> dict:
    """Phan ra tong tac dong cua mot shock nguon len r^c (docs/07 §5.2):

        Total = Direct + Indirect
        Direct   = λ · ∂GPR^{c,⊥}/∂shock
        Indirect = Σ_M θ_M · γ_{M,shock}   (γ tu tang 2)

    gamma : DataFrame tang 2 (cot macro_var, shock, horizon, beta=γ).
    theta : {macro_channel: θ_M} tu estimate_tier3.
    lam   : λ (DIRECT coef) tu estimate_tier3.
    d_orth_d_shock : ∂GPR^{c,⊥}/∂shock (do tu buoc orthogonalize; ~0 neu phan rieng doc lap shock).
    """
    g = gamma[(gamma["shock"] == shock) & (gamma["horizon"] == horizon)]
    g = g.set_index("macro_var")["beta"]

    indirect = 0.0
    contrib = {}
    for ch, th in theta.items():
        gm = float(g.get(ch, 0.0))
        c = th * gm
        contrib[ch] = c
        indirect += c

    direct = lam * d_orth_d_shock
    return {
        "shock": shock,
        "horizon": horizon,
        "direct": direct,
        "indirect": indirect,
        "total": direct + indirect,
        "indirect_by_channel": contrib,
    }


def variance_decomposition(
    df: pd.DataFrame,
    market_ret: str,
    theta: Mapping[str, float],
    lam: float,
    direct_shock: str,
) -> dict:
    """Ty le dong gop tung kenh vao Var(r^c) (docs/07 §5.3):
        Share_M = θ_M^2 · Var(M) / Var(r^c),  Share_direct = λ^2 · Var(orth) / Var(r^c).
    """
    var_r = df[market_ret].var()
    shares = {ch: (th ** 2) * df[ch].var() / var_r for ch, th in theta.items()}
    shares["direct"] = (lam ** 2) * df[direct_shock].var() / var_r
    return shares
