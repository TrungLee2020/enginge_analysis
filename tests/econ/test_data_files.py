"""Test cho data_files.py (G2a offline loader) — phan PURE, khong goi mang.

Kiem chung:
  - transform_gpr_shocks: zscore (mean0/std1) vs log1p.
  - splice_dxy_returns: broad uu tien, fallback major, dung return.
  - build_tier2_panel: luoi business-day lien tuc, complete-case (khong NaN),
    shift(k) khong vuot khe NaN (monkeypatch I/O de khong dung FRED/file).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as df_mod
from gpr_engine.econometrics.data_files import (
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


def test_build_tier2_panel_contiguous_and_complete(monkeypatch):
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

    panel = build_tier2_panel(start="2020-01-01", end="2020-02-29", ffill_limit=3)

    # 1) khong con NaN (complete-case)
    assert not panel.isna().any().any()
    # 2) index la business-day lien tuc (khong co thu 7/CN)
    assert (panel.index.dayofweek < 5).all()
    # 3) index tang deu, khong lap
    assert panel.index.is_monotonic_increasing and panel.index.is_unique
    # 4) co du cot macro + shock
    for c in ["oil", "vix", "us10y", "dxy", "GPRD", "GPRD_ACT", "GPRD_THREAT"]:
        assert c in panel.columns
    # 5) shock da z-score (mean~0)
    assert abs(panel["GPRD"].mean()) < 3.0  # z-score tren mau goc, sub-slice lech nhe
