"""Test cho tier2_global_macro.py (G2a) — Global Macro Impact.

Tang 2 generic: GPR shock -> {oil, dxy, vix, us10y} bang LP.
Kiem chung:
  - estimate_tier2 tra ve IRF panel co (macro_var, shock, horizon) + beta/se/ci.
  - Tren du lieu tong hop shock->oil voi gamma biet truoc, thu hoi dung gamma.
  - Nhieu shock + nhieu macro var chay het khong loi.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.tier2_global_macro import estimate_tier2


def test_recovers_known_gamma_oil():
    n = 2500
    rng = np.random.default_rng(11)
    shock = pd.Series(rng.standard_normal(n).clip(min=0), name="GPRD_t")  # GPR>=0
    gammas = [0.5, 0.2]  # oil phan ung theo shock tai h=0 va h=1
    oil = np.zeros(n)
    for h, g in enumerate(gammas):
        oil += g * np.concatenate([np.zeros(h), shock.values[:n - h]])
    oil += rng.standard_normal(n) * 0.1
    df = pd.DataFrame({"oil": oil, "GPRD_t": shock})

    irf = estimate_tier2(df, macro_vars=["oil"], shocks=["GPRD_t"],
                         controls=[], horizons=range(len(gammas)))
    got = irf.set_index(["macro_var", "shock", "horizon"])["beta"]
    for h, g in enumerate(gammas):
        assert got.loc[("oil", "GPRD_t", h)] == pytest.approx(g, abs=0.05)


def test_panel_structure_multi():
    n = 400
    rng = np.random.default_rng(2)
    df = pd.DataFrame({
        "oil": rng.standard_normal(n),
        "vix": rng.standard_normal(n),
        "GPRD": rng.standard_normal(n),
        "GPRD_ACT": rng.standard_normal(n),
    })
    irf = estimate_tier2(df, macro_vars=["oil", "vix"],
                         shocks=["GPRD", "GPRD_ACT"],
                         controls=[], horizons=range(4))
    # 2 macro x 2 shock x 4 horizon = 16 hang
    assert len(irf) == 2 * 2 * 4
    for col in ["macro_var", "shock", "horizon", "beta", "se", "ci_low", "ci_high"]:
        assert col in irf.columns
    assert set(irf["macro_var"]) == {"oil", "vix"}
    assert set(irf["shock"]) == {"GPRD", "GPRD_ACT"}


def test_missing_macro_var_raises():
    df = pd.DataFrame({"oil": [1.0, 2, 3], "GPRD": [0.1, 0.2, 0.3]})
    with pytest.raises((KeyError, ValueError)):
        estimate_tier2(df, macro_vars=["nope"], shocks=["GPRD"],
                       controls=[], horizons=[0])
