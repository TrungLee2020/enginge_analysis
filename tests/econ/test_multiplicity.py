"""Test hieu chinh boi giua outcome (docs/14 M10, `multiplicity.py`).

Test tinh chat cua thu tuc, khong test "ket qua dep":
  - Holm khop dinh nghia step-down tren vi du tinh tay duoc,
  - m=1 thi khong phat gi (neu khong, ho mot phan tu tu lam kho chinh no),
  - NaN khong duoc dem vao m (mot o that bai ky thuat khong phai mot kiem dinh),
  - ho phai PHAN HOACH va phai PHU HET (bo im lang mot outcome = lam nhe FWER),
  - hieu chinh trong ho B long hon toan bang C — dung huong docs/14 §6.6.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.multiplicity import (
    PREREGISTERED_OUTCOME_FAMILIES,
    holm,
    holm_by_family,
)


# ---------------------------------------------------------------------------
# Holm — thu tuc
# ---------------------------------------------------------------------------
def test_holm_matches_hand_computation():
    """m=4, alpha=0.10 -> nguong 0.025 / 0.0333 / 0.05 / 0.10, step-down."""
    p = [0.010, 0.030, 0.040, 0.500]
    out = holm(p, alpha=0.10)
    np.testing.assert_allclose(out["threshold"], [0.025, 0.1 / 3, 0.05, 0.10], rtol=1e-12)
    # p_(1)=0.010 <= 0.025 qua; p_(2)=0.030 <= 0.0333 qua; p_(3)=0.040 <= 0.05 qua;
    # p_(4)=0.500 > 0.10 dung.
    assert out["reject"].tolist() == [True, True, True, False]
    np.testing.assert_allclose(out["pvalue_adj"], [0.040, 0.090, 0.090, 0.500], rtol=1e-12)


def test_holm_step_down_stops_at_first_failure():
    """Gap p dau tien khong qua nguong -> DUNG, ke ca khi p sau nho hon nguong sau.

    Day la khac biet giua Holm va Bonferroni-tung-cai; lam sai cho ra FWER > alpha.
    """
    # p_(1)=0.09 > 0.10/3=0.0333 -> dung ngay, du p_(2)=0.09 <= 0.05? (khong) va
    # p_(3)=0.095 <= 0.10 (co, nhung khong duoc bac bo vi da dung).
    out = holm([0.09, 0.09, 0.095], alpha=0.10)
    assert not out["reject"].any()
    assert out.loc[2, "pvalue_adj"] == pytest.approx(0.27)   # bi don dieu hoa len


def test_holm_single_test_is_unpenalised():
    """m=1: nguong = alpha, p_adj = p. Ho mot phan tu (physical_channel: freight)
    khong duoc tu lam kho chinh no."""
    out = holm([0.06], alpha=0.10)
    assert out.loc[0, "threshold"] == pytest.approx(0.10)
    assert out.loc[0, "pvalue_adj"] == pytest.approx(0.06)
    assert bool(out.loc[0, "reject"])


def test_holm_ignores_nan_in_m():
    """Spec khong hoi tu = o trong, KHONG phai mot kiem dinh. Dem no vao m la tu
    phat vi mot that bai ky thuat."""
    with_nan = holm([0.010, np.nan, 0.030], alpha=0.10)
    without = holm([0.010, 0.030], alpha=0.10)
    assert np.isnan(with_nan.loc[1, "pvalue_adj"])
    assert not bool(with_nan.loc[1, "reject"])
    np.testing.assert_allclose(
        with_nan.loc[[0, 2], "pvalue_adj"].to_numpy(),
        without["pvalue_adj"].to_numpy(), rtol=1e-12)


def test_holm_is_conservative_relative_to_raw():
    """p_adj >= p luon dung — neu khong thi hieu chinh dang NOI LONG."""
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 40)
    out = holm(p, alpha=0.10)
    assert (out["pvalue_adj"] >= out["pvalue"] - 1e-12).all()


def test_holm_rejects_bad_input():
    with pytest.raises(ValueError, match="alpha"):
        holm([0.01], alpha=0.0)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        holm([0.01, 1.4])


# ---------------------------------------------------------------------------
# Ho kiem dinh — governance
# ---------------------------------------------------------------------------
@pytest.fixture
def gamma_table() -> pd.DataFrame:
    """Mot hang = mot (outcome, shock) tren CA duong IRF — khong phai mot horizon."""
    return pd.DataFrame({
        "macro_var": ["oil", "dxy", "vix", "us10y", "ip", "cpi", "infl_exp", "freight"],
        "shock": ["GPRD"] * 8,
        "pvalue": [0.004, 0.30, 0.02, 0.40, 0.03, 0.20, 0.60, 0.06],
    })


def test_family_b_is_looser_than_whole_table_c(gamma_table):
    """docs/14 §6.6: B (nhom pre-register) phai long hon C (ca bang 8 outcome).

    Neu hai cai cho cung ket qua thi lua chon §6.6 khong co hau qua va khong dang
    la mot quyet dinh governance.
    """
    b = holm_by_family(gamma_table, PREREGISTERED_OUTCOME_FAMILIES, alpha=0.10)
    c = holm_by_family(gamma_table, {"all": tuple(gamma_table["macro_var"])}, alpha=0.10)
    assert b["reject"].sum() > c["reject"].sum()
    # freight (ho 1 phan tu) song trong B, chet trong C.
    assert bool(b.loc[b["macro_var"] == "freight", "reject"].iloc[0])
    assert not bool(c.loc[c["macro_var"] == "freight", "reject"].iloc[0])


def test_family_sizes_match_preregistered_groups(gamma_table):
    """Ho lay tu SCA-01.report_axis_outcome: 4 / 3 / 1 (docs/14 §6.6 bang B)."""
    out = holm_by_family(gamma_table, PREREGISTERED_OUTCOME_FAMILIES)
    sizes = out.groupby("family")["family_size"].first().to_dict()
    assert sizes == {"asset_price": 4.0, "real_macro": 3.0, "physical_channel": 1.0}


def test_uncovered_outcome_raises(gamma_table):
    """Bo im lang mot outcome khoi hieu chinh = lam nhe FWER ma report khong ghi."""
    partial = {k: v for k, v in PREREGISTERED_OUTCOME_FAMILIES.items()
               if k != "physical_channel"}
    with pytest.raises(ValueError, match="freight"):
        holm_by_family(gamma_table, partial)
    # strict=False phai la lua chon CO CHU DICH, va khi do o do de trong.
    out = holm_by_family(gamma_table, partial, strict=False)
    row = out[out["macro_var"] == "freight"].iloc[0]
    assert pd.isna(row["family"]) and not bool(row["reject"])


def test_overlapping_families_raise(gamma_table):
    """Ho phai PHAN HOACH — outcome o hai ho bi phat hai lan."""
    bad = {"a": ("oil", "vix"), "b": ("vix", "dxy")}
    with pytest.raises(ValueError, match="hai ho|phan hoach|nam trong ca"):
        holm_by_family(gamma_table[gamma_table["macro_var"].isin(
            ["oil", "vix", "dxy"])], bad)


def test_no_default_family_exists():
    """`family` khong co mac dinh: chon ho SAU khi thay p-value la HARKing.

    §6.6 chua ky — ham phai bat caller khai bao, khong duoc tu chon giup.
    """
    import inspect
    sig = inspect.signature(holm_by_family)
    assert sig.parameters["family"].default is inspect.Parameter.empty
