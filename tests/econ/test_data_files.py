"""Test cho data_files.py (G2a offline loader) — phan PURE, khong goi mang.

Kiem chung:
  - transform_gpr_shocks: zscore (mean0/std1) vs log1p.
  - splice_dxy_returns: broad uu tien, fallback major, dung return.
  - build_tier2_panel: chi giu phien macro that, complete-case (khong NaN).
  - information time: GPR D chi dung tu D+1, tin cuoi tuan vao phien tiep theo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as df_mod
from gpr_engine.econometrics.data_files import (
    align_daily_gpr_to_information_time,
    align_daily_shock_measures_to_information_time,
    build_tier2_panel,
    splice_dxy_returns,
    transform_gpr_shocks,
)


def test_transform_gpr_shocks_zscore():
    raw = pd.DataFrame({"GPRD": [10.0, 20, 30, 40, 400]})  # co spike
    out = transform_gpr_shocks(raw, method="zscore")
    assert out["GPRD"].mean() == pytest.approx(0.0, abs=1e-9)
    assert out["GPRD"].std() == pytest.approx(1.0, abs=1e-9)
    # spike van la gia tri lon nhat (khong bi lam phang nhu log1p)
    assert out["GPRD"].idxmax() == 4


def test_transform_gpr_shocks_log1p_flattens_spike():
    raw = pd.DataFrame({"GPRD": [10.0, 400]})
    out = transform_gpr_shocks(raw, method="log1p")
    # log1p ep 400 -> ~6 : ti le spike/base tut manh so voi raw
    assert out["GPRD"].iloc[1] < 7
    assert (out["GPRD"] == np.log1p(raw["GPRD"])).all()


def test_transform_gpr_shocks_bad_method():
    with pytest.raises(ValueError):
        transform_gpr_shocks(pd.DataFrame({"GPRD": [1.0]}), method="nope")


def test_splice_dxy_broad_priority_and_fallback():
    idx = pd.bdate_range("2000-01-03", periods=6)
    # major phu het; broad chi 3 ky cuoi
    major = pd.Series([100.0, 101, 102, 103, 104, 105], index=idx)
    broad = pd.Series([np.nan, np.nan, np.nan, 200.0, 202, 204], index=idx)
    dxy = splice_dxy_returns(broad, major)
    # ky cuoi: dung return cua broad (204/202-1 ~ ln), khong phai major
    assert dxy.loc[idx[5]] == pytest.approx(np.log(204 / 202), abs=1e-9)
    # ky dau (broad NaN): fallback major
    assert dxy.loc[idx[1]] == pytest.approx(np.log(101 / 100), abs=1e-9)


def test_build_tier2_panel_uses_observed_macro_days_and_is_complete(monkeypatch):
    # GPR daily gia (ngay lich, gom ca cuoi tuan)
    cal = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    gpr = pd.DataFrame({s: np.arange(len(cal), dtype=float)
                        for s in ["GPRD", "GPRD_ACT", "GPRD_THREAT"]}, index=cal)

    # macro da transform, business day, CO khe NaN rai rac (mo phong FRED thua ngay)
    bdays = pd.bdate_range("2020-01-01", "2020-02-29")
    macro = pd.DataFrame({
        "oil": np.random.default_rng(0).standard_normal(len(bdays)),
        "vix": 20 + np.random.default_rng(1).standard_normal(len(bdays)),
        "us10y": np.random.default_rng(2).standard_normal(len(bdays)) * 0.01,
        "dxy": np.random.default_rng(3).standard_normal(len(bdays)) * 0.003,
    }, index=bdays)
    macro.iloc[5, 0] = np.nan   # 1 khe NaN oil
    macro.iloc[10, 1] = np.nan  # 1 khe NaN vix

    monkeypatch.setattr(df_mod, "load_gpr_daily", lambda path=None: gpr)
    monkeypatch.setattr(
        df_mod, "load_macro_transformed",
        lambda *a, **k: macro)

    with pytest.warns(DeprecationWarning, match="ffill_limit"):
        panel = build_tier2_panel(
            start="2020-01-01", end="2020-02-29", ffill_limit=3,
            shock_method="zscore")

    # 1) khong con NaN (complete-case)
    assert not panel.isna().any().any()
    # 2) chi co phien business-day that, khong tao return gia bang forward-fill
    assert (panel.index.dayofweek < 5).all()
    assert bdays[5] not in panel.index
    assert bdays[10] not in panel.index
    # 3) index tang, khong lap
    assert panel.index.is_monotonic_increasing and panel.index.is_unique
    # 4) co du cot macro + shock
    for c in ["oil", "vix", "us10y", "dxy", "GPRD", "GPRD_ACT", "GPRD_THREAT"]:
        assert c in panel.columns
    # 5) shock da z-score (mean~0)
    assert abs(panel["GPRD"].mean()) < 3.0  # z-score tren mau goc, sub-slice lech nhe


def test_daily_gpr_is_available_d_plus_one_and_weekend_rolls_forward():
    """Fri/Sat/Sun news chi vao Monday; Monday news chi vao Tuesday."""
    idx = pd.date_range("2020-01-03", "2020-01-06", freq="D")  # Fri..Mon
    gpr = pd.DataFrame({"GPRD": [3.0, 5.0, 7.0, 11.0]}, index=idx)
    decisions = pd.DatetimeIndex(["2020-01-06", "2020-01-07"])

    out = align_daily_gpr_to_information_time(
        gpr, decisions, publish_lag_days=1, aggregation="mean")

    assert out.loc[pd.Timestamp("2020-01-06"), "GPRD"] == pytest.approx(5.0)
    assert out.loc[pd.Timestamp("2020-01-07"), "GPRD"] == pytest.approx(11.0)


def test_daily_alignment_requires_explicit_aggregation():
    gpr = pd.DataFrame(
        {"GPRD": [1.0]}, index=pd.DatetimeIndex(["2020-01-03"]))
    with pytest.raises(ValueError, match="aggregation"):
        align_daily_gpr_to_information_time(
            gpr, pd.DatetimeIndex(["2020-01-06"]), publish_lag_days=1)


def test_daily_shock_alignment_uses_mean_level_and_max_jump():
    """Composite duoc ghep sau aggregation, nen spike cuoi tuan khong bi pha loang."""
    idx = pd.date_range("2020-01-03", "2020-01-05", freq="D")  # Fri..Sun
    measures = pd.DataFrame({
        "GPRD_LEVEL": [3.0, 5.0, 7.0],
        "GPRD_INNOV": [-1.0, 2.0, 1.0],
        "GPRD_JUMP": [0.0, 9.0, 0.0],
        "GPRD_LEVEL_PLUS_JUMP": [3.0, 14.0, 7.0],
    }, index=idx)

    out = align_daily_shock_measures_to_information_time(
        measures,
        pd.DatetimeIndex(["2020-01-06"]),
        publish_lag_days=1,
    )

    assert out.loc["2020-01-06", "GPRD_LEVEL"] == pytest.approx(5.0)
    assert out.loc["2020-01-06", "GPRD_INNOV"] == pytest.approx(2 / 3)
    assert out.loc["2020-01-06", "GPRD_JUMP"] == pytest.approx(9.0)
    assert out.loc["2020-01-06", "GPRD_LEVEL_PLUS_JUMP"] == pytest.approx(14.0)
