"""Test panel_var — block-exogenous VAR + Granger test khối (docs/11 §5.5).

Kiem chung cot loi (nguyen tac #8, block exogeneity):
  - fit_block_exogenous_var ap dung rang buoc A_XZ=0: phuong trinh X KHONG chua
    lag cua Z; phuong trinh Z chua lag ca X lan Z.
  - granger_block_test H0: Z ↛ X. Dung dau DGP:
      * DGP block-exo THAT (Z khong day X) -> KHONG bac bo (p cao).
      * DGP co Z->X -> BAC BO (p thap). Test bat dung chieu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.panel_var import (
    fit_block_exogenous_var,
    granger_block_test,
)


def _sim_block_exo(n=600, seed=0) -> pd.DataFrame:
    """DGP block-exo THAT: X tu-hoi quy (khong phu thuoc Z); Z phu thuoc X va Z.

    x_t = 0.6 x_{t-1} + e
    z_t = 0.4 z_{t-1} + 0.5 x_{t-1} + u     (X day Z, KHONG nguoc lai)
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    z = np.zeros(n)
    ex, ez = rng.standard_normal(n), rng.standard_normal(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + ex[t]
        z[t] = 0.4 * z[t - 1] + 0.5 * x[t - 1] + ez[t]
    idx = pd.bdate_range("2000-01-03", periods=n)
    return pd.DataFrame({"x": x, "z": z}, index=idx)


def _sim_z_causes_x(n=600, seed=1) -> pd.DataFrame:
    """DGP VI PHAM: Z day X (block exogeneity SAI).

    x_t = 0.6 x_{t-1} + 0.5 z_{t-1} + e     <- Z -> X
    z_t = 0.4 z_{t-1} + u
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    z = np.zeros(n)
    ex, ez = rng.standard_normal(n), rng.standard_normal(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + 0.5 * z[t - 1] + ex[t]
        z[t] = 0.4 * z[t - 1] + ez[t]
    idx = pd.bdate_range("2000-01-03", periods=n)
    return pd.DataFrame({"x": x, "z": z}, index=idx)


# ---------------------------------------------------------------------------
# Granger block test — cot loi
# ---------------------------------------------------------------------------
def test_granger_not_reject_when_block_exo_true():
    """DGP block-exo that (Z khong day X) -> KHONG bac bo H0: Z↛X (p cao)."""
    df = _sim_block_exo()
    res = granger_block_test(df, x_cols=["x"], z_cols=["z"], lags=2)
    assert res["pvalue"] > 0.10, f"block-exo that ma bac bo (p={res['pvalue']:.3f})"
    assert res["reject_block_exogeneity"] is False


def test_granger_reject_when_z_causes_x():
    """DGP Z->X -> BAC BO H0 (p thap): block exogeneity KHONG hop le."""
    df = _sim_z_causes_x()
    res = granger_block_test(df, x_cols=["x"], z_cols=["z"], lags=2)
    assert res["pvalue"] < 0.05, f"Z->X ma khong bac bo (p={res['pvalue']:.3f})"
    assert res["reject_block_exogeneity"] is True


# ---------------------------------------------------------------------------
# fit — rang buoc A_XZ = 0
# ---------------------------------------------------------------------------
def test_fit_x_equation_excludes_z_lags():
    """Phuong trinh X KHONG duoc chua lag cua Z (rang buoc A_XZ=0)."""
    df = _sim_block_exo()
    fit = fit_block_exogenous_var(df, x_cols=["x"], z_cols=["z"], lags=2)
    x_regressors = fit["equations"]["x"]["regressors"]
    assert not any("z" in r for r in x_regressors), \
        f"phuong trinh X chua lag Z (vi pham block-exo): {x_regressors}"
    # co lag cua chinh x
    assert any("x_l" in r for r in x_regressors)


def test_fit_z_equation_includes_both():
    """Phuong trinh Z chua lag ca X lan Z (A_ZX, A_ZZ tu do)."""
    df = _sim_block_exo()
    fit = fit_block_exogenous_var(df, x_cols=["x"], z_cols=["z"], lags=2)
    z_reg = fit["equations"]["z"]["regressors"]
    assert any("x_l" in r for r in z_reg), "phuong trinh Z phai co lag X"
    assert any("z_l" in r for r in z_reg), "phuong trinh Z phai co lag Z"


def test_fit_recovers_zx_coefficient():
    """z_t = 0.4 z_{t-1} + 0.5 x_{t-1}: he so x_{t-1} trong pt Z ~ 0.5."""
    df = _sim_block_exo(n=2000, seed=3)
    fit = fit_block_exogenous_var(df, x_cols=["x"], z_cols=["z"], lags=1)
    params = fit["equations"]["z"]["params"]
    # tim he so cua x_l1
    key = [k for k in params if k.startswith("x_l1")][0]
    assert params[key] == pytest.approx(0.5, abs=0.1)


def test_multivariate_x_and_z():
    """Chay duoc voi nhieu bien X va Z (khong chi 1-1)."""
    df = _sim_block_exo(n=800)
    df["x2"] = df["x"].shift(1).fillna(0) * 0.3 + np.random.default_rng(9).standard_normal(len(df)) * 0.5
    df["z2"] = df["z"] * 0.5 + 0.1
    res = granger_block_test(df, x_cols=["x", "x2"], z_cols=["z", "z2"], lags=2)
    assert "pvalue" in res and 0.0 <= res["pvalue"] <= 1.0
    assert res["df_num"] > 0
