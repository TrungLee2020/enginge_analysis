"""Test cu soc chinh sach tien te tu cua so cong bo FOMC (`policy_shock.py`).

Khong goi mang. Kiem cac bat bien de phep do sai ma van "chay":
  - ngay su kien lay theo gio NEW YORK, khong phai UTC tho;
  - ngay khong hop = 0 ("khong co cong bo") chu khong phai NaN im lang;
  - ngay hop ma thieu gia -> BO, khong noi suy;
  - gop thang tra ca `sum` lan `absmax`, khong ep mot cach doc;
  - `contamination_ratio` phai bat duoc truong hop proxy vo dung (ty le ~1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.policy_shock import (
    contamination_ratio,
    event_days,
    policy_surprise,
    to_monthly,
)


def _yields(n: int = 60, start: str = "2026-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(np.linspace(4.0, 4.5, n), index=idx, name="DGS2")


def test_event_day_uses_new_york_not_raw_utc():
    """Cong bo 14:00 ET = 18:00 UTC (he) / 19:00 UTC (dong). Lay ngay theo mui
    New York de khong phu thuoc may man cua offset."""
    ts = [pd.Timestamp("2026-07-29T18:00", tz="UTC"),
          pd.Timestamp("2026-01-28T19:00", tz="UTC")]
    got = event_days(ts)
    assert list(got) == [pd.Timestamp("2026-01-28"), pd.Timestamp("2026-07-29")]


def test_late_utc_timestamp_still_maps_to_the_us_day():
    """Moc 23:30 UTC van la NGAY HOM TRUOC o New York — lay ngay UTC tho se
    lech mot phien."""
    got = event_days([pd.Timestamp("2026-07-29T23:30", tz="UTC")])
    assert list(got) == [pd.Timestamp("2026-07-29")]


def test_non_event_days_inside_coverage_are_zero_not_nan():
    """TRONG pham vi da thu thap: 0 = 'khong co cong bo nao', khac han 'thieu
    du lieu'. Tron hai cai lam hoi quy am tham bo hang.
    (Ngoai pham vi thi NaN — xem test ke ben.)"""
    y = _yields()
    ev = pd.DatetimeIndex([y.index[10], y.index[30]])
    s = policy_surprise(y, ev)
    inside = s.loc[y.index[10]: y.index[30]]
    assert inside.notna().all()
    assert inside.loc[y.index[10]] != 0
    assert (inside.drop([y.index[10], y.index[30]]) == 0).all()


def test_zero_fill_stops_at_the_edges_of_real_coverage():
    """0 chi hop le TRONG pham vi da thu thap su kien.

    Neu chua lay duoc ngay cong bo cua giai doan dau mau ma van dien 0 thi chuoi
    bao "khong co cong bo nao" trong khi thuc te co 8 cuoc hop moi nam — bien
    kiem soat mang gia tri sai lam lech he so cua bien CHINH ma khong dau hieu.
    """
    y = _yields(n=40)
    ev = pd.DatetimeIndex([y.index[20], y.index[25]])
    s = policy_surprise(y, ev)
    assert s.loc[: y.index[19]].isna().all(), "truoc su kien dau phai la NaN"
    assert s.loc[y.index[26]:].isna().all(), "sau su kien cuoi phai la NaN"
    assert (s.loc[y.index[20]: y.index[25]].notna()).all()
    assert (s.loc[y.index[21]: y.index[24]] == 0).all()   # trong pham vi: 0 that


def test_no_matching_event_raises_instead_of_all_zero_series():
    y = _yields()
    with pytest.raises(ValueError, match="hoan toan bia|Khong ngay su kien"):
        policy_surprise(y, pd.DatetimeIndex(["2030-01-01"]))


def test_fill_none_keeps_only_event_days():
    y = _yields()
    ev = pd.DatetimeIndex([y.index[5], y.index[10]])
    s = policy_surprise(y, ev, fill_non_event=None)
    assert list(s.index) == list(ev)


def test_event_day_without_price_is_dropped_not_interpolated():
    """Ngay nghi le khong co gia -> bo. Noi suy la bia mot cu soc khong ton tai."""
    y = _yields()
    ev = pd.DatetimeIndex([y.index[10], pd.Timestamp("2030-01-01")])
    s = policy_surprise(y, ev, fill_non_event=None)
    assert list(s.index) == [y.index[10]]


def test_surprise_is_the_daily_change():
    y = pd.Series([4.00, 4.00, 4.25, 4.25],
                  index=pd.bdate_range("2026-01-05", periods=4))
    s = policy_surprise(y, pd.DatetimeIndex([y.index[2]]), fill_non_event=None)
    assert s.iloc[0] == pytest.approx(0.25)


def test_monthly_reports_both_aggregations():
    """`sum` va `absmax` tra loi hai cau khac nhau — module khong chon ho."""
    idx = pd.to_datetime(["2026-01-05", "2026-01-20", "2026-02-10"])
    s = pd.Series([0.10, -0.30, 0.05], index=idx)
    m = to_monthly(s)
    jan = m.loc[pd.Timestamp("2026-01-01")]
    assert jan["mp_surprise_sum"] == pytest.approx(-0.20)
    assert jan["mp_surprise_absmax"] == pytest.approx(-0.30)   # giu DAU
    assert jan["mp_n_events"] == 2
    assert m.loc[pd.Timestamp("2026-01-01"), "mp_surprise"] == pytest.approx(-0.20)
    assert to_monthly(s, how="absmax").loc[
        pd.Timestamp("2026-01-01"), "mp_surprise"] == pytest.approx(-0.30)


def test_monthly_grid_is_month_start_not_forward_filled():
    """#10: grid dau thang that, khong no ra ngay."""
    s = pd.Series([0.1], index=pd.to_datetime(["2026-03-18"]))
    m = to_monthly(s)
    assert list(m.index) == [pd.Timestamp("2026-03-01")]


def test_unknown_aggregation_raises():
    with pytest.raises(ValueError, match="how phai la"):
        to_monthly(pd.Series([0.1], index=pd.to_datetime(["2026-01-05"])), how="mean")


def test_contamination_ratio_detects_a_useless_proxy():
    """Neu ngay cong bo khong khac ngay thuong (ty le ~1) thi phep do chi la
    nhieu thi truong — phai nhin thay dieu do, khong dung mu."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2020-01-01", periods=500)
    noise = pd.Series(rng.normal(scale=0.03, size=500), index=idx)
    ev = idx[::10]
    flat = contamination_ratio(noise, ev)
    assert 0.7 < flat["abs_ratio"] < 1.4          # khong tach duoc khoi nhieu

    loud = noise.copy()
    loud.loc[ev] += rng.normal(scale=0.15, size=len(ev))
    assert contamination_ratio(loud, ev)["abs_ratio"] > 2.0


def test_contamination_ratio_needs_overlapping_dates():
    s = pd.Series([0.1], index=pd.to_datetime(["2026-01-05"]))
    with pytest.raises(ValueError, match="Khong du ngay"):
        contamination_ratio(s, pd.DatetimeIndex(["2030-01-01"]))
