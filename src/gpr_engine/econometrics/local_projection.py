"""Local Projection (Jorda 2005) — utility DUNG CHUNG cho tang 2 va tang 3.

Xem docs/07_formulas_reference_v2.md §3 (tang 2) va §5.1 (tang 3), docs/06 §2.5.

Vai tro: KHONG con la "model chinh" — la ham nen uoc luong impulse response cho
mot phuong trinh LP bat ky. Tang 2 (tier2_global_macro) va tang 3 (tier3_country)
deu goi ham nay.

Cong thuc uoc luong tai moi horizon h:
    y_{t+h} = alpha_h + beta_h * shock_t + Phi_h * controls_t + eps_{t+h}
IRF = { beta_h : h in horizons }, sai so chuan Newey-West (HAC) vi horizon chong lan.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm


def run_local_projection(
    df: pd.DataFrame,
    y: str,
    shock: str,
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 61),
    hac_maxlags: int | None = None,
    ci: float = 0.90,
) -> pd.DataFrame:
    """Uoc luong LP: hoi quy y_{t+h} len shock_t (+ controls_t) cho tung h.

    Parameters
    ----------
    df : DataFrame da align theo thoi gian (mot hang = mot ky). Dung thu tu hang
        lam truc thoi gian; khong yeu cau index dac biet.
    y : ten cot bien phu thuoc (return / bien vi mo tang 2).
    shock : ten cot bien shock (GPR da log(1+x), S-GPR...).
    controls : danh sach cot kiem soat X (VIX, DXY, lag return...).
    horizons : cac h can uoc luong (0 = dong thoi).
    hac_maxlags : lag cho Newey-West. Mac dinh = max(horizons) (chong lan chuan).
    ci : muc tin cay cho dai IRF (0.90 -> z ~ 1.645).

    Returns
    -------
    DataFrame index = horizon, cot: beta, se, tstat, pvalue, ci_low, ci_high, nobs.
    """
    from scipy.stats import norm

    controls = list(controls)
    horizons = list(horizons)

    missing = [c for c in [y, shock, *controls] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    if hac_maxlags is None:
        hac_maxlags = max(horizons) if horizons else 0

    z = norm.ppf(0.5 + ci / 2.0)

    rows = {}
    base = df.reset_index(drop=True)
    x_cols = [shock, *controls]

    for h in horizons:
        # y dich chuyen len h ky: y_{t+h} khop voi shock_t o hang t
        y_h = base[y].shift(-h)
        data = pd.concat([y_h.rename("__y__"), base[x_cols]], axis=1).dropna()
        if len(data) <= len(x_cols) + 1:
            rows[h] = dict(beta=np.nan, se=np.nan, tstat=np.nan, pvalue=np.nan,
                           ci_low=np.nan, ci_high=np.nan, nobs=len(data))
            continue

        Xc = sm.add_constant(data[x_cols], has_constant="add")
        model = sm.OLS(data["__y__"], Xc)
        # HAC/Newey-West: bat buoc vi horizon chong lan tao autocorrelation residual.
        res = model.fit(cov_type="HAC", cov_kwds={"maxlags": max(hac_maxlags, h)})

        beta = res.params[shock]
        se = res.bse[shock]
        rows[h] = dict(
            beta=beta,
            se=se,
            tstat=res.tvalues[shock],
            pvalue=res.pvalues[shock],
            ci_low=beta - z * se,
            ci_high=beta + z * se,
            nobs=int(res.nobs),
        )

    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "horizon"
    return out[["beta", "se", "tstat", "pvalue", "ci_low", "ci_high", "nobs"]]
