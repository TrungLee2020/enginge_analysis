"""Test cho run_local_projection() — utility Jordà LP dung chung tang 2 & tang 3.

Viet TRUOC khi code (CLAUDE.md: test truoc cho phan cong thuc). Kiem chung:
  1. LP thu hoi dung he so tren du lieu tong hop co beta_h biet truoc.
  2. IRF tra ve dung so horizon, dung cot.
  3. HAC/Newey-West SE hoat dong (khong NaN, duong).
  4. Controls duoc dua vao dung.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.local_projection import run_local_projection


def _make_ar_response(n=800, seed=0, betas=(1.0, 0.6, 0.3, 0.0)):
    """Sinh chuoi: y_{t+h} = betas[h]*shock_t + noise. Shock iid.
    Voi moi h, quan he y_{t+h} ~ shock_t co he so dung betas[h].
    """
    rng = np.random.default_rng(seed)
    shock = rng.standard_normal(n)
    noise = rng.standard_normal(n) * 0.5
    y = pd.Series(rng.standard_normal(n) * 0.5, name="y")  # base level
    return shock, y, noise


def test_recovers_known_coefficients():
    """LP phai thu hoi beta_h ~ betas[h] tren du lieu sach."""
    n = 2000
    betas = [1.0, 0.6, 0.3, 0.0]
    rng = np.random.default_rng(42)
    shock = pd.Series(rng.standard_normal(n), name="shock")
    # y_t phu thuoc shock cac ky truoc: y_t = Σ_h betas[h]*shock_{t-h} + eps
    eps = rng.standard_normal(n) * 0.3
    y = pd.Series(0.0, index=range(n), name="y")
    for h, b in enumerate(betas):
        y += b * shock.shift(h).fillna(0.0)
    y += eps

    df = pd.DataFrame({"y": y, "shock": shock})
    irf = run_local_projection(df, y="y", shock="shock",
                               controls=[], horizons=range(len(betas)))

    # irf co cot 'beta' index theo horizon
    assert list(irf.index) == list(range(len(betas)))
    for h, b in enumerate(betas):
        assert irf.loc[h, "beta"] == pytest.approx(b, abs=0.08), \
            f"h={h}: got {irf.loc[h,'beta']}, expect {b}"


def test_irf_shape_and_columns():
    n = 500
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "y": rng.standard_normal(n),
        "shock": rng.standard_normal(n),
        "ctrl": rng.standard_normal(n),
    })
    irf = run_local_projection(df, y="y", shock="shock",
                               controls=["ctrl"], horizons=range(6))
    assert len(irf) == 6
    for col in ["beta", "se", "ci_low", "ci_high"]:
        assert col in irf.columns
    # SE duong, khong NaN
    assert (irf["se"] > 0).all()
    assert not irf[["beta", "se"]].isna().any().any()


def test_hac_se_positive_and_ci_brackets_beta():
    n = 1000
    rng = np.random.default_rng(7)
    shock = pd.Series(rng.standard_normal(n), name="shock")
    y = 0.8 * shock + rng.standard_normal(n) * 0.5
    df = pd.DataFrame({"y": y, "shock": shock})
    irf = run_local_projection(df, y="y", shock="shock",
                               controls=[], horizons=[0])
    row = irf.loc[0]
    assert row["ci_low"] < row["beta"] < row["ci_high"]
    assert row["se"] > 0


def test_controls_change_estimate():
    """Khi shock tuong quan voi control, dua control vao phai doi uoc luong."""
    n = 1500
    rng = np.random.default_rng(3)
    z = rng.standard_normal(n)
    shock = z + rng.standard_normal(n) * 0.5          # shock tuong quan voi z
    y = 1.0 * shock + 2.0 * z + rng.standard_normal(n) * 0.3
    df = pd.DataFrame({"y": y, "shock": pd.Series(shock), "z": z})

    no_ctrl = run_local_projection(df, y="y", shock="shock",
                                   controls=[], horizons=[0]).loc[0, "beta"]
    with_ctrl = run_local_projection(df, y="y", shock="shock",
                                     controls=["z"], horizons=[0]).loc[0, "beta"]
    # Khong control -> bias len (hut anh huong cua z); control z -> ve gan 1.0
    assert with_ctrl == pytest.approx(1.0, abs=0.1)
    assert abs(with_ctrl - 1.0) < abs(no_ctrl - 1.0)


def test_missing_column_raises():
    df = pd.DataFrame({"y": [1.0, 2, 3], "shock": [0.1, 0.2, 0.3]})
    with pytest.raises((KeyError, ValueError)):
        run_local_projection(df, y="y", shock="nope", controls=[], horizons=[0])
