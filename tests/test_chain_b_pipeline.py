"""Test TICH HOP chan B: phat ngon -> LLM cham -> S-GPR -> ladder -> payload.

Tai hien vi du xuyen suot docs/15 §2 (tin Trump ap thue 14:07) bang fake LLM —
kiem rang BON TANG ghep duoc voi nhau va moi con so trong payload cuoi den tu
CONG THUC (LLM chi cham v/channel/commitment/specificity, dung docs/15 §0).
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.ladder import (
    DEFAULT_LADDER_CONFIG,
    classify_ladder,
    ladder_transitions,
    load_ladder_config,
)
from gpr_engine.indices.s_gpr import expanding_percentile, s_gpr_pair
from gpr_engine.scoring.statement_scorer import (
    ScorerConfig,
    Statement,
    score_statements,
)

CONFIG = ScorerConfig(model_version="fake-for-test",
                      training_cutoff=dt.date(2023, 10, 1))

# Fake LLM: tra diem theo noi dung — dong vai scorer, khong sinh so nao khac.
CANNED = {
    "tariff": {"v": 0.92, "actor_country": "USA", "target_country": "CHN",
               "channel": "trade", "commitment": "announced_action",
               "specificity": 0.85, "rationale": "enacted tariffs with date"},
    "dialogue": {"v": -0.30, "actor_country": "CHN", "target_country": "USA",
                 "channel": "diplomacy", "commitment": "rhetoric",
                 "specificity": 0.40, "rationale": "calls for dialogue"},
}


def fake_llm(messages, temperature):
    text = messages[-1]["content"].lower()
    for key, payload in CANNED.items():
        if key in text:
            return json.dumps(payload)
    return json.dumps({"v": 0.0, "actor_country": None, "target_country": None,
                       "channel": None, "commitment": "rhetoric",
                       "specificity": 0.0, "rationale": "neutral"})


def fake_encoder(text: str) -> float:
    return 0.97 if ("tariff" in text.lower() or "dialogue" in text.lower()) else 0.2


def test_statement_to_ladder_end_to_end():
    stmts = [
        Statement(source="truth_social",
                  published_at=pd.Timestamp("2026-07-18 14:07"),
                  speaker="Donald Trump", speaker_role="head_of_state",
                  speaker_country="USA",
                  text="Additional tariffs on Chinese goods, effective August 1."),
        Statement(source="mofa_cn",
                  published_at=pd.Timestamp("2026-07-18 09:00"),
                  speaker="MOFA spokesperson", speaker_role="spokesperson",
                  speaker_country="CHN",
                  text="China calls for constructive dialogue with the US."),
        Statement(source="whitehouse",
                  published_at=pd.Timestamp("2026-07-18 11:00"),
                  speaker="Press Office", speaker_role="spokesperson",
                  speaker_country="USA",
                  text="Statement on National Park Week."),
    ]

    # [tang 2] encoder loc -> LLM cham (JSON strict)
    scored, dropped = score_statements(stmts, fake_llm, CONFIG,
                                       encoder=fake_encoder)
    assert len(scored) == 2
    assert dropped["reason"].tolist() == ["encoder_filtered"]

    # [tang 2] cong thuc: S-GPR pair 7d — so tay: 1.0*0.92*0.85 (Trump moi post
    # duy nhat cua truth_social hom do); MOFA hoa giai vao s_conc chieu nguoc.
    idx = s_gpr_pair(scored, window=7)
    us_cn = idx[idx["pair"] == "USA>CHN"].set_index("date")
    assert us_cn.loc[pd.Timestamp("2026-07-18"), "s_gpr"] == pytest.approx(0.782)
    cn_us = idx[idx["pair"] == "CHN>USA"].set_index("date")
    assert cn_us.loc[pd.Timestamp("2026-07-18"), "s_conc"] == pytest.approx(0.4 * 0.3)
    assert cn_us.loc[pd.Timestamp("2026-07-18"), "s_gpr"] == pytest.approx(0.0)

    # [tang 2->4] percentile lich su (khong lookahead) + JUMP chan A gia lap
    # -> ladder: ngay cuoi jump vuot q95 -> S4, sinh trigger "chuyen bac".
    n = 120
    rng = np.random.default_rng(7)
    hist = pd.Series(rng.uniform(0, 0.1, n),
                     index=pd.date_range("2026-03-21", periods=n, freq="D"))
    hist.iloc[-1] = 0.782                       # ngay co phat ngon Trump
    s_pct = expanding_percentile(hist, min_periods=30)

    jump = pd.Series(0.0, index=hist.index)
    jump.iloc[-1] = 6.03                        # JUMP chan A (Hormuz-scale)
    j_pct = expanding_percentile(jump, min_periods=30)

    indicators = pd.DataFrame({
        "s_gpr_pair_pct": s_pct, "jump_pct": j_pct,
        "quad3_pct": np.nan, "quad4_pct": np.nan,   # GDELT chua ingest
    })
    ladder = classify_ladder(indicators.dropna(subset=["jump_pct"]),
                             load_ladder_config(DEFAULT_LADDER_CONFIG))
    assert ladder["state"].iloc[-1] == 4
    tr = ladder_transitions(ladder["state"])
    assert tr.iloc[-1]["direction"] == "up"

    # Payload card: MOI con so truy ve duoc mot ham + input (guard P1 ap sau).
    payload = {
        "v": float(scored.iloc[0]["v"]),
        "commitment": scored.iloc[0]["commitment"],
        "channel": scored.iloc[0]["channel"],
        "s_gpr_7d": float(us_cn.loc[pd.Timestamp("2026-07-18"), "s_gpr"]),
        "s_gpr_pctile": float(s_pct.iloc[-1]),
        "ladder_state": int(ladder["state"].iloc[-1]),
        "model_version": scored.iloc[0]["model_version"],
        "rubric_version": scored.iloc[0]["rubric_version"],
    }
    assert payload["s_gpr_pctile"] > 99.0                   # max lich su (strict <)
    assert payload["ladder_state"] == 4
    assert payload["model_version"] == "fake-for-test"
