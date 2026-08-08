"""Test scoring/statement_scorer.py — tang 2 do luong (chan B).

Khong goi mang: LLM la fake client tiem vao. Test giu cac CONTRACT:
  - JSON strict: sai key/mien/kieu -> tu choi, khong sua ho (LLM cam sinh so
    ngoai schema, docs/15 §0);
  - encoder loc duoi 0.6 -> khong goi LLM (pipeline 2 tang ECB, docs/11 §7);
  - versioning day du tren moi hang diem + training_cutoff bat buoc (docs/14 §3.1.4);
  - prompt chua quy tac contamination (docs/14 §3.1.1) va bang neo rubric;
  - cache theo content_hash: cung van ban khong cham hai lan, doi model_version
    thi cham lai;
  - published_at nguon daily phai co gio phut (CLAUDE.md #5).
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from gpr_engine.scoring.statement_scorer import (
    DEFAULT_TEMPERATURE,
    PROMPT_VERSION,
    RUBRIC_VERSION,
    SCORE_COLUMNS,
    SYSTEM_PROMPT,
    ScoreParseError,
    ScorerConfig,
    Statement,
    build_messages,
    content_hash,
    parse_score,
    score_statement,
    score_statements,
    to_transmission_channel,
)

CONFIG = ScorerConfig(model_version="gpt-4o-mini-2024-07-18",
                      training_cutoff=dt.date(2023, 10, 1))

GOOD = {"v": 0.92, "actor_country": "USA", "target_country": "CHN",
        "channel": "trade", "commitment": "announced_action",
        "specificity": 0.85, "rationale": "tariff announcement with date"}


def stmt(text="Additional tariffs on Chinese goods, effective August 1.",
         **kw) -> Statement:
    base = dict(source="truth_social",
                published_at=pd.Timestamp("2026-07-18 14:07"),
                speaker="Donald Trump", speaker_role="head_of_state",
                speaker_country="USA", text=text)
    base.update(kw)
    return Statement(**base)


def fake_llm(payload=GOOD):
    """Client tra JSON co dinh + dem so lan goi."""
    calls = []

    def _call(messages, temperature):
        calls.append((messages, temperature))
        return json.dumps(payload)

    _call.calls = calls
    return _call


# ---------------------------------------------------------------------------
# JSON strict contract
# ---------------------------------------------------------------------------
def test_parse_valid():
    out = parse_score(json.dumps(GOOD))
    assert out["v"] == pytest.approx(0.92)
    assert out["actor_country"] == "USA" and out["channel"] == "trade"


@pytest.mark.parametrize("mutation, match", [
    ({"v": 1.5}, "ngoai"),                       # ngoai mien rubric
    ({"v": "high"}, "khong phai so"),
    ({"v": True}, "khong phai so"),              # bool lot qua isinstance int
    ({"specificity": -0.1}, "specificity"),
    ({"channel": "cyber"}, "channel"),           # ngoai taxonomy
    ({"commitment": "promise"}, "commitment"),
    ({"actor_country": "US"}, "ISO3"),           # ISO2 khong nhan
])
def test_parse_rejects_out_of_contract(mutation, match):
    bad = {**GOOD, **mutation}
    with pytest.raises(ScoreParseError, match=match):
        parse_score(json.dumps(bad))


def test_parse_rejects_missing_and_extra_keys():
    missing = {k: v for k, v in GOOD.items() if k != "channel"}
    with pytest.raises(ScoreParseError, match="thieu"):
        parse_score(json.dumps(missing))
    extra = {**GOOD, "market_impact_pct": -2.5}   # LLM sinh so ngoai schema
    with pytest.raises(ScoreParseError, match="thua"):
        parse_score(json.dumps(extra))
    with pytest.raises(ScoreParseError, match="JSON"):
        parse_score("The score is 0.92 because...")


def test_retry_then_success_and_hard_fail():
    """Lan 1 hong -> gui lai kem loi -> lan 2 dat. Hong het -> raise, khong bia."""
    responses = ["not json", json.dumps(GOOD)]

    def flaky(messages, temperature):
        return responses.pop(0)

    row = score_statement(stmt(), flaky, CONFIG, max_retries=1)
    assert row["v"] == pytest.approx(0.92)

    def always_bad(messages, temperature):
        return "nope"

    with pytest.raises(ScoreParseError, match="2 lan"):
        score_statement(stmt(), always_bad, CONFIG, max_retries=1)


# ---------------------------------------------------------------------------
# Encoder 2 tang
# ---------------------------------------------------------------------------
def test_encoder_filters_below_threshold_without_calling_llm():
    llm = fake_llm()
    out = score_statement(stmt(text="Happy National Day to our friends!"),
                          llm, CONFIG, encoder=lambda t: 0.1)
    assert out is None
    assert len(llm.calls) == 0, "encoder loc rot thi KHONG duoc ton tien goi LLM"


def test_encoder_pass_records_probability():
    row = score_statement(stmt(), fake_llm(), CONFIG, encoder=lambda t: 0.97)
    assert row["encoder_p"] == pytest.approx(0.97)


# ---------------------------------------------------------------------------
# Versioning + metadata
# ---------------------------------------------------------------------------
def test_batch_has_full_versioning_columns():
    scored, dropped = score_statements([stmt()], fake_llm(), CONFIG)
    assert list(scored.columns) == SCORE_COLUMNS
    r = scored.iloc[0]
    assert r["model_version"] == CONFIG.model_version
    assert r["rubric_version"] == RUBRIC_VERSION
    assert r["prompt_version"] == PROMPT_VERSION
    assert r["temperature"] == DEFAULT_TEMPERATURE
    assert r["training_cutoff"] == dt.date(2023, 10, 1)
    assert dropped.empty


def test_actor_from_metadata_not_llm():
    """docs/00 §2.1: actor biet chac tu metadata nguon — LLM chi la fallback."""
    llm = fake_llm({**GOOD, "actor_country": "CAN"})   # LLM doan sai
    row = score_statement(stmt(), llm, CONFIG)
    assert row["actor_country"] == "USA"               # metadata thang
    assert row["actor_country_llm"] == "CAN"           # van luu de audit
    row2 = score_statement(stmt(speaker_country=None), llm, CONFIG)
    assert row2["actor_country"] == "CAN"              # khong metadata -> fallback


def test_dropped_statements_are_traceable():
    def bad_llm(messages, temperature):
        return "garbage"

    scored, dropped = score_statements(
        [stmt(), stmt(text="Weather is nice.")], bad_llm, CONFIG,
        encoder=lambda t: 0.9 if "tariff" in t.lower() else 0.2, max_retries=0)
    assert scored.empty
    assert set(dropped["reason"]) == {"parse_error", "encoder_filtered"}


# ---------------------------------------------------------------------------
# Cache theo content_hash
# ---------------------------------------------------------------------------
def test_cache_prevents_rescoring_same_content():
    llm = fake_llm()
    cache: dict = {}
    score_statement(stmt(), llm, CONFIG, cache=cache)
    score_statement(stmt(), llm, CONFIG, cache=cache)
    assert len(llm.calls) == 1, "cung noi dung + cung spec -> cham dung 1 lan"


def test_hash_changes_with_model_version_and_text():
    a = content_hash(stmt(), "gpt-4o-mini")
    assert content_hash(stmt(), "qwen3-14b") != a, "doi model -> diem cu vo hieu"
    assert content_hash(stmt(text="Other text."), "gpt-4o-mini") != a


# ---------------------------------------------------------------------------
# Prompt: rubric + contamination
# ---------------------------------------------------------------------------
def test_prompt_contains_rubric_and_contamination_rules():
    assert "announced action" in SYSTEM_PROMPT           # bang neo docs/00 §2.3
    assert "effective immediately" in SYSTEM_PROMPT
    # Quy tac contamination docs/14 §3.1.1 — phai nam trong prompt, khong ngam hieu
    assert "never its consequences" in SYSTEM_PROMPT
    assert "events after the statement's date" in SYSTEM_PROMPT
    msgs = build_messages(stmt())
    assert msgs[0]["role"] == "system"
    assert "Donald Trump" in msgs[1]["content"]
    assert "tariffs" in msgs[1]["content"].lower()


def test_prompt_forbids_invented_numbers_in_rationale():
    """p1->p2 (2026-08-08): Guard P1 chan lien tuc rationale cua model (vd
    Gemini) chua so tu bia. Fix o nguon — prompt phai noi ro QUALITATIVE ONLY,
    khong chi dua vao Guard P1 lam luoi cuoi. Doi prompt ma quen bump
    PROMPT_VERSION la loi cache (content_hash dua tren PROMPT_VERSION)."""
    assert "QUALITATIVE ONLY" in SYSTEM_PROMPT
    assert "never invent numbers" in SYSTEM_PROMPT
    assert PROMPT_VERSION == "p2"


# ---------------------------------------------------------------------------
# published_at den phut (CLAUDE.md #5) + taxonomy mapping
# ---------------------------------------------------------------------------
def test_daily_source_rejects_date_only_timestamp():
    with pytest.raises(ValueError, match="00:00:00"):
        stmt(published_at=pd.Timestamp("2026-07-18"))
    s = stmt(published_at=pd.Timestamp("2026-07-18"), midnight_ok=True)
    assert s.published_at == pd.Timestamp("2026-07-18")
    s2 = stmt(published_at=pd.Timestamp("2026-07-18"), cadence="slow")
    assert s2.cadence == "slow"                          # nguon cham: ngay du


def test_transmission_mapping_only_obvious_pairs():
    """6 kenh cham -> 4 kenh bang γ: cap chua chot tra None, khong nhet bua."""
    assert to_transmission_channel("trade") == "trade"
    assert to_transmission_channel("military") == "military"
    assert to_transmission_channel("sanction") is None    # cho user chot
    assert to_transmission_channel("diplomacy") is None
    assert to_transmission_channel(None) is None
    with pytest.raises(ValueError):
        to_transmission_channel("cyber")
