"""Test AI-GPR "Country Decompositions" (docs/16 §1 v1.2/v1.3) — 3 file
KHÁC chỉ số tổng hợp daily/monthly: theo loại sự kiện, nước×loại sự kiện,
cặp nước có hướng. File TẢI TAY, không có dữ liệu thật trong repo nên test
dùng fixture nhỏ khớp schema thật đã xác minh 2026-08-05.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gpr_engine.econometrics.data_files import (
    AI_GPR_EVENT_TYPES,
    ai_gpr_vintage,
    load_ai_gpr_bilateral_monthly,
    load_ai_gpr_country_eventtype_monthly,
    load_ai_gpr_eventtype_monthly,
    select_bilateral_pair,
    select_country_eventtype,
)


def _dates(n=6):
    return pd.date_range("2020-01-01", periods=n, freq="MS")


@pytest.fixture
def eventtype_file(tmp_path):
    p = tmp_path / "ai_gpr_eventtype_monthly.csv"
    idx = _dates()
    df = pd.DataFrame({"Date": idx, "GPR_AI": range(len(idx)),
                       **{et: 1.0 for et in AI_GPR_EVENT_TYPES}})
    df.to_csv(p, index=False)
    return str(p)


@pytest.fixture
def country_eventtype_file(tmp_path):
    p = tmp_path / "ai_gpr_country_eventtype_monthly.csv"
    idx = _dates()
    cols = {"Date": idx, "GPR_AI": range(len(idx))}
    for country in ("Vietnam", "USA"):
        for et in AI_GPR_EVENT_TYPES:
            cols[f"{country}_{et}"] = 2.0
    pd.DataFrame(cols).to_csv(p, index=False)
    return str(p)


@pytest.fixture
def bilateral_file(tmp_path):
    p = tmp_path / "ai_gpr_bilateral_monthly.csv"
    idx = _dates()
    df = pd.DataFrame({"Date": idx, "GPR_AI": range(len(idx)),
                       "USA|Vietnam": 3.0, "Vietnam|USA": 4.0})
    df.to_csv(p, index=False)
    return str(p)


# ---------------------------------------------------------------------------
# eventtype (global, 8 loại sự kiện)
# ---------------------------------------------------------------------------
def test_eventtype_loads_all_eight_categories(eventtype_file):
    df = load_ai_gpr_eventtype_monthly(eventtype_file)
    assert df.index.name == "month"
    assert set(AI_GPR_EVENT_TYPES) <= set(df.columns)
    assert "AIGPR" in df.columns
    assert df.attrs["vintage"] == ai_gpr_vintage(eventtype_file)


def test_eventtype_missing_category_raises(tmp_path):
    p = tmp_path / "partial.csv"
    pd.DataFrame({"Date": _dates(), "GPR_AI": range(6),
                 "military_conflict": 1.0}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="thiếu cột"):
        load_ai_gpr_eventtype_monthly(str(p))


# ---------------------------------------------------------------------------
# country × eventtype
# ---------------------------------------------------------------------------
def test_select_country_eventtype_extracts_one_country(country_eventtype_file):
    df = load_ai_gpr_country_eventtype_monthly(country_eventtype_file)
    vn = select_country_eventtype(df, "Vietnam")
    assert list(vn.columns) == list(AI_GPR_EVENT_TYPES)
    assert (vn == 2.0).all().all()
    # khong lo ra cot cua nuoc khac
    assert "USA_military_conflict" not in vn.columns


def test_select_country_eventtype_unknown_country_raises(country_eventtype_file):
    df = load_ai_gpr_country_eventtype_monthly(country_eventtype_file)
    with pytest.raises(KeyError, match="Không tìm thấy nước"):
        select_country_eventtype(df, "Atlantis")


# ---------------------------------------------------------------------------
# bilateral (có hướng)
# ---------------------------------------------------------------------------
def test_select_bilateral_pair_is_directional(bilateral_file):
    df = load_ai_gpr_bilateral_monthly(bilateral_file)
    usa_vn = select_bilateral_pair(df, "USA", "Vietnam")
    vn_usa = select_bilateral_pair(df, "Vietnam", "USA")
    assert (usa_vn == 3.0).all()
    assert (vn_usa == 4.0).all()  # KHAC gia tri — co huong that


def test_select_bilateral_pair_unknown_pair_raises(bilateral_file):
    df = load_ai_gpr_bilateral_monthly(bilateral_file)
    with pytest.raises(KeyError, match="Không tìm thấy cặp"):
        select_bilateral_pair(df, "Atlantis", "Nowhere")


def test_bilateral_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_ai_gpr_bilateral_monthly(str(tmp_path / "nope.csv"))
