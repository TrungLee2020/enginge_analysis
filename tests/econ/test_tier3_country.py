"""Test cho tier3_country.py (G2b) — Country Transmission, spec v2 (docs/07v2 §5).

Viet TRUOC khi sua code (CLAUDE.md; docs/10 F2). Kiem chung 3 fix theo review 08:
  - [4.2] estimate_tier3 tra du BA he so: beta (global-direct), theta (indirect),
    lambda (domestic-direct). Thu hoi dung tren du lieu tong hop.
  - [4.1] transmission decomposition la TICH CHAP theo thoi gian, khop tinh tay,
    va PHAI KHAC ket qua nhan-cung-horizon (cong thuc v1 da bo).
  - [4.5] shapley_r2: tong share = R2 (truong hop khong controls); xu ly duoc
    regressor tuong quan (nai ve θ²Var/Var se vuot R2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import tier3_country as t3


# ---------------------------------------------------------------------------
# orthogonalize — giu nguyen hanh vi (khong doi trong F2)
# ---------------------------------------------------------------------------
def test_orthogonalize_residual_uncorrelated():
    n = 1000
    rng = np.random.default_rng(5)
    glob = rng.standard_normal(n)
    own = rng.standard_normal(n)                      # phan rieng that
    raw = 0.7 * glob + own                            # VNM tho = global + rieng
    df = pd.DataFrame({"GPRC_VNM": raw, "GPRD": glob})
    resid = t3.orthogonalize(df, target="GPRC_VNM", on=["GPRD"])
    assert abs(np.corrcoef(resid, glob)[0, 1]) < 0.05
    assert np.corrcoef(resid, own)[0, 1] > 0.9


# ---------------------------------------------------------------------------
# estimate_tier3 — BA he so (review 4.2; khoi phuc spec 01 Lop 4b)
# ---------------------------------------------------------------------------
def _tier3_synthetic(n=3000, seed=9):
    """r = beta*g + theta_oil*oil + theta_vix*vix + lam*direct + eps."""
    rng = np.random.default_rng(seed)
    g = rng.standard_normal(n)                        # global shock (innovation)
    oil = rng.standard_normal(n)
    vix = rng.standard_normal(n)
    direct = rng.standard_normal(n)                   # GPR^{c,⊥} innovation
    beta, theta_oil, theta_vix, lam = 0.25, -0.4, -0.3, -0.2
    r = (beta * g + theta_oil * oil + theta_vix * vix + lam * direct
         + rng.standard_normal(n) * 0.2)
    df = pd.DataFrame({"RET": r, "G_INNOV": g, "oil": oil, "vix": vix,
                       "DIRECT": direct})
    return df, dict(beta=beta, theta_oil=theta_oil, theta_vix=theta_vix, lam=lam)


def _coef(res: pd.DataFrame, h: int, term: str) -> float:
    row = res[(res["horizon"] == h) & (res["term"] == term)]
    assert len(row) == 1, f"term {term} @h={h}: {len(row)} rows"
    return float(row["coef"].iloc[0])


def test_estimate_tier3_recovers_three_coefficients():
    df, true = _tier3_synthetic()
    res = t3.estimate_tier3(
        df, market_ret="RET",
        global_shocks=["G_INNOV"],
        macro_channels=["oil", "vix"],
        direct_shock="DIRECT",
        controls=[], horizons=[0],
    )
    assert _coef(res, 0, "G_INNOV") == pytest.approx(true["beta"], abs=0.05)
    assert _coef(res, 0, "oil") == pytest.approx(true["theta_oil"], abs=0.05)
    assert _coef(res, 0, "vix") == pytest.approx(true["theta_vix"], abs=0.05)
    assert _coef(res, 0, "DIRECT") == pytest.approx(true["lam"], abs=0.05)


def test_estimate_tier3_roles_labelled():
    df, _ = _tier3_synthetic(n=500)
    res = t3.estimate_tier3(
        df, market_ret="RET", global_shocks=["G_INNOV"],
        macro_channels=["oil", "vix"], direct_shock="DIRECT",
        horizons=[0, 1],
    )
    roles = res.set_index("term")["role"].to_dict()
    assert roles["G_INNOV"] == "beta"
    assert roles["oil"] == "theta" and roles["vix"] == "theta"
    assert roles["DIRECT"] == "lambda"
    # SE va p-value phai co va hop le
    assert (res["se"] > 0).all()
    assert res["pvalue"].between(0, 1).all()


def test_estimate_tier3_direct_shock_optional():
    """Track daily VN: direct_shock=None (khong co daily country shock — CLAUDE.md #10)."""
    df, _ = _tier3_synthetic(n=500)
    res = t3.estimate_tier3(
        df, market_ret="RET", global_shocks=["G_INNOV"],
        macro_channels=["oil", "vix"], direct_shock=None,
        horizons=[0],
    )
    assert "lambda" not in set(res["role"])
    assert {"beta", "theta"} <= set(res["role"])


# ---------------------------------------------------------------------------
# convolve_indirect — tich chap (review 4.1)
# ---------------------------------------------------------------------------
def _toy_irfs():
    """IRF do choi 2 kenh, 2 buoc — tinh tay duoc."""
    gamma = {"oil": pd.Series([0.5, 0.2], index=[0, 1]),
             "vix": pd.Series([0.3, 0.1], index=[0, 1])}
    theta = {"oil": pd.Series([-0.4, -0.1], index=[0, 1]),
             "vix": pd.Series([-0.2, -0.05], index=[0, 1])}
    return gamma, theta


def test_convolution_matches_hand_computation():
    gamma, theta = _toy_irfs()
    out = t3.convolve_indirect(gamma, theta, horizons=[0, 1])
    # h=0: γ(0)·θ(0)
    ind0 = 0.5 * -0.4 + 0.3 * -0.2                      # -0.26
    # h=1: γ(0)·θ(1) + γ(1)·θ(0)
    ind1_oil = 0.5 * -0.1 + 0.2 * -0.4                  # -0.13
    ind1_vix = 0.3 * -0.05 + 0.1 * -0.2                 # -0.035
    assert out.loc[0, "indirect_total"] == pytest.approx(ind0)
    assert out.loc[1, "oil"] == pytest.approx(ind1_oil)
    assert out.loc[1, "vix"] == pytest.approx(ind1_vix)
    assert out.loc[1, "indirect_total"] == pytest.approx(ind1_oil + ind1_vix)


def test_convolution_differs_from_same_horizon_product():
    """Cong thuc v1 (nhan cung horizon) phai KHAC — day chinh la bug review 4.1."""
    gamma, theta = _toy_irfs()
    out = t3.convolve_indirect(gamma, theta, horizons=[1])
    same_h_product = (gamma["oil"][1] * theta["oil"][1]
                      + gamma["vix"][1] * theta["vix"][1])   # -0.025 (SAI)
    assert out.loc[1, "indirect_total"] != pytest.approx(same_h_product)


def test_transmission_decomposition_total():
    """Total^global(h) = beta(h) + Indirect(h); domestic = lambda(h)."""
    gamma_df = pd.DataFrame({
        "macro_var": ["oil", "oil", "vix", "vix"],
        "shock": ["GPRD"] * 4,
        "horizon": [0, 1, 0, 1],
        "beta": [0.5, 0.2, 0.3, 0.1],
    })
    tier3_coefs = pd.DataFrame({
        "horizon": [0, 0, 0, 0, 1, 1, 1, 1],
        "term": ["GPRD", "oil", "vix", "D", "GPRD", "oil", "vix", "D"],
        "role": ["beta", "theta", "theta", "lambda"] * 2,
        "coef": [0.25, -0.4, -0.2, -0.15, 0.10, -0.1, -0.05, -0.08],
    })
    out = t3.transmission_decomposition(gamma_df, tier3_coefs, shock="GPRD",
                                        horizons=[0, 1])
    ind0 = 0.5 * -0.4 + 0.3 * -0.2                       # -0.26
    ind1 = (0.5 * -0.1 + 0.2 * -0.4) + (0.3 * -0.05 + 0.1 * -0.2)
    assert out.loc[0, "beta_global_direct"] == pytest.approx(0.25)
    assert out.loc[0, "indirect"] == pytest.approx(ind0)
    assert out.loc[0, "total_global"] == pytest.approx(0.25 + ind0)
    assert out.loc[1, "total_global"] == pytest.approx(0.10 + ind1)
    assert out.loc[0, "domestic"] == pytest.approx(-0.15)
    assert out.loc[1, "domestic"] == pytest.approx(-0.08)


# ---------------------------------------------------------------------------
# shapley_r2 — thay θ²Var/Var (review 4.5)
# ---------------------------------------------------------------------------
def test_shapley_shares_sum_to_r2():
    n = 4000
    rng = np.random.default_rng(11)
    # 3 kenh TUONG QUAN nhau — truong hop nai ve θ²Var/Var sai
    z = rng.standard_normal(n)
    oil = z + rng.standard_normal(n) * 0.6
    vix = z + rng.standard_normal(n) * 0.6
    d = rng.standard_normal(n)
    r = 0.5 * oil + 0.4 * vix + 0.3 * d + rng.standard_normal(n) * 0.5
    df = pd.DataFrame({"r": r, "oil": oil, "vix": vix, "direct": d})

    out = t3.shapley_r2(df, y="r", channels=["oil", "vix", "direct"])
    shares = out["shares"]
    # Tong share = R2 full (tinh chat co ban cua Shapley/LMG)
    assert sum(shares.values()) == pytest.approx(out["r2_full"], abs=1e-9)
    # Moi kenh co dong gop duong o day (deu co he so that > 0)
    assert all(v > 0 for v in shares.values())
    # Doi chung ly do bo cong thuc cu (review 4.5): θ²Var/Var bo term hiep phuong
    # sai 2θθ·cov nen KHONG cong lai bang R² — cov duong thi hut duoi, cov am thi
    # vuot tren. O day (cov duong manh) lech ~0.3 R². Shapley thi cong dung R².
    import statsmodels.api as sm
    X = sm.add_constant(df[["oil", "vix", "direct"]])
    res = sm.OLS(df["r"], X).fit()
    naive = sum(res.params[c] ** 2 * df[c].var() for c in ["oil", "vix", "direct"])
    naive_share = naive / df["r"].var()
    assert abs(naive_share - out["r2_full"]) > 0.2       # lech xa — khong dung duoc


def test_shapley_with_controls_baseline():
    """Controls luon trong model; share phan ra phan R2 TREN baseline controls."""
    n = 3000
    rng = np.random.default_rng(13)
    ctrl = rng.standard_normal(n)
    oil = rng.standard_normal(n)
    r = 1.0 * ctrl + 0.5 * oil + rng.standard_normal(n) * 0.5
    df = pd.DataFrame({"r": r, "oil": oil, "ctrl": ctrl})
    out = t3.shapley_r2(df, y="r", channels=["oil"], controls=["ctrl"])
    assert sum(out["shares"].values()) == pytest.approx(
        out["r2_full"] - out["r2_baseline"], abs=1e-9)
    assert out["r2_baseline"] > 0.3                      # ctrl giai thich phan lon


def test_variance_decomposition_removed():
    """Cong thuc nai ve da bi XOA (CLAUDE.md #12) — khong con goi duoc."""
    assert not hasattr(t3, "variance_decomposition")
    assert not hasattr(t3, "mediation_analysis")
