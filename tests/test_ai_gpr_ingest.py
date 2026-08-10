"""Test ingest.ai_gpr — load/to_long offline (pure), upsert mock (KHONG Postgres that).

Chan A production: ingest 12 chuoi TONG HOP (headline/threat/act/oil-tong/
oil-8-vung/AER/NONOIL) vao ext_series, cung schema voi ingest/gpr_daily.py.
KHONG co Postgres song trong sandbox (cung gioi han voi ingest/gpr_daily.py,
gpr_monthly.py, market_data.py — CLAUDE.md) nen phan upsert() mock
sqlalchemy.create_engine, cung pattern voi tests/test_kafka_io.py mock
confluent_kafka.Producer.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from gpr_engine.ingest.ai_gpr import (
    AI_GPR_COLUMNS,
    available_at,
    ingest_one,
    load_dataframe,
    to_long,
    upsert,
)


def _write(path, n=5, freq="D"):
    idx = pd.date_range("2020-01-01", periods=n, freq=freq)
    pd.DataFrame({"Date": idx, **{c: range(n) for c in AI_GPR_COLUMNS}}).to_csv(path, index=False)


def test_load_dataframe_renames_and_sorts(tmp_path):
    p = tmp_path / "daily.csv"
    _write(p)
    df = load_dataframe(str(p))
    assert list(df.columns) == ["date", *AI_GPR_COLUMNS.values()]
    assert df["date"].is_monotonic_increasing


def test_load_dataframe_missing_file_raises_with_instructions(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        load_dataframe(str(tmp_path / "nope.csv"))
    assert "TAI TAY" in str(e.value)
    assert "ai_gpr.html" in str(e.value)


def test_load_dataframe_missing_column_raises_not_silently_dropped(tmp_path):
    p = tmp_path / "partial.csv"
    pd.DataFrame({"Date": ["2020-01-01"], "GPR_AI": [1.0]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="thieu cot"):
        load_dataframe(str(p))


def test_load_dataframe_missing_date_column_raises(tmp_path):
    p = tmp_path / "nodate.csv"
    pd.DataFrame({c: [1] for c in AI_GPR_COLUMNS}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="cot ngay"):
        load_dataframe(str(p))


def test_available_at_daily_is_date_plus_one_day():
    dates = pd.Series(pd.to_datetime(["2020-01-01"]))
    ts = available_at(dates, "daily")
    assert ts.iloc[0] == pd.Timestamp("2020-01-02 12:00", tz="UTC")


def test_available_at_monthly_is_next_month_begin_plus_lag():
    """Gia tri thang M chi biet sau khi thang M ket thuc — dung `date` (dau
    thang M) lam proxy la look-ahead (docs/08 §4.7), giong het gpr_monthly.py."""
    dates = pd.Series(pd.to_datetime(["2020-01-01"]))
    ts = available_at(dates, "monthly")
    assert ts.iloc[0] == pd.Timestamp("2020-02-06 12:00", tz="UTC")


def test_available_at_unknown_freq_raises():
    with pytest.raises(ValueError, match="freq"):
        available_at(pd.Series(pd.to_datetime(["2020-01-01"])), "weekly")


def test_to_long_covers_all_series_with_correct_metadata(tmp_path):
    p = tmp_path / "daily.csv"
    _write(p, n=3)
    df = load_dataframe(str(p))
    long = to_long(df, "daily", "src_v1", "v1")
    assert set(long["series_id"]) == set(AI_GPR_COLUMNS.values())
    assert (long["freq"] == "daily").all()
    assert (long["source"] == "ai_gpr_daily_file").all()
    assert (long["source_version"] == "src_v1").all()
    assert (long["data_version"] == "v1").all()
    assert len(long) == 3 * len(AI_GPR_COLUMNS)


def test_daily_and_monthly_series_ids_are_disjoint(tmp_path):
    """Bug that 2026-08-09: hai tan suat dung CHUNG series_id.

    `ext_series` PK la (series_id, date, data_version) — KHONG co `freq`. Moi
    ngay dau thang co mat o ca file daily lan monthly, nen dung chung ten la ghi
    de lan nhau: 11.186 hang mang gia tri THANG trong chuoi danh dau daily. Am
    tham vi gia tri thang ~ trung binh cua thang, cung thang do voi gia tri ngay
    (AIGPR_OIL 2026-03-01: 1844.10 thang vs 610.53 ngay).
    """
    from gpr_engine.ingest.ai_gpr import MONTHLY_SUFFIX, series_ids

    p = tmp_path / "x.csv"
    _write(p, n=3)
    df = load_dataframe(str(p))
    d = set(to_long(df, "daily", "sv", "v1")["series_id"])
    m = set(to_long(df, "monthly", "sv", "v1")["series_id"])
    assert d & m == set(), f"series_id trung giua hai tan suat: {sorted(d & m)}"
    assert m == {f"{s}{MONTHLY_SUFFIX}" for s in d}
    assert set(series_ids("daily")) == d and set(series_ids("monthly")) == m


def test_series_id_for_rejects_unknown_freq():
    from gpr_engine.ingest.ai_gpr import series_id_for

    with pytest.raises(ValueError, match="freq phai la"):
        series_id_for("GPR_AI", "weekly")


def test_upsert_sends_conflict_safe_sql_via_mocked_engine():
    long = pd.DataFrame([{
        "series_id": "AIGPR", "date": pd.Timestamp("2020-01-01").date(), "value": 1.0,
        "freq": "daily", "source": "ai_gpr_daily_file",
        "available_at": pd.Timestamp("2020-01-02T12:00", tz="UTC"),
        "source_version": "v1", "data_version": "v1",
    }])
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    with patch("gpr_engine.ingest.ai_gpr.create_engine", return_value=mock_engine):
        n = upsert(long, "postgresql://fake")
    assert n == 1
    mock_conn.execute.assert_called_once()
    sql_arg = mock_conn.execute.call_args[0][0]
    assert "ON CONFLICT (series_id, date, data_version)" in str(sql_arg)


def test_ingest_one_end_to_end_with_mocked_db(tmp_path):
    p = tmp_path / "daily.csv"
    _write(p, n=2)
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    with patch("gpr_engine.ingest.ai_gpr.create_engine", return_value=mock_engine):
        n = ingest_one(str(p), "daily", "postgresql://fake", "src_v1", "v1")
    assert n == 2 * len(AI_GPR_COLUMNS)
    mock_conn.execute.assert_called_once()
