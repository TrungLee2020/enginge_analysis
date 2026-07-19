"""Test cho dataset.py — phan transform (pure, khong can PG).

Kiem chung cac bien doi bat buoc (docs/07 §0):
  - log1p_gpr: log(1+GPR)
  - dlog: log-difference cho gia (Oil, DXY)
  - transform_global_macro: Oil/DXY -> dln, VIX/US10Y giu level/diff dung
  - align_frames: gop nhieu series long -> wide, thang hang thoi gian
  - fill_weekend: gan GPR ngay nghi vao ngay giao dich ke tiep
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import dataset as ds


def test_log1p_gpr():
    s = pd.Series([0.0, np.e - 1, 9.0])
    out = ds.log1p_gpr(s)
    assert out.iloc[0] == pytest.approx(0.0)
    assert out.iloc[1] == pytest.approx(1.0)
    assert out.iloc[2] == pytest.approx(np.log(10.0))


def test_dlog_is_log_return():
    s = pd.Series([100.0, 110.0, 99.0])
    out = ds.dlog(s)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == pytest.approx(np.log(110 / 100))
    assert out.iloc[2] == pytest.approx(np.log(99 / 110))


def test_transform_global_macro_columns():
    n = 50
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    raw = pd.DataFrame({
        "BRENT": np.linspace(50, 60, n),
        "DXY": np.linspace(90, 95, n),
        "VIX": np.linspace(15, 25, n),
        "US10Y": np.linspace(1.0, 2.0, n),
    }, index=idx)
    out = ds.transform_global_macro(raw)
    # gia -> dln (co the co NaN dau); VIX level; US10Y diff
    for col in ["oil", "dxy", "vix", "us10y"]:
        assert col in out.columns
    # oil la log-return cua BRENT
    assert out["oil"].iloc[1] == pytest.approx(np.log(raw["BRENT"].iloc[1] / raw["BRENT"].iloc[0]))
    # vix giu level
    assert out["vix"].iloc[5] == pytest.approx(raw["VIX"].iloc[5])


def test_fill_weekend_forward_to_trading_day():
    # GPR co gia tri T7/CN; VN-Index chi co ngay giao dich (T2-T6)
    dates = pd.to_datetime(["2022-01-07", "2022-01-08", "2022-01-09", "2022-01-10"])  # Fri,Sat,Sun,Mon
    gpr = pd.Series([10.0, 20.0, 30.0, 40.0], index=dates)
    trading = pd.to_datetime(["2022-01-07", "2022-01-10"])  # Fri, Mon
    out = ds.fill_weekend(gpr, trading_days=trading)
    # Thu 2 (Mon) phai gom trung binh T7+CN+T2 = mean(20,30,40)=30
    assert out.loc[pd.Timestamp("2022-01-10")] == pytest.approx(30.0)
    assert out.loc[pd.Timestamp("2022-01-07")] == pytest.approx(10.0)
    # chi con ngay giao dich
    assert list(out.index) == list(trading)


def test_fill_weekend_first_window_does_not_average_all_history():
    dates = pd.date_range("2022-01-01", "2022-01-10", freq="D")
    gpr = pd.Series(np.arange(1.0, 11.0), index=dates)
    out = ds.fill_weekend(gpr, trading_days=pd.DatetimeIndex(["2022-01-10"]))
    # First requested session is Monday: only Sat/Sun/Mon, not Jan 1..10.
    assert out.loc[pd.Timestamp("2022-01-10")] == pytest.approx(9.0)


def test_align_frames_inner_join_on_time():
    a = pd.DataFrame({"x": [1, 2, 3]}, index=pd.date_range("2020-01-01", periods=3))
    b = pd.DataFrame({"y": [4, 5]}, index=pd.date_range("2020-01-02", periods=2))
    out = ds.align_frames(a, b, how="inner")
    assert list(out.columns) == ["x", "y"]
    assert len(out) == 2   # chi cac ngay chung
    assert out["x"].iloc[0] == 2
