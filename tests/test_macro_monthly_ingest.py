"""Test ingest.macro_monthly — nhom THANG (ip/cpi/infl_exp/EPU/freight) vao ext_series.

Khong goi mang: `load_fred_monthly` duoc thay bang frame gia. Cai dang test la
cac BAT BIEN de mat du lieu hoac sinh look-ahead:
  - ma FRED phai TRUNG KHIT duong research (`data_files`) — hai duong lech ma
    khong ai thay la kieu bug ton kem nhat o repo nay;
  - `available_at` phai tinh tu DAU THANG KE TIEP, khong phai tu `date`;
  - series_id khong duoc trung voi nhom daily (PK khong chua `freq`);
  - series chua khai do tre publish -> raise, khong mac dinh 0.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gpr_engine.ingest.macro_monthly import (
    FRED_MONTHLY,
    PUBLISH_LAG_DAYS,
    available_at,
    to_long,
)


def _raw(series_id: str = "INDPRO", n: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="MS")
    return pd.DataFrame({"series_id": series_id, "date": idx,
                         "value": [100.0 + i for i in range(n)]})


# ---------------------------------------------------------------------------
# Khop duong research
# ---------------------------------------------------------------------------
def test_macro_monthly_codes_match_research_path():
    """Ma FRED o ingest phai bang ma o `data_files`.

    Khong import lai duoc (data_files import TU ingest — nguoc lai la vong tron)
    nen su trung khop chi con test nay giu. Lech ma khong ai thay = duong DB va
    duong file tinh tren hai chuoi khac nhau.
    """
    from gpr_engine.econometrics.data_files import (
        FRED_BENCHMARK,
        FRED_FREIGHT,
        FRED_REAL_MACRO,
    )

    expected = {
        "INDPRO": FRED_REAL_MACRO["ip"],
        "CPI": FRED_REAL_MACRO["cpi"],
        "INFL_EXP": FRED_REAL_MACRO["infl_exp"],
        "EPU_US": FRED_BENCHMARK["epu_us"],
        "EPU_GLOBAL": FRED_BENCHMARK["epu_global"],
        "FREIGHT_PPI": FRED_FREIGHT,
    }
    assert FRED_MONTHLY == expected


def test_internal_names_match_transform_output_columns():
    """Ten noi bo cua duong DB phai trung cot ma `data_files.transform_*` sinh ra,
    neu khong thi hai duong ra hai bo ten cot cho cung mot bien."""
    from gpr_engine.econometrics.dataset import MONTHLY_MACRO_SERIES

    assert set(MONTHLY_MACRO_SERIES) == set(FRED_MONTHLY)
    assert set(MONTHLY_MACRO_SERIES.values()) == {
        "ip", "cpi", "infl_exp", "epu_us", "epu_global", "freight"}


def test_series_ids_do_not_collide_with_daily_sources():
    """PK khong chua `freq` — trung ten voi nhom daily la ghi de lan nhau
    (bug AI-GPR 2026-08-09)."""
    from gpr_engine.ingest.market_data import FRED_MAP, VN_SERIES

    daily = set(FRED_MAP) | set(VN_SERIES) | {"GPRD", "GPRD_ACT", "GPRD_THREAT"}
    assert set(FRED_MONTHLY) & daily == set()


# ---------------------------------------------------------------------------
# available_at — chong look-ahead
# ---------------------------------------------------------------------------
def test_available_at_is_next_month_begin_plus_lag():
    """Gia tri thang M tong hop CA THANG -> som nhat la dau thang M+1 + do tre."""
    got = available_at(pd.Series(pd.to_datetime(["2026-03-01"])), "INDPRO")
    expected = pd.Timestamp("2026-04-01", tz="UTC") + pd.Timedelta(days=18, hours=12)
    assert got.iloc[0] == expected


def test_available_at_never_equals_observation_date():
    """Dung chinh `date` lam moc = nhin truoc gan mot thang (docs/08 §4.7)."""
    dates = pd.Series(pd.to_datetime(["2026-01-01", "2026-02-01"]))
    for sid in FRED_MONTHLY:
        got = available_at(dates, sid)
        assert (got.dt.tz_localize(None) > dates).all()


def test_slower_published_series_has_later_availability():
    """IP/CPI ra giua thang ke tiep, EPU ra dau thang -> IP phai MUON hon."""
    d = pd.Series(pd.to_datetime(["2026-03-01"]))
    assert available_at(d, "INDPRO").iloc[0] > available_at(d, "EPU_US").iloc[0]
    assert PUBLISH_LAG_DAYS["FREIGHT_PPI"] >= PUBLISH_LAG_DAYS["CPI"]


def test_unknown_series_lag_raises_instead_of_defaulting_to_zero():
    """Mac dinh 0 la look-ahead im lang — phai bat khai bao."""
    with pytest.raises(ValueError, match="Chua khai do tre publish"):
        available_at(pd.Series(pd.to_datetime(["2026-01-01"])), "SOMETHING_NEW")


# ---------------------------------------------------------------------------
# to_long
# ---------------------------------------------------------------------------
def test_to_long_sets_metadata_and_keeps_raw_values():
    """Luu MUC THO — transform la viec cua dataset/data_files, khong fork."""
    long = to_long(_raw(), "sv1", "v1")
    assert (long["freq"] == "monthly").all()
    assert (long["source"] == "fred_monthly").all()
    assert (long["source_version"] == "sv1").all()
    assert long["value"].tolist() == [100.0, 101.0, 102.0]


def test_to_long_applies_per_series_lag_not_a_single_lag():
    """Moi series mot do tre — gop chung mot con so la sai cho ca hai dau."""
    raw = pd.concat([_raw("INDPRO", 2), _raw("EPU_US", 2)], ignore_index=True)
    long = to_long(raw, "sv1", "v1")
    by = long.groupby("series_id")["available_at"].min()
    assert by["INDPRO"] > by["EPU_US"]


def test_to_long_drops_missing_values_only():
    raw = _raw(n=3)
    raw.loc[1, "value"] = None
    long = to_long(raw, "sv1", "v1")
    assert len(long) == 2
