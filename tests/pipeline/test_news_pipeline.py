"""Test pipeline.news_pipeline.process_news_item — fake LLM/history/jump/gamma,
KHONG Postgres/Kafka that (đúng quy ước hiện tại của repo, xem ingest/*.py).
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from gpr_engine.pipeline.news_pipeline import (
    ExcludedResult,
    NewsAssessment,
    process_news_item,
)
from gpr_engine.reporting.composer import GammaCell
from gpr_engine.scoring.statement_scorer import ScorerConfig, Statement

CONFIG = ScorerConfig(model_version="fake-v1", training_cutoff=dt.date(2026, 1, 1))
EMPTY_HISTORY = pd.DataFrame(columns=["published_at", "source", "actor_country",
                                      "target_country", "v", "specificity",
                                      "speaker_role"])


def _stmt(text="We will impose tariffs.", speaker_role="head_of_state",
         published_at="2026-08-03 14:07"):
    return Statement(source="truth_social", published_at=pd.Timestamp(published_at, tz="UTC"),
                     speaker="Trump", speaker_role=speaker_role, text=text)


def _jump_series(as_of="2026-08-03", spike=2.5, n_days=64):
    idx = pd.date_range(end=as_of, periods=n_days, freq="D", tz="UTC").normalize()
    vals = pd.Series(0.1, index=idx)
    vals.iloc[-1] = spike
    return vals


def _gamma_loader(cells=None):
    cells = cells if cells is not None else [
        GammaCell(outcome="oil (LEVEL·act)", horizon=1, beta=0.5, pvalue=0.03,
                  standardized=0.5, survived_holm=True, survived_battery=True)]
    return lambda channel: (cells, "fake_gamma.csv")


def _llm_json(**overrides):
    base = {"v": 0.85, "actor_country": "USA", "target_country": "CHN",
           "channel": "trade", "commitment": "announced_action",
           "specificity": 0.8, "rationale": "Tariff threat announced."}
    base.update(overrides)
    return lambda messages, temperature: json.dumps(base)


def test_encoder_filters_before_scoring():
    def boom(messages, temperature):
        raise AssertionError("encoder dưới ngưỡng phải chặn TRƯỚC khi gọi LLM")

    result = process_news_item(
        _stmt(), boom, CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader(), encoder=lambda text: 0.1)
    assert isinstance(result, ExcludedResult)
    assert result.reason == "encoder_filtered"


def test_full_happy_path_pair_identified():
    result = process_news_item(
        _stmt(), _llm_json(), CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader())
    assert isinstance(result, NewsAssessment)
    assert result.pair_identified is True
    assert result.measurement_card is not None
    assert result.measurement_card_error is None
    # tin dau tien cua cap -> S-GPR = w(head_of_state)=1.0 * v * specificity
    assert result.s_gpr_now == pytest.approx(0.85 * 0.8, rel=1e-6)
    # JUMP spike 2.5 vuot nguong 95th percentile chain A -> S4
    assert result.ladder_state == 4
    assert result.jump == pytest.approx(2.5)
    for tier_text in (result.measurement_card, result.macro_brief, result.vn_note):
        assert "_claim:" in tier_text


def test_no_pair_identified_skips_measurement_card_but_keeps_macro_and_vn():
    result = process_news_item(
        _stmt(), _llm_json(actor_country=None, target_country=None), CONFIG,
        lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    assert result.pair_identified is False
    assert result.measurement_card is None
    assert result.measurement_card_error is None
    assert "Model Brief" in result.macro_brief
    assert "VIỆT NAM" in result.vn_note


def test_unmapped_channel_gives_honest_vn_gap():
    result = process_news_item(
        _stmt(), _llm_json(channel="sanction"), CONFIG,
        lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    assert result.transmission_channel is None
    assert "chưa xác định" in result.vn_note.lower()


def test_measurement_card_degrades_gracefully_on_guard_violation():
    """rationale LLM chua so khong khop payload (25%) -> Guard P1 chan card,
    KHONG lam sap ca pipeline; macro_brief/vn_note van phat binh thuong."""
    result = process_news_item(
        _stmt(), _llm_json(rationale="Announced 25% tariff, effective immediately."),
        CONFIG, lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    assert result.measurement_card is None
    assert result.measurement_card_error is not None
    assert result.macro_brief and result.vn_note  # phan khac van phat


def test_gamma_channel_follows_commitment_proxy():
    result_act = process_news_item(
        _stmt(), _llm_json(commitment="announced_action"), CONFIG,
        lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    result_threat = process_news_item(
        _stmt(), _llm_json(commitment="rhetoric", v=0.1), CONFIG,
        lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    assert result_act.gamma_channel == "act"
    assert result_threat.gamma_channel == "threat"


def test_as_dict_is_json_ready_flat_mapping():
    result = process_news_item(
        _stmt(), _llm_json(), CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader())
    d = result.as_dict()
    assert d["v"] == 0.85 and d["actor_country"] == "USA"
    json.dumps(d)  # phai serialize duoc thang, khong con Timestamp/dataclass song


# ---------------------------------------------------------------------------
# Hai suy giam co kiem soat (vá theo review): chain-A cũ, speaker_role lạ
# ---------------------------------------------------------------------------
def test_chain_a_stale_when_jump_series_does_not_reach_as_of():
    """GPRD chưa refresh tới ngày của tin -> chain_a_stale=True, JUMP=0 KHÔNG
    được đọc là 'yên ắng' một cách âm thầm — có cờ + caveat trong macro_brief."""
    stale_jump = _jump_series(as_of="2026-06-01", n_days=64)  # dừng ở 06-01

    def jump_series_provider(as_of):
        return stale_jump

    result = process_news_item(
        _stmt(published_at="2026-08-03 14:07"), _llm_json(), CONFIG,
        lambda pair: EMPTY_HISTORY, jump_series_provider, _gamma_loader())
    assert result.chain_a_stale is True
    assert result.chain_a_last_available == pd.Timestamp("2026-06-01", tz="UTC")
    assert result.jump == 0.0  # dung nhung khong the doc la "khong co JUMP that"
    assert "chain a" in result.macro_brief.lower() or "chain A" in result.macro_brief
    assert "thiếu dữ liệu" in result.macro_brief.lower()


def test_chain_a_not_stale_when_jump_series_covers_as_of():
    result = process_news_item(
        _stmt(), _llm_json(), CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader())
    assert result.chain_a_stale is False


def test_unknown_speaker_role_degrades_instead_of_crashing():
    """Vai trò không có trong w(role) -> trước đây KeyError bay lên tận
    run_consumer_loop và tin biến mất; giờ suy giảm có kiểm soát, macro/VN vẫn
    phát, measurement_card=None kèm lý do rõ ràng."""
    result = process_news_item(
        _stmt(speaker_role="unknown_role_xyz"), _llm_json(), CONFIG,
        lambda pair: EMPTY_HISTORY, _jump_series, _gamma_loader())
    assert isinstance(result, NewsAssessment)
    assert result.measurement_card is None
    assert result.measurement_card_error is not None
    assert "vai trò" in result.measurement_card_error.lower()
    assert result.macro_brief and result.vn_note  # phan khac van phat binh thuong
    assert result.s_gpr_now == 0.0 and result.ladder_state == 0  # khong tinh duoc, khong bia
    assert result.ladder_computed is False  # phan biet voi S0 THAT (xem test duoi)


def test_ladder_computed_true_on_success():
    result = process_news_item(
        _stmt(), _llm_json(), CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader())
    assert result.ladder_computed is True


# ---------------------------------------------------------------------------
# published_at tz-naive (rà lại sau khi vá lần 2): Statement cho phép naive,
# nhung phan con lai cua pipeline (Postgres, test fixture khac) la tz-aware
# UTC — tron hai loai lam pandas raise TypeError/ValueError o nhieu diem.
# ---------------------------------------------------------------------------
def test_tz_naive_published_at_does_not_crash():
    naive_stmt = Statement(source="truth_social",
                           published_at=pd.Timestamp("2026-08-03 14:07"),  # KHONG co tz
                           speaker="Trump", speaker_role="head_of_state",
                           text="We will impose tariffs.")
    result = process_news_item(
        naive_stmt, _llm_json(), CONFIG, lambda pair: EMPTY_HISTORY, _jump_series,
        _gamma_loader())
    assert isinstance(result, NewsAssessment)
    assert result.pair_identified is True
    assert result.ladder_computed is True
    assert result.measurement_card is not None
    assert result.s_gpr_now == pytest.approx(0.85 * 0.8, rel=1e-6)


def test_tz_naive_published_at_mixes_with_tz_aware_history_without_crash():
    """History (fake DB) tz-aware, tin moi tz-naive — day la to hop de crash
    thuc te nhat (pd.concat roi to_datetime tren cot lan tz-aware/naive)."""
    aware_history = pd.DataFrame({
        "published_at": [pd.Timestamp("2026-08-01 10:00", tz="UTC")],
        "source": ["mofa_cn"], "actor_country": ["USA"], "target_country": ["CHN"],
        "v": [0.3], "specificity": [0.4], "speaker_role": ["spokesperson"],
    })
    naive_stmt = Statement(source="truth_social",
                           published_at=pd.Timestamp("2026-08-03 14:07"),
                           speaker="Trump", speaker_role="head_of_state",
                           text="We will impose tariffs.")
    result = process_news_item(
        naive_stmt, _llm_json(), CONFIG, lambda pair: aware_history, _jump_series,
        _gamma_loader())
    assert isinstance(result, NewsAssessment)
    assert result.ladder_computed is True
