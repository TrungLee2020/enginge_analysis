"""ingest/gdelt_events.py — slot cua collector -> ty trong QuadClass theo ngay (offline, khong DB)."""
import json

import pandas as pd
import pytest

from gpr_engine.ingest import gdelt_events as ge


def _write(root, day, n_slots, n=100, q3=20, q4=10, watch_n=10, wq3=5, wq4=4):
    d = root / day[:7]
    d.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(day, tz="UTC")
    rows = [{"slot": (start + pd.Timedelta(minutes=15 * i)).isoformat(), "n": n,
             "q": [n - q3 - q4, 0, q3, q4], "m": [0, 0, 0, 0],
             "watch_n": watch_n, "watch_q": [watch_n - wq3 - wq4, 0, wq3, wq4]} for i in range(n_slots)]
    (d / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_daily_shares_and_incomplete_days_dropped(tmp_path):
    _write(tmp_path, "2026-10-24", 96)
    _write(tmp_path, "2026-10-25", 40)                     # collector nghi nua ngay -> bo
    wide = ge.daily(ge.load_slots(str(tmp_path)))
    assert list(wide["date"].dt.strftime("%Y-%m-%d")) == ["2026-10-24"]
    row = wide.iloc[0]
    assert row["GDELT_EVENTS_N"] == 9600
    assert row["GDELT_QUAD3_SHARE"] == pytest.approx(0.2)
    assert row["GDELT_QUAD4_SHARE"] == pytest.approx(0.1)
    assert row["GDELT_WATCH_QUAD4_SHARE"] == pytest.approx(0.4)


def test_long_has_available_at_after_the_day_and_drops_undefined_shares(tmp_path):
    _write(tmp_path, "2026-10-24", 96, watch_n=0, wq3=0, wq4=0)
    long = ge.to_long(ge.daily(ge.load_slots(str(tmp_path))), "sv", "v1")
    assert set(long["series_id"]) == set(ge.SERIES) - {"GDELT_WATCH_QUAD3_SHARE", "GDELT_WATCH_QUAD4_SHARE"}
    assert (long["available_at"] == pd.Timestamp("2026-10-25 01:00", tz="UTC")).all()
    assert set(long.columns) >= {"series_id", "date", "value", "freq", "source", "available_at",
                                 "source_version", "data_version"}
    assert (long["freq"] == "daily").all()


def test_duplicate_slot_keeps_the_last_reading(tmp_path):
    _write(tmp_path, "2026-10-24", 96)
    extra = tmp_path / "2026-10" / "2026-10-24.jsonl"
    extra.write_text(extra.read_text() + json.dumps(
        {"slot": "2026-10-24T00:00:00+00:00", "n": 100, "q": [0, 0, 100, 0], "watch_q": [0, 0, 0, 0]}) + "\n")
    slots = ge.load_slots(str(tmp_path))
    assert len(slots) == 96
    assert slots.iloc[0]["q3"] == 100


def test_missing_directory_raises_with_the_collector_command(tmp_path):
    with pytest.raises(FileNotFoundError, match="gdelt-backfill"):
        ge.load_slots(str(tmp_path / "none"))
