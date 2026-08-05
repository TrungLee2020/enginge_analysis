"""Test pipeline.news_pipeline.process_news_item_live wiring — mock service.store
+ gamma_lookup (KHONG Postgres that, dung mock de kiem tra ORCHESTRATION:
goi dung ham, dung dieu kien, khong phai kinh te luong — cai do da test o
test_news_pipeline.py roi).
"""
from __future__ import annotations

import datetime as dt
import json
from unittest.mock import patch

import pandas as pd
import pytest

from gpr_engine.pipeline.news_pipeline import process_news_item_live
from gpr_engine.reporting.composer import GammaCell
from gpr_engine.scoring.statement_scorer import ScorerConfig, Statement

CONFIG = ScorerConfig(model_version="fake-v1", training_cutoff=dt.date(2026, 1, 1))
EMPTY_HISTORY = pd.DataFrame(columns=["published_at", "source", "actor_country",
                                      "target_country", "v", "specificity",
                                      "speaker_role"])


def _stmt(speaker_role="head_of_state"):
    return Statement(source="truth_social", published_at=pd.Timestamp("2026-08-03 14:07", tz="UTC"),
                     speaker="Trump", speaker_role=speaker_role, text="We will impose tariffs.")


def _llm(messages, temperature):
    return json.dumps({"v": 0.85, "actor_country": "USA", "target_country": "CHN",
                       "channel": "trade", "commitment": "announced_action",
                       "specificity": 0.8, "rationale": "Tariff threat announced."})


def _jump_series():
    idx = pd.date_range(end="2026-08-03", periods=64, freq="D", tz="UTC").normalize()
    vals = pd.Series(0.1, index=idx)
    vals.iloc[-1] = 2.5
    return vals


@pytest.fixture
def mocked_store(tmp_path):
    """Mock toan bo I/O — engine gia, cac ham store.* thanh Mock ghi lai duoc goi."""
    with patch("gpr_engine.service.store.get_engine") as m_engine, \
         patch("gpr_engine.service.store.load_pair_history", return_value=EMPTY_HISTORY), \
         patch("gpr_engine.service.store.load_jump_series", return_value=_jump_series()), \
         patch("gpr_engine.service.store.insert_statement", return_value=1), \
         patch("gpr_engine.service.store.insert_statement_score") as m_score, \
         patch("gpr_engine.service.store.upsert_ladder_state") as m_ladder, \
         patch("gpr_engine.service.store.insert_news_assessment") as m_assess, \
         patch("gpr_engine.pipeline.gamma_lookup.load_published_gamma",
               return_value=([GammaCell(outcome="oil", horizon=1, beta=0.5, pvalue=0.03,
                                        standardized=0.5, survived_holm=True,
                                        survived_battery=True)], "fake.csv")):
        m_engine.return_value = object()
        yield {"ladder": m_ladder, "score": m_score, "assess": m_assess, "engine": m_engine}


def test_ladder_state_persisted_when_computation_succeeds(mocked_store):
    result = process_news_item_live(_stmt(), "postgresql://fake", _llm, CONFIG)
    assert result.ladder_computed is True
    mocked_store["ladder"].assert_called_once()
    args = mocked_store["ladder"].call_args.args
    assert args[1] == "USA>CHN"
    assert args[3] == result.ladder_state  # dung gia tri THAT, khong phai 0 mac dinh


def test_ladder_state_NOT_persisted_when_role_unknown(mocked_store):
    """Bug da vá: truoc day ham nay ghi ladder_state=0 (gia) de len DB khi vai
    tro la, co the de len mot trang thai DUNG da co truoc do cua ngay hom do."""
    result = process_news_item_live(_stmt(speaker_role="unknown_xyz"),
                                    "postgresql://fake", _llm, CONFIG)
    assert result.ladder_computed is False
    assert result.measurement_card_error is not None
    mocked_store["ladder"].assert_not_called()
    # nhung statement/score/assessment van phai duoc ghi — khong mat tin
    mocked_store["score"].assert_called_once()
    mocked_store["assess"].assert_called_once()


def test_engine_created_lazily_when_not_injected_backward_compat(mocked_store):
    """Khong tiem `engine=` -> ham tu goi store.get_engine(dsn) nhu truoc (goi
    don le / test cu khong doi hanh vi)."""
    process_news_item_live(_stmt(), "postgresql://fake", _llm, CONFIG)
    mocked_store["engine"].assert_called_once_with("postgresql://fake")


def test_injected_engine_reused_across_calls_no_new_pool_per_message(mocked_store):
    """Bug da vá (audit production-readiness 2026-08-05): truoc ban va, MOI
    lan goi ham nay (tuc MOI message Kafka trong run_news_service.py) tu tao
    MOT SQLAlchemy engine moi qua store.get_engine(dsn) — connection pool moi
    khong bao gio dispose, ro ri connection duoi tai lien tuc. Tiem `engine=`
    co san (nhu run_news_service.main() lam MOT LAN cho ca vong doi consumer)
    phai bo qua get_engine hoan toan, du goi nhieu lan."""
    fake_engine = object()
    process_news_item_live(_stmt(), "postgresql://fake", _llm, CONFIG, engine=fake_engine)
    process_news_item_live(_stmt(), "postgresql://fake", _llm, CONFIG, engine=fake_engine)
    mocked_store["engine"].assert_not_called()
