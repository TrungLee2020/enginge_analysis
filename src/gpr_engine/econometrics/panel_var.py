"""panel_var.py — Block-exogenous VAR + Granger test khối (tầng 3, docs/11 §5.5). 🔬

Nền lý thuyết cho nguyên tắc #8 ("1 engine, n bộ params"): nếu khối biến NGOẠI (X:
shock GPR, oil, DXY, VIX, US10Y, cước vận tải) không bị khối NỘI của nước c (Z:
r^c, chính sách p, GPR nội địa) tác động — cùng kỳ lẫn có độ trễ — thì:
  1. Tầng 1–2 ước lượng MỘT LẦN hợp lệ cho mọi nước nhỏ mở.
  2. Thêm nước = thêm file params, KHÔNG re-estimate engine.
  3. Kiểm định được: Granger Z ↛ X. Không bác bỏ → kiến trúc engine+params hợp lệ.

Ràng buộc block exogeneity (Cushman-Zha 1997; Sato-Zhang-McAleer 2011):

    [X_t]   [A_XX(L)   0     ] [X_{t-1}]   [u^X_t]
    [Z_t] = [A_ZX(L)  A_ZZ(L)] [Z_{t-1}] + [u^Z_t]

    A_XZ(L) = 0  ∀L  → phương trình X CHỈ chứa lag của X, không lag Z.

🔬 research. Reduced-form; KHÔNG claim structural/causal (claims matrix 07v2 §6.4).
Đây là kiểm định GIẢ ĐỊNH kiến trúc, không phải impulse response.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


def _make_lags(df: pd.DataFrame, cols: Sequence[str], lags: int) -> pd.DataFrame:
    """Tạo cột lag <col>_l<k> cho k=1..lags."""
    out = {}
    for c in cols:
        for k in range(1, lags + 1):
            out[f"{c}_l{k}"] = df[c].shift(k)
    return pd.DataFrame(out, index=df.index)


def fit_block_exogenous_var(
    df: pd.DataFrame,
    x_cols: Sequence[str],
    z_cols: Sequence[str],
    lags: int = 2,
) -> dict:
    """Ước lượng VAR có ràng buộc block exogeneity A_XZ=0 (docs/11 §5.5).

    Phương trình X: y_{X} ~ const + lag(X)            (KHÔNG lag Z — ràng buộc).
    Phương trình Z: y_{Z} ~ const + lag(X) + lag(Z).

    Returns dict:
      equations[var] = {regressors, params, resid, rss, nobs}
      meta = {x_cols, z_cols, lags}
    """
    x_cols, z_cols = list(x_cols), list(z_cols)
    lag_x = _make_lags(df, x_cols, lags)
    lag_z = _make_lags(df, z_cols, lags)

    equations: dict[str, dict] = {}

    # Phương trình khối X: chỉ lag X (A_XZ=0).
    for v in x_cols:
        data = pd.concat([df[v].rename("__y__"), lag_x], axis=1).dropna()
        X = sm.add_constant(data[lag_x.columns], has_constant="add")
        res = sm.OLS(data["__y__"], X).fit()
        equations[v] = _eq_summary(res, list(lag_x.columns))

    # Phương trình khối Z: lag X + lag Z.
    z_regr = pd.concat([lag_x, lag_z], axis=1)
    for v in z_cols:
        data = pd.concat([df[v].rename("__y__"), z_regr], axis=1).dropna()
        X = sm.add_constant(data[z_regr.columns], has_constant="add")
        res = sm.OLS(data["__y__"], X).fit()
        equations[v] = _eq_summary(res, list(z_regr.columns))

    return {
        "equations": equations,
        "meta": {"x_cols": x_cols, "z_cols": z_cols, "lags": lags},
    }


def _eq_summary(res, regressors: list[str]) -> dict:
    return {
        "regressors": regressors,
        "params": dict(res.params),
        "resid": res.resid,
        "rss": float((res.resid ** 2).sum()),
        "nobs": int(res.nobs),
    }


def granger_block_test(
    df: pd.DataFrame,
    x_cols: Sequence[str],
    z_cols: Sequence[str],
    lags: int = 2,
) -> dict:
    """Granger test khối H0: Z ↛ X (block exogeneity hợp lệ).

    Với MỖI phương trình trong khối X, so sánh:
      - restricted   : X ~ const + lag(X)               (áp H0: hệ số lag Z = 0)
      - unrestricted : X ~ const + lag(X) + lag(Z)
    F-test gộp trên toàn khối X (tổng RSS) — Granger causality khối chuẩn.

    KHÔNG bác bỏ (p cao) → Z không Granger-cause X → block exogeneity hợp lệ →
    kiến trúc engine+params dùng được cho nước này (nguyên tắc #8, hệ quả 3).

    Returns dict: {fstat, pvalue, df_num, df_denom, rss_restricted,
                   rss_unrestricted, reject_block_exogeneity}
    """
    x_cols, z_cols = list(x_cols), list(z_cols)
    lag_x = _make_lags(df, x_cols, lags)
    lag_z = _make_lags(df, z_cols, lags)

    # Dùng CÙNG mẫu (complete-case trên cả lag X và Z) cho restricted/unrestricted
    # — nếu không hai mô hình chạy mẫu khác nhau, F-test vô nghĩa.
    full = pd.concat([df[x_cols], lag_x, lag_z], axis=1).dropna()

    rss_r = rss_u = 0.0
    n = len(full)
    # số ràng buộc = số hệ số lag Z trên MỖI phương trình X × số phương trình X
    q = lag_z.shape[1] * len(x_cols)
    # số tham số của model unrestricted trên 1 phương trình X (const + lagX + lagZ)
    k_u = 1 + lag_x.shape[1] + lag_z.shape[1]

    for v in x_cols:
        y = full[v]
        Xr = sm.add_constant(full[lag_x.columns], has_constant="add")
        Xu = sm.add_constant(pd.concat([full[lag_x.columns], full[lag_z.columns]],
                                       axis=1), has_constant="add")
        res_r = sm.OLS(y, Xr).fit()
        res_u = sm.OLS(y, Xu).fit()
        rss_r += float((res_r.resid ** 2).sum())
        rss_u += float((res_u.resid ** 2).sum())

    df_denom = len(x_cols) * n - len(x_cols) * k_u
    fstat = ((rss_r - rss_u) / q) / (rss_u / df_denom)
    pvalue = float(stats.f.sf(fstat, q, df_denom))

    return {
        "fstat": float(fstat),
        "pvalue": pvalue,
        "df_num": int(q),
        "df_denom": int(df_denom),
        "rss_restricted": rss_r,
        "rss_unrestricted": rss_u,
        "reject_block_exogeneity": pvalue < 0.05,
    }


__all__ = ["fit_block_exogenous_var", "granger_block_test"]
