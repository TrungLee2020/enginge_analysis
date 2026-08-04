"""Test econometrics/ladder.py — Escalation Ladder V1 rule-based (docs/00 §4.1).

Kiem: config version-hoa load + validate; phan trang thai dung nguong (uu tien
state cao); NaN = khong leo bac; days_in_state dem run; transitions bat dung
chieu; thieu chi bao la loi chet.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.ladder import (
    DEFAULT_LADDER_CONFIG,
    LadderConfig,
    classify_ladder,
    ladder_transitions,
    load_ladder_config,
)


@pytest.fixture
def config() -> LadderConfig:
    return load_ladder_config(DEFAULT_LADDER_CONFIG)


def idx(days: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-07-01", periods=days, freq="D")


def frame(days: int, **cols) -> pd.DataFrame:
    return pd.DataFrame({k: v for k, v in cols.items()}, index=idx(days))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_config_v1_loads_and_is_versioned(config):
    assert config.version == "ladder_v1"
    states = [r.state for r in config.rules]
    assert states == sorted(states, reverse=True), "rule phai xet tu bac cao xuong"
    assert set(config.indicators) == {"quad4_pct", "jump_pct",
                                      "s_gpr_pair_pct", "quad3_pct"}


def test_config_rejects_bad_entries(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: x\nstates:\n  - state: 9\n    conditions:\n"
                   "      - {indicator: a, op: '>', value: 50}\n",
                   encoding="utf-8")
    with pytest.raises(ValueError, match="state=9"):
        load_ladder_config(bad)
    bad.write_text("states: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_ladder_config(bad)
    bad.write_text("version: x\nstates:\n  - state: 2\n    conditions:\n"
                   "      - {indicator: a, op: '!=', value: 50}\n",
                   encoding="utf-8")
    with pytest.raises(ValueError, match="op"):
        load_ladder_config(bad)


# ---------------------------------------------------------------------------
# Phan trang thai
# ---------------------------------------------------------------------------
def test_states_hand_computed(config):
    df = frame(
        4,
        s_gpr_pair_pct=[50, 80, 80, 80],
        quad3_pct=[50, 80, 80, 80],
        quad4_pct=[50, 50, 50, 95],   # ngay cuoi: material conflict vuot p90
        jump_pct=[10, 10, 10, 10],
    )
    out = classify_ladder(df, config)
    assert out["state"].tolist() == [0, 2, 2, 4]
    assert (out["config_version"] == "ladder_v1").all()


def test_higher_state_wins_when_both_fire(config):
    """S4 (any) va S2 (all) cung thoa -> lay S4, khong lay rule xet sau."""
    df = frame(1, s_gpr_pair_pct=[90], quad3_pct=[90], quad4_pct=[50],
               jump_pct=[99])
    out = classify_ladder(df, config)
    assert out["state"].iloc[0] == 4


def test_s4_any_fires_on_jump_alone_without_gdelt(config):
    """Chua co GDELT (quad NaN): S4 van bat qua JUMP chan A (docs/15 §3 trigger tam);
    S2 thi KHONG bat duoc — han che ghi trong config, kiem de khong ai ngo nhan."""
    df = frame(2,
               s_gpr_pair_pct=[99, 99],
               quad3_pct=[np.nan, np.nan], quad4_pct=[np.nan, np.nan],
               jump_pct=[50, 99])
    out = classify_ladder(df, config)
    assert out["state"].tolist() == [0, 4], \
        "NaN khong duoc thoa dieu kien nao — ke ca chieu <= (S2 phai khong bat)"


def test_days_in_state_counts_runs(config):
    df = frame(5,
               s_gpr_pair_pct=[80] * 5, quad3_pct=[80] * 5,
               quad4_pct=[50, 50, 95, 50, 50], jump_pct=[0] * 5)
    out = classify_ladder(df, config)
    assert out["state"].tolist() == [2, 2, 4, 2, 2]
    assert out["days_in_state"].tolist() == [1, 2, 1, 1, 2]


def test_missing_indicator_is_fatal(config):
    df = frame(2, s_gpr_pair_pct=[80, 80])
    with pytest.raises(KeyError, match="quad4_pct|jump_pct|quad3_pct"):
        classify_ladder(df, config)


# ---------------------------------------------------------------------------
# Transitions — trigger tang 4
# ---------------------------------------------------------------------------
def test_transitions_direction(config):
    states = pd.Series([0, 2, 2, 4, 1], index=idx(5))
    tr = ladder_transitions(states)
    assert tr["from_state"].tolist() == [0, 2, 4]
    assert tr["to_state"].tolist() == [2, 4, 1]
    assert tr["direction"].tolist() == ["up", "up", "down"]
    assert tr["date"].iloc[1] == pd.Timestamp("2026-07-04")


def test_no_transition_on_first_day():
    states = pd.Series([3, 3], index=idx(2))
    assert ladder_transitions(states).empty
