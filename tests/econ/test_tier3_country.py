"""Test cho tier3_country.py (G2b) — Country Transmission + mediation.

Kiem chung:
  - orthogonalize: phan du truc giao voi cac regressor global (corr ~ 0).
  - estimate_tier3: tra ve he so theta_* (INDIRECT) + lambda (DIRECT) theo horizon.
    Tren du lieu tong hop biet truoc theta/lambda, thu hoi dung.
  - mediation_analysis: Total = Direct + Indirect (so hoc dung).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import tier3_country as t3


def test_orthogonalize_residual_uncorrelated():
    n = 1000
    rng = np.random.default_rng(5)
    glob = rng.standard_normal(n)
    own = rng.standard_normal(n)                      # phan rieng that
    raw = 0.7 * glob + own                            # VNM tho = global + rieng
    df = pd.DataFrame({"GPRC_VNM": raw, "GPRD": glob})
    resid = t3.orthogonalize(df, target="GPRC_VNM", on=["GPRD"])
    # phan du gan truc giao voi GPRD
    assert abs(np.corrcoef(resid, glob)[0, 1]) < 0.05
    # va tuong quan cao voi phan rieng that
    assert np.corrcoef(resid, own)[0, 1] > 0.9


def test_estimate_tier3_recovers_coeffs():
    n = 3000
    rng = np.random.default_rng(9)
    oil = rng.standard_normal(n)
    vix = rng.standard_normal(n)
    direct = rng.standard_normal(n)                   # GPRC_VNM_ORTH
    theta_oil, theta_vix, lam = -0.4, -0.3, -0.2
    r = (theta_oil * oil + theta_vix * vix + lam * direct
         + rng.standard_normal(n) * 0.2)
    df = pd.DataFrame({"VNINDEX_RET": r, "oil": oil, "vix": vix,
                       "GPRC_VNM_ORTH": direct})
    res = t3.estimate_tier3(
        df, market_ret="VNINDEX_RET",
        macro_channels=["oil", "vix"], direct_shock="GPRC_VNM_ORTH",
        controls=[], horizons=[0],
    )
    row = res.set_index("horizon").loc[0]
    assert row["theta_oil"] == pytest.approx(theta_oil, abs=0.05)
    assert row["theta_vix"] == pytest.approx(theta_vix, abs=0.05)
    assert row["lambda"] == pytest.approx(lam, abs=0.05)


def test_mediation_total_equals_direct_plus_indirect():
    # gamma tang 2: shock GPRD day oil = 0.5, vix = 0.3 (tai h=0)
    gamma = pd.DataFrame({
        "macro_var": ["oil", "vix"],
        "shock": ["GPRD", "GPRD"],
        "horizon": [0, 0],
        "beta": [0.5, 0.3],
    })
    # theta tang 3
    theta = {"oil": -0.4, "vix": -0.2}
    lam = -0.1
    # d(orth)/d(GPRD): gia su phan rieng khong phu thuoc GPRD -> 0 (Indirect chi qua macro)
    med = t3.mediation_analysis(gamma, theta=theta, lam=lam,
                                d_orth_d_shock=0.0, shock="GPRD", horizon=0)
    indirect = 0.5 * (-0.4) + 0.3 * (-0.2)
    direct = lam * 0.0
    assert med["indirect"] == pytest.approx(indirect)
    assert med["direct"] == pytest.approx(direct)
    assert med["total"] == pytest.approx(direct + indirect)


def test_mediation_direct_nonzero():
    gamma = pd.DataFrame({"macro_var": ["oil"], "shock": ["GPRD"],
                          "horizon": [0], "beta": [0.5]})
    med = t3.mediation_analysis(gamma, theta={"oil": -0.4}, lam=-0.3,
                                d_orth_d_shock=0.2, shock="GPRD", horizon=0)
    assert med["direct"] == pytest.approx(-0.3 * 0.2)
    assert med["total"] == pytest.approx(-0.3 * 0.2 + 0.5 * -0.4)
