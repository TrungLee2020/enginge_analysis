"""Test indices/s_gpr.py — cong thuc tong hop chan B (docs/00 §2.5).

Kiem TINH CHAT cua cong thuc:
  - dung nguyen van: esc = w·max(v,0)·specificity, conc = w·max(-v,0);
  - hai chieu KHONG net voi nhau (giu rieng — bat doi xung);
  - role la -> raise (#7: khong gan trong so ngam);
  - chuan hoa nhip dang nguon;
  - global can trade_weights day du, khong co mac dinh;
  - expanding_percentile khong nhin tuong lai (con so phat ra bat bien ve sau).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.indices.s_gpr import (
    expanding_percentile,
    s_gpr_global,
    s_gpr_pair,
    statement_contributions,
)


def make_scores(rows) -> pd.DataFrame:
    cols = ["published_at", "source", "actor_country", "target_country",
            "v", "specificity", "speaker_role"]
    return pd.DataFrame(rows, columns=cols)


TS = pd.Timestamp


def test_contribution_formula_hand_computed():
    df = make_scores([
        # head_of_state (w=1.0), v=+0.92, spec=0.85 -> esc = 0.782
        [TS("2026-07-18 14:07"), "truth_social", "USA", "CHN", 0.92, 0.85,
         "head_of_state"],
        # spokesperson (w=0.4), v=-0.30 -> conc = 0.12 (KHONG nhan specificity)
        [TS("2026-07-18 09:00"), "mofa_cn", "CHN", "USA", -0.30, 0.60,
         "spokesperson"],
    ])
    out = statement_contributions(df)
    assert out["esc"].iloc[0] == pytest.approx(1.0 * 0.92 * 0.85)
    assert out["conc"].iloc[0] == pytest.approx(0.0)
    assert out["esc"].iloc[1] == pytest.approx(0.0)
    assert out["conc"].iloc[1] == pytest.approx(0.4 * 0.30)  # spec KHONG vao conc


def test_two_directions_never_netted():
    """Cung cap cung ngay co ca leo thang lan hoa giai -> CA HAI cot deu duong."""
    df = make_scores([
        [TS("2026-07-18 10:00"), "whitehouse", "USA", "CHN", 0.5, 1.0,
         "head_of_state"],
        [TS("2026-07-18 16:00"), "whitehouse", "USA", "CHN", -0.8, 1.0,
         "head_of_state"],
    ])
    idx = s_gpr_pair(df, window=1)
    row = idx[idx["date"] == TS("2026-07-18")].iloc[0]
    assert row["s_gpr"] > 0 and row["s_conc"] > 0, "net hai chieu la sai spec"


def test_unknown_role_raises_not_silent_weight():
    df = make_scores([[TS("2026-07-18 10:00"), "x", "USA", "CHN", 0.5, 1.0,
                       "deputy_minister"]])
    with pytest.raises(KeyError, match="deputy_minister"):
        statement_contributions(df)
    out = statement_contributions(df, role_weights={"deputy_minister": 0.5})
    assert out["esc"].iloc[0] == pytest.approx(0.25)


def test_source_cadence_normalization():
    """Nguon dang 4 post/ngay khong duoc lan at nguon dang 1 post/ngay."""
    rows = [[TS(f"2026-07-18 {h}:00"), "truth_social", "USA", "CHN", 0.5, 1.0,
             "head_of_state"] for h in (8, 10, 12, 14)]
    rows.append([TS("2026-07-18 09:00"), "mofa_cn", "CHN", "USA", 0.5, 1.0,
                 "spokesperson"])
    out = statement_contributions(make_scores(rows))
    ts_total = out[out["source"] == "truth_social"]["esc"].sum()
    assert ts_total == pytest.approx(0.5), "4 post /4 = trung binh, khong x4"
    raw = statement_contributions(make_scores(rows), normalize_by_source=False)
    assert raw[raw["source"] == "truth_social"]["esc"].sum() == pytest.approx(2.0)


def test_rolling_window_and_zero_fill():
    """Ngay im lang = 0 (flow); rolling 7d cong don dung."""
    df = make_scores([
        [TS("2026-07-01 10:00"), "x", "USA", "CHN", 1.0, 1.0, "head_of_state"],
        [TS("2026-07-05 10:00"), "x", "USA", "CHN", 1.0, 1.0, "head_of_state"],
    ])
    idx = s_gpr_pair(df, window=7).set_index("date")
    assert idx.loc[TS("2026-07-03"), "s_gpr"] == pytest.approx(1.0)   # con trong 7d
    assert idx.loc[TS("2026-07-05"), "s_gpr"] == pytest.approx(2.0)   # 2 phat ngon
    assert TS("2026-07-02") in idx.index, "ngay im lang phai co mat (=gia tri window)"


def test_pair_is_directional():
    df = make_scores([
        [TS("2026-07-18 10:00"), "x", "USA", "CHN", 0.5, 1.0, "head_of_state"],
        [TS("2026-07-18 11:00"), "y", "CHN", "USA", 0.7, 1.0, "spokesperson"],
    ])
    idx = s_gpr_pair(df, window=1)
    assert set(idx["pair"]) == {"USA>CHN", "CHN>USA"}


def test_missing_pair_dropped_but_counted():
    df = make_scores([
        [TS("2026-07-18 10:00"), "x", "USA", None, 0.5, 1.0, "head_of_state"],
        [TS("2026-07-18 11:00"), "x", "USA", "CHN", 0.5, 1.0, "head_of_state"],
    ])
    out = statement_contributions(df)
    assert len(out) == 1
    assert out.attrs["n_dropped_no_pair"] == 1, "phat ngon roi mau phai dem duoc"


def test_global_requires_full_trade_weights():
    df = make_scores([
        [TS("2026-07-18 10:00"), "x", "USA", "CHN", 0.5, 1.0, "head_of_state"],
        [TS("2026-07-18 11:00"), "y", "RUS", "UKR", 0.5, 1.0, "head_of_state"],
    ])
    idx = s_gpr_pair(df, window=1)
    with pytest.raises(KeyError, match="RUS>UKR"):
        s_gpr_global(idx, {"USA>CHN": 0.8})
    out = s_gpr_global(idx, {"USA>CHN": 0.8, "RUS>UKR": 0.2})
    expected = 0.8 * 0.5 + 0.2 * 0.5
    assert out["s_gpr_global"].iloc[0] == pytest.approx(expected)


def test_expanding_percentile_no_lookahead():
    """Percentile tai t khong doi khi noi them du lieu tuong lai."""
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(size=300))
    p_short = expanding_percentile(s.iloc[:200], min_periods=50)
    p_full = expanding_percentile(s, min_periods=50)
    pd.testing.assert_series_equal(p_short.iloc[50:200], p_full.iloc[50:200])
    assert p_full.iloc[:49].isna().all(), "chua du lich su -> NaN, khong doan"
    # max moi vuot TOAN BO lich su truoc do -> 100
    s2 = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert expanding_percentile(s2, min_periods=1).iloc[-1] == pytest.approx(100.0)


def test_expanding_percentile_zero_inflated_quiet_day_is_low():
    """Chuoi kieu JUMP (da so 0, thinh thoang spike): ngay im ang KHONG duoc ra
    percentile cao. Dinh nghia '<=' cho 0 -> ~100 va trigger '>95' no moi ngay —
    dung cai bay zero-inflation ma registry KĐ-E1c ghi nhan."""
    s = pd.Series([0.0] * 99 + [6.0])
    p = expanding_percentile(s, min_periods=10)
    assert (p.iloc[10:-1] == 0.0).all(), "ngay im ang phai la percentile 0"
    assert p.iloc[-1] == pytest.approx(100.0), "spike vuot toan bo lich su"
