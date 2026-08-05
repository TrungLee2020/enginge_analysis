"""store.py — Postgres I/O cho pipeline production (schema sql/002_schema_serving.sql).

🏭 production-path. Cung pattern SQLAlchemy `create_engine` + `text()` UPSERT
da dung trong `ingest/gpr_daily.py` — khong phat minh pattern moi.

Module nay la LOP I/O MONG duoc `pipeline.news_pipeline.process_news_item_live`
goi; logic (S-GPR/ladder/gamma/VN) nam het o `pipeline/`, o day chi doc/ghi.
Khong co test DB that trong repo (giong het `ingest/*.py` — khong Postgres
song trong sandbox CI); import lazy (sqlalchemy/psycopg2) de khong ep test
khac phai co driver DB.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from ..pipeline.news_pipeline import NewsAssessment
    from ..scoring.statement_scorer import Statement

JUMP_HISTORY_DAYS = 1095       # ~3 nam — du dem cho rolling window=250 cua jump()
JUMP_MIN_PERIODS = None        # None -> shocks.jump tu chon max(20, window//4)


def get_engine(dsn: str) -> "Engine":
    from sqlalchemy import create_engine
    return create_engine(dsn)


def load_pair_history(engine: "Engine", pair: str, before: pd.Timestamp) -> pd.DataFrame:
    """Lich su statement_scores cua CAP actor>target, CHI truoc `before` (#11).

    Tra DataFrame khop `indices.s_gpr.REQUIRED_SCORE_COLS` — cot khong co gi
    thi tra DataFrame RONG cung khop schema, khong None (caller nap thang vao
    `s_gpr_pair` qua `pd.concat`).
    """
    from sqlalchemy import text

    actor, target = pair.split(">")
    sql = text("""
        SELECT s.published_at, s.source, sc.actor_country, sc.target_country,
               sc.v, sc.specificity, s.speaker_role
        FROM statements s
        JOIN statement_scores sc ON sc.statement_id = s.id
        WHERE sc.actor_country = :actor AND sc.target_country = :target
          AND s.published_at < :before
        ORDER BY s.published_at
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"actor": actor, "target": target,
                                            "before": before.to_pydatetime()})
    if df.empty:
        return pd.DataFrame(columns=["published_at", "source", "actor_country",
                                     "target_country", "v", "specificity",
                                     "speaker_role"])
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    return df


def load_jump_series(engine: "Engine", as_of: pd.Timestamp) -> pd.Series:
    """Chuoi JUMP THO (chan A, GPRD daily) tinh den `as_of` — point-in-time (#11).

    Chi dung hang co `available_at <= as_of` — dung `date` lam proxy la
    look-ahead bias (CLAUDE.md #11, khop `ingest/gpr_daily.py`).
    """
    from sqlalchemy import text

    from ..econometrics.shocks import jump as compute_jump

    start = (as_of - pd.Timedelta(days=JUMP_HISTORY_DAYS)).date()
    sql = text("""
        SELECT date, value FROM ext_series
        WHERE series_id = 'GPRD' AND date >= :start AND available_at <= :as_of
        ORDER BY date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"start": start, "as_of": as_of.to_pydatetime()})
    if df.empty:
        return pd.Series(dtype=float)
    s = pd.Series(df["value"].to_numpy(), index=pd.to_datetime(df["date"], utc=True))
    return compute_jump(s, min_periods=JUMP_MIN_PERIODS)


def insert_statement(engine: "Engine", stmt: "Statement") -> int:
    from sqlalchemy import text

    sql = text("""
        INSERT INTO statements (source, url, published_at, speaker, speaker_role,
                                speaker_country, text, lang, cadence)
        VALUES (:source, :url, :published_at, :speaker, :speaker_role,
                :speaker_country, :text, :lang, :cadence)
        RETURNING id
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {
            "source": stmt.source, "url": stmt.url,
            "published_at": stmt.published_at.to_pydatetime(),
            "speaker": stmt.speaker, "speaker_role": stmt.speaker_role,
            "speaker_country": stmt.speaker_country, "text": stmt.text,
            "lang": stmt.lang, "cadence": stmt.cadence,
        }).first()
    return int(row[0])


def insert_statement_score(engine: "Engine", statement_id: int, score: dict) -> None:
    from sqlalchemy import text

    sql = text("""
        INSERT INTO statement_scores (
            statement_id, v, actor_country, target_country, channel, commitment,
            specificity, rationale, encoder_p, model_version, rubric_version,
            prompt_version, temperature, training_cutoff, content_hash)
        VALUES (
            :statement_id, :v, :actor_country, :target_country, :channel, :commitment,
            :specificity, :rationale, :encoder_p, :model_version, :rubric_version,
            :prompt_version, :temperature, :training_cutoff, :content_hash)
        ON CONFLICT (statement_id, model_version, rubric_version)
        DO UPDATE SET v = EXCLUDED.v, actor_country = EXCLUDED.actor_country,
            target_country = EXCLUDED.target_country, channel = EXCLUDED.channel,
            commitment = EXCLUDED.commitment, specificity = EXCLUDED.specificity,
            rationale = EXCLUDED.rationale, content_hash = EXCLUDED.content_hash,
            scored_at = now()
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"statement_id": statement_id, **score})


def upsert_ladder_state(engine: "Engine", pair: str, date, state: int,
                        days_in_state: int, config_version: str) -> None:
    from sqlalchemy import text

    sql = text("""
        INSERT INTO ladder_state (pair, date, state, days_in_state, config_version)
        VALUES (:pair, :date, :state, :days_in_state, :config_version)
        ON CONFLICT (pair, date, config_version)
        DO UPDATE SET state = EXCLUDED.state, days_in_state = EXCLUDED.days_in_state,
            computed_at = now()
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"pair": pair, "date": date, "state": state,
                           "days_in_state": days_in_state,
                           "config_version": config_version})


def insert_news_assessment(engine: "Engine", statement_id: int,
                           result: "NewsAssessment") -> None:
    from sqlalchemy import text

    sql = text("""
        INSERT INTO news_assessment (
            statement_id, gamma_channel_used, transmission_channel, s_gpr_now,
            s_gpr_prev, s_gpr_pctile, ladder_state, chain_a_last_available,
            chain_a_stale, measurement_card, macro_brief, vn_note, gamma_data_version)
        VALUES (
            :statement_id, :gamma_channel_used, :transmission_channel, :s_gpr_now,
            :s_gpr_prev, :s_gpr_pctile, :ladder_state, :chain_a_last_available,
            :chain_a_stale, :measurement_card, :macro_brief, :vn_note, :gamma_data_version)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "statement_id": statement_id,
            "gamma_channel_used": result.gamma_channel,
            "transmission_channel": result.transmission_channel,
            "s_gpr_now": result.s_gpr_now, "s_gpr_prev": result.s_gpr_prev,
            "s_gpr_pctile": result.s_gpr_pctile, "ladder_state": result.ladder_state,
            "chain_a_last_available": (result.chain_a_last_available.date()
                                       if result.chain_a_last_available is not None else None),
            "chain_a_stale": result.chain_a_stale,
            "measurement_card": result.measurement_card or "",
            "macro_brief": result.macro_brief, "vn_note": result.vn_note,
            "gamma_data_version": result.gamma_data_version,
        })
