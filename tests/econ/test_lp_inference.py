"""Test suy dien LP: lag augmentation + HC1 + dai sup-t + hoi quy phan vi.

docs/14 M8/M9. Ba thu nay da pre-register o SCA-01.lp_inference (lag_augmented_LP /
se: white / bands: sup_t_simultaneous) — code chi la thuc thi spec da khoa.

Test o day khong kiem "ket qua dep" ma kiem TINH CHAT:
  - lag augmentation them lag cua CA y LAN shock (thieu lag shock la sup do co so
    bo HAC — xem docstring local_projection),
  - SE la EHW/HC1 chu khong phai HAC,
  - dai sup-t va SE pointwise den tu CUNG mot ma tran hiep phuong sai,
  - dai sup-t RONG hon pointwise (neu khong thi no khong sua duoc gi),
  - tai lap duoc theo seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from gpr_engine.econometrics.local_projection import run_local_projection

H = list(range(0, 9))


@pytest.fixture
def panel() -> pd.DataFrame:
    """y dai dang (AR(1) rho=0.9) phan ung voi shock — dung mien MO-PM nham toi."""
    rng = np.random.default_rng(11)
    n = 600
    shock = rng.normal(0, 1, n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.9 * y[t - 1] + 0.5 * shock[t - 1] + rng.normal(0, 1)
    ctrl = rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "shock": shock, "ctrl": ctrl})


# ---------------------------------------------------------------------------
# Tuong thich nguoc — ban cu KHONG duoc doi
# ---------------------------------------------------------------------------
def test_default_is_still_hac_and_unchanged(panel):
    """Mac dinh van la HAC/Newey-West. Doi mac dinh = doi moi report da sinh."""
    out = run_local_projection(panel, y="y", shock="shock", horizons=H)
    manual = []
    for h in H:
        d = pd.concat([panel["y"].shift(-h).rename("__y__"), panel[["shock"]]],
                      axis=1).dropna()
        res = sm.OLS(d["__y__"], sm.add_constant(d[["shock"]])).fit(
            cov_type="HAC", cov_kwds={"maxlags": max(max(H), h)})
        manual.append(res.bse["shock"])
    np.testing.assert_allclose(out["se"].to_numpy(), manual, rtol=1e-10)
    assert "supt_c" not in out.columns, "sup-t phai tat mac dinh"


# ---------------------------------------------------------------------------
# M8a — lag augmentation
# ---------------------------------------------------------------------------
def test_lag_augmented_includes_lags_of_both_y_and_shock(panel):
    """Dieu kien then chot MO-PM: lag cua y VA lag cua shock, khong chi lag y.

    Thieu lag shock -> regressor chua partial-out thanh innovation -> co so bo HAC
    sup do. Test doc thang danh sach term de khong the lang le bo mat mot ve.
    """
    out = run_local_projection(panel, y="y", shock="shock", horizons=[0, 1, 2],
                               inference="lag_augmented", lags=3, return_all=True)
    terms = set(out["term"])
    for k in (1, 2, 3):
        assert f"__la_y_l{k}" in terms, f"thieu lag {k} cua y"
        assert f"__la_shock_l{k}" in terms, f"thieu lag {k} cua SHOCK"


def test_lag_augmented_uses_hc1_not_hac(panel):
    """SE che do lag_augmented = HC1 chinh xac, khong phai HAC."""
    lags = 2
    out = run_local_projection(panel, y="y", shock="shock", horizons=H,
                               inference="lag_augmented", lags=lags)
    work = panel.copy()
    cols = ["shock"]
    for c in ("y", "shock"):
        for k in range(1, lags + 1):
            work[f"l_{c}_{k}"] = work[c].shift(k)
            cols.append(f"l_{c}_{k}")
    manual = []
    for h in H:
        d = pd.concat([work["y"].shift(-h).rename("__y__"), work[cols]],
                      axis=1).dropna()
        manual.append(sm.OLS(d["__y__"], sm.add_constant(d[cols]))
                      .fit(cov_type="HC1").bse["shock"])
    np.testing.assert_allclose(out["se"].to_numpy(), manual, rtol=1e-10)


def test_lag_augmented_rejects_zero_lags(panel):
    """lags=0 khong phai lag-augmented — phai bao loi thay vi im lang tra LP tran."""
    with pytest.raises(ValueError, match="lags >= 1"):
        run_local_projection(panel, y="y", shock="shock", horizons=[0, 1],
                             inference="lag_augmented", lags=0)


def test_invalid_inference_rejected(panel):
    with pytest.raises(ValueError, match="inference"):
        run_local_projection(panel, y="y", shock="shock", horizons=[0],
                             inference="newey_west")


# ---------------------------------------------------------------------------
# M8b — dai sup-t
# ---------------------------------------------------------------------------
def test_supt_diagonal_matches_hc1(panel):
    """Duong cheo ma tran hiep phuong sai (nguon cua sup-t) = SE pointwise HC1.

    Day la test quan trong nhat cua khoi sup-t: neu hai thu nay lech thi report
    dang chua HAI bo sai so chuan khac nhau — dai pointwise noi mot dang, dai
    sup-t noi mot dang — va khong ai phat hien duoc bang mat.
    """
    from gpr_engine.econometrics.local_projection import _influence

    lags, h = 2, 3
    work = panel.copy()
    cols = ["shock"]
    for c in ("y", "shock"):
        for k in range(1, lags + 1):
            work[f"l_{c}_{k}"] = work[c].shift(k)
            cols.append(f"l_{c}_{k}")
    d = pd.concat([work["y"].shift(-h).rename("__y__"), work[cols]], axis=1).dropna()
    Xc = sm.add_constant(d[cols])
    res = sm.OLS(d["__y__"], Xc).fit(cov_type="HC1")

    psi = _influence(np.asarray(Xc, float), np.asarray(res.resid, float),
                     1 + cols.index("shock"))
    assert np.sqrt((psi ** 2).sum()) == pytest.approx(res.bse["shock"], rel=1e-10)


def test_supt_band_is_wider_than_pointwise(panel):
    """c_supt > z_pointwise va dai rong hon o MOI horizon — neu khong thi vo dung."""
    out = run_local_projection(panel, y="y", shock="shock", horizons=H,
                               inference="lag_augmented", lags=2,
                               simultaneous=True, ci=0.90)
    c = out["supt_c"].iloc[0]
    assert c > 1.6449, f"supt_c={c:.3f} khong lon hon z pointwise 1.645"
    assert (out["ci_high_supt"] >= out["ci_high"]).all()
    assert (out["ci_low_supt"] <= out["ci_low"]).all()
    # Cung mot c cho moi horizon (dai sup-t la SE nhan hang so chung)
    assert out["supt_c"].nunique() == 1


def test_supt_is_reproducible_by_seed(panel):
    """Con so vao report phai tai lap duoc (#4 versioning)."""
    kw = dict(y="y", shock="shock", horizons=H, inference="lag_augmented",
              lags=2, simultaneous=True)
    a = run_local_projection(panel, seed=7, **kw)
    b = run_local_projection(panel, seed=7, **kw)
    c = run_local_projection(panel, seed=8, **kw)
    assert a["supt_c"].iloc[0] == b["supt_c"].iloc[0]
    assert a["supt_c"].iloc[0] != c["supt_c"].iloc[0], "seed khac phai cho draw khac"


def test_supt_single_horizon_falls_back_to_pointwise(panel):
    """1 horizon thi khong co gi de 'sup' — c phai bang z pointwise."""
    out = run_local_projection(panel, y="y", shock="shock", horizons=[2],
                               inference="lag_augmented", lags=2,
                               simultaneous=True, ci=0.90)
    assert out["supt_c"].iloc[0] == pytest.approx(1.6449, abs=1e-3)


# ---------------------------------------------------------------------------
# M9 — hoi quy phan vi
# ---------------------------------------------------------------------------
def test_quantile_median_close_to_ols_under_symmetric_errors(panel):
    """tau=0.5 voi sai so doi xung -> he so gan OLS. Kiem tra day noi dung dung."""
    q = run_local_projection(panel, y="y", shock="shock", horizons=[1, 2],
                             method="quantile", tau=0.5)
    o = run_local_projection(panel, y="y", shock="shock", horizons=[1, 2])
    for h in (1, 2):
        assert q.loc[h, "beta"] == pytest.approx(o.loc[h, "beta"], abs=0.25)


def test_quantile_tails_differ_under_asymmetric_shock_effect():
    """tau=0.10 va tau=0.90 phai TACH khi shock tac dong len duoi duoi.

    Day la ly do docs/14 dat primary_cell.funcform=quantile_tau_0.10: neu quantile
    chi lap lai OLS thi no khong them thong tin gi.
    """
    rng = np.random.default_rng(3)
    n = 1500
    shock = rng.normal(0, 1, n)
    # Location-scale DON DIEU theo shock: Q_y(tau|shock) = Q_eps(tau)·exp(0.4·shock).
    # Q_eps(.90)>0 -> doc len; Q_eps(.10)<0 -> doc xuong; trung vi ~ phang.
    # (Ban dau dung scale ~ |shock| — DOI XUNG, nen QR tuyen tinh tren shock khong
    #  the bat duoc va ca hai duoi deu ra ~0. Loi cua DGP, khong phai cua QR.)
    y = rng.normal(0, 1, n) * np.exp(0.4 * shock)
    df = pd.DataFrame({"y": y, "shock": shock})
    lo = run_local_projection(df, y="y", shock="shock", horizons=[0],
                              method="quantile", tau=0.10).loc[0, "beta"]
    hi = run_local_projection(df, y="y", shock="shock", horizons=[0],
                              method="quantile", tau=0.90).loc[0, "beta"]
    assert hi - lo > 0.3, f"tau=.90 ({hi:.3f}) khong tach khoi tau=.10 ({lo:.3f})"


def test_quantile_rejects_bad_tau(panel):
    with pytest.raises(ValueError, match="tau"):
        run_local_projection(panel, y="y", shock="shock", horizons=[0],
                             method="quantile", tau=1.5)


def test_supt_with_quantile_raises_not_silently_wrong(panel):
    """simultaneous + quantile -> NotImplementedError, KHONG tra dai sai.

    Ham anh huong cua QuantReg can uoc luong sparsity tai tau; dung cong thuc OLS
    o day se cho dai sup-t sai ma khong ai thay. Tha bao loi.
    """
    with pytest.raises(NotImplementedError, match="bootstrap"):
        run_local_projection(panel, y="y", shock="shock", horizons=H,
                             method="quantile", tau=0.1, simultaneous=True)
