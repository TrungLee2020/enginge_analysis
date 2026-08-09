"""`estimate_tier2(shock_groups=...)` — nhieu regressor trong CUNG mot hoi quy.

P1.4 cua docs/17_master_plan.md §6. Truoc thay doi nay, spec kep (§4.1) khong
chay duoc: `estimate_tier2` chi bao cao he so cua dung mot `shock`, regressor
thu hai chi co the nhet vao `controls` va he so cua no bi VUT.

Du lieu tong hop, deterministic (seed co dinh) — khong doc file, khong mang.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.tier2_global_macro import estimate_tier2


@pytest.fixture
def panel() -> pd.DataFrame:
    """oil phan ung voi CA HAI thanh phan, voi he so BIET TRUOC.

    ANTICIPATED co sd nho hon SURPRISE ~3 lan — tai lap dung tinh huong thang do
    cua chuoi that (Var(ANT)/Var(SUR) ~0.1).
    """
    rng = np.random.default_rng(7)
    n = 400
    idx = pd.date_range("1990-01-01", periods=n, freq="MS")
    ant = rng.normal(0, 0.1, n)
    sur = rng.normal(0, 0.3, n)
    oil = 2.0 * ant + 1.0 * sur + rng.normal(0, 0.05, n)
    return pd.DataFrame({"oil": oil, "A": ant, "S": sur}, index=idx)


def test_tra_ve_he_so_cua_MOI_thanh_vien_nhom(panel):
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                         shock_groups=[["A", "S"]], horizons=[0], macro_lags=0)
    assert set(out["shock"]) == {"A", "S"}
    assert set(out["spec"]) == {"A+S"}


def test_khong_tra_ve_he_so_control_va_lag(panel):
    """Control/lag augmentation la nuisance — doc chung nhu γ la sai."""
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                         shock_groups=[["A", "S"]], horizons=[0], macro_lags=1)
    assert set(out["shock"]) == {"A", "S"}
    assert not any(str(s).startswith("__") for s in out["shock"])


def test_he_so_khop_gia_tri_dat_ra(panel):
    """Hoi quy CHUNG phai lay lai duoc 2.0 va 1.0 — neu tach hai hoi quy rieng
    thi he so se lech do bo sot regressor kia."""
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                         shock_groups=[["A", "S"]], horizons=[0], macro_lags=0)
    b = out.set_index("shock")["beta"]
    assert abs(b["A"] - 2.0) < 0.15, b["A"]
    assert abs(b["S"] - 1.0) < 0.05, b["S"]


def test_beta_chuan_hoa_dao_thu_tu_so_voi_he_so_tho(panel):
    """Chinh la tai nan thang do cua E2, tai lap trong test.

    He so tho: A (2.0) > S (1.0). Chuan hoa: A×0.1=0.2 < S×0.3=0.3. Neu ai do
    bo cot `beta_standardized` di, test nay do.
    """
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                         shock_groups=[["A", "S"]], horizons=[0], macro_lags=0)
    r = out.set_index("shock")
    assert r.loc["A", "beta"] > r.loc["S", "beta"]
    assert r.loc["A", "beta_standardized"] < r.loc["S", "beta_standardized"]
    assert np.isclose(r.loc["A", "beta_standardized"],
                      r.loc["A", "beta"] * r.loc["A", "sd_regressor"])


def test_dung_chung_voi_shocks_thi_gop_mot_bang(panel):
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=["A"],
                         shock_groups=[["A", "S"]], horizons=[0], macro_lags=0)
    assert len(out) == 3                       # 1 hang rieng + 2 hang nhom
    solo = out[out["spec"].isna()]
    assert len(solo) == 1 and solo.iloc[0]["shock"] == "A"


def test_nhanh_cu_khong_doi_cot(panel):
    """Khong truyen shock_groups -> bang y het ban truoc P1.4."""
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=["A"],
                         horizons=[0], macro_lags=0)
    assert "spec" not in out.columns
    assert "beta_standardized" not in out.columns


def test_supt_moi_he_so_mot_dai_rieng(panel):
    """sup-t: hang so c phai RIENG tung he so — chung co ma tran tuong quan qua
    horizon khac nhau, dung chung mot c la sai."""
    out = estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                         shock_groups=[["A", "S"]], horizons=[0, 1, 2],
                         macro_lags=0, inference="lag_augmented",
                         simultaneous=True)
    cs = out.groupby("shock")["supt_c"].nunique()
    assert (cs == 1).all()                                  # 1 c cho moi he so
    assert out.groupby("shock")["supt_c"].first().nunique() > 1   # va khac nhau


def test_nhom_mot_phan_tu_thi_raise(panel):
    with pytest.raises(ValueError, match=">=2 regressor"):
        estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                       shock_groups=[["A"]], horizons=[0], macro_lags=0)


def test_nhom_trung_ten_thi_raise(panel):
    """Cot trung khit -> X'X suy bien, pinv chia doi he so ma khong bao loi."""
    with pytest.raises(ValueError, match="trung ten"):
        estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                       shock_groups=[["A", "A"]], horizons=[0], macro_lags=0)


def test_cot_thieu_thi_raise(panel):
    with pytest.raises(KeyError):
        estimate_tier2(panel, macro_vars=["oil"], shocks=[],
                       shock_groups=[["A", "KHONG_CO"]], horizons=[0], macro_lags=0)


def test_khong_co_shock_nao_thi_raise(panel):
    with pytest.raises(ValueError, match="it nhat mot"):
        estimate_tier2(panel, macro_vars=["oil"], shocks=[], horizons=[0])
