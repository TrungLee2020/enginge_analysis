"""Test NOI M8/M9 vao cascade: tang 2 + tang 3 phai goi duoc suy dien da khoa.

Boi canh (rà 2026-08-02): `local_projection.py` co lag_augmented / sup-t /
quantile tu M8-M9, nhung `estimate_tier2` va `estimate_tier3` KHONG truyen tham
so nao xuong — nen bang γ cua Phase 1a chi chay duoc bang dung cai inference ma
`SCA-01.lp_inference` noi la sai. Cac test o day khoa duong day do.

Kem hai cong an toan phat hien luc noi:
  - simultaneous=True + inference="hac" tron HAI bo sai so chuan (Omega EHW voi
    se HAC) -> phai RAISE (docs/15 §5 muc 4),
  - simultaneous=True + return_all=True truoc day IM LANG khong tra dai nao.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.local_projection import run_local_projection
from gpr_engine.econometrics.tier2_global_macro import estimate_tier2
from gpr_engine.econometrics.tier3_country import estimate_tier3

H = list(range(0, 7))


@pytest.fixture
def panel() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    n = 500
    shock = rng.normal(0, 1, n)
    dom = rng.normal(0, 1, n)
    oil = np.zeros(n)
    vix = np.zeros(n)
    for t in range(1, n):
        oil[t] = 0.7 * oil[t - 1] + 0.4 * shock[t - 1] + rng.normal(0, 1)
        vix[t] = 0.8 * vix[t - 1] + 0.2 * shock[t] + rng.normal(0, 1)
    ret = 0.3 * oil + 0.2 * dom + rng.normal(0, 1, n)
    return pd.DataFrame({"oil": oil, "vix": vix, "GPRD": shock,
                         "GPRC_ORTH": dom, "ret": ret})


# ---------------------------------------------------------------------------
# Cong an toan: sup-t chi hop le voi lag_augmented
# ---------------------------------------------------------------------------
def test_supt_with_hac_raises_instead_of_mixing_standard_errors(panel):
    """Omega tu ham anh huong EHW + `se` HAC = hai bo sai so chuan trong mot dai.

    Day dung la loi ma `test_supt_diagonal_matches_hc1` sinh ra de chan, chi khac
    la no lot qua duoc vi hai nguon nam o hai dong code.
    """
    with pytest.raises(ValueError, match="lag_augmented"):
        run_local_projection(panel, y="oil", shock="GPRD", horizons=H,
                             inference="hac", simultaneous=True)


def test_supt_default_inference_also_blocked(panel):
    """Mac dinh la 'hac' — goi simultaneous=True ma quen doi inference phai no."""
    with pytest.raises(ValueError, match="lag_augmented"):
        run_local_projection(panel, y="oil", shock="GPRD", horizons=H,
                             simultaneous=True)


# ---------------------------------------------------------------------------
# sup-t voi return_all (duong tang 3 di)
# ---------------------------------------------------------------------------
def test_return_all_no_longer_drops_supt_silently(panel):
    """Truoc day return_all=True tra ve TRUOC khoi sup-t: psi tinh xong roi vut.

    Tang 3 doc beta/theta/lambda theo horizon — do chinh la cho can dai dong thoi.
    """
    out = run_local_projection(
        panel, y="ret", shock="GPRD", controls=["oil", "GPRC_ORTH"],
        horizons=H, return_all=True, inference="lag_augmented", lags=2,
        simultaneous=True)
    for col in ("supt_c", "ci_low_supt", "ci_high_supt"):
        assert col in out.columns
    assert out["supt_c"].notna().all()
    assert (out["ci_high_supt"] >= out["ci_high"] - 1e-12).all()
    assert (out["ci_low_supt"] <= out["ci_low"] + 1e-12).all()


def test_supt_constant_differs_across_terms(panel):
    """Moi he so co ma tran tuong quan qua horizon RIENG -> hang so c rieng.

    Dung chung mot c cho beta/theta/lambda la ap dac tinh cua he so nay len he so
    kia; neu test nay do thi ai do da gop chung lai.
    """
    out = run_local_projection(
        panel, y="ret", shock="GPRD", controls=["oil", "GPRC_ORTH"],
        horizons=H, return_all=True, inference="lag_augmented", lags=2,
        simultaneous=True)
    cs = out.groupby("term")["supt_c"].first()
    assert cs.nunique() > 1, f"moi term cung mot c={cs.unique()} — nghi bi gop"
    assert (cs > 1.6449).all(), "c sup-t phai lon hon z pointwise o moi term"


# ---------------------------------------------------------------------------
# Tang 2 — pass-through
# ---------------------------------------------------------------------------
def test_tier2_default_unchanged(panel):
    """Mac dinh van la HAC/pointwise: doi mac dinh = doi moi report G2a da sinh."""
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=["GPRD"],
                         horizons=H, macro_lags=1)
    assert "supt_c" not in out.columns


def test_tier2_passes_inference_and_supt_through(panel):
    """Spec Phase 1a: lag_augmented + HC1 + sup-t. Truoc day khong goi duoc."""
    out = estimate_tier2(panel, macro_vars=["oil", "vix"], shocks=["GPRD"],
                         horizons=H, macro_lags=0,
                         inference="lag_augmented", lags=2, simultaneous=True)
    for col in ("ci_low_supt", "ci_high_supt", "supt_c"):
        assert col in out.columns
    assert out["supt_c"].notna().all()
    # Hai outcome khac nhau -> hang so sup-t khac nhau (tinh tren tung hoi quy).
    assert out.groupby("macro_var")["supt_c"].first().nunique() == 2


def test_tier2_lag_augmented_refuses_duplicate_macro_lags(panel):
    """macro_lags + lag augmentation = lag cua M them HAI LAN -> X'X suy bien.

    pinv KHONG bao loi, no chia doi he so giua hai cot trung khit va SE mat nghia
    — hong im lang, nen phai chan o cua vao.
    """
    with pytest.raises(ValueError, match="macro_lags"):
        estimate_tier2(panel, macro_vars=["oil"], shocks=["GPRD"],
                       horizons=H, macro_lags=1, inference="lag_augmented")


def test_tier2_quantile_runs_and_differs_from_ols(panel):
    """method/tau phai xuong toi LP; tau=.10 khong duoc trung OLS."""
    ols = estimate_tier2(panel, macro_vars=["oil"], shocks=["GPRD"],
                         horizons=[1, 2], macro_lags=1)
    q10 = estimate_tier2(panel, macro_vars=["oil"], shocks=["GPRD"],
                         horizons=[1, 2], macro_lags=1,
                         method="quantile", tau=0.10)
    assert not np.allclose(ols["beta"], q10["beta"]), "quantile khong xuong toi LP"


# ---------------------------------------------------------------------------
# Tang 3 — pass-through
# ---------------------------------------------------------------------------
def test_tier3_passes_supt_through_and_keeps_roles(panel):
    out = estimate_tier3(
        panel, market_ret="ret", macro_channels=["oil"],
        direct_shock="GPRC_ORTH", global_shocks=["GPRD"], horizons=H,
        inference="lag_augmented", lags=2, simultaneous=True)
    for col in ("ci_low_supt", "ci_high_supt", "supt_c"):
        assert col in out.columns
    roles = set(out["role"])
    assert {"beta", "theta", "lambda"} <= roles
    # Cot lag augmentation duoc gan nhan tuong minh, khong de NaN.
    assert out["role"].notna().all()
    assert "lag_augmentation" in roles


def test_tier3_default_unchanged(panel):
    out = estimate_tier3(panel, market_ret="ret", macro_channels=["oil"],
                         direct_shock="GPRC_ORTH", global_shocks=["GPRD"],
                         horizons=H)
    assert "supt_c" not in out.columns
    assert set(out["role"]) == {"beta", "theta", "lambda"}
