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

# Chuoi chan A mac dinh cho JUMP. Truoc 2026-08-08 gia tri nay hard-code trong
# SQL cua load_jump_series; tach ra hang so + tham so de thu chuoi khac (vd
# 'AIGPR' da ingest qua ingest/ai_gpr.py) khong phai sua ma nguon. Mac dinh
# GIU NGUYEN 'GPRD' — doi mac dinh la doi thuoc do shock, phai qua governance
# (xem docs/reports/E3_aigpr_jump_*.md §6 khuyen nghi 1).
CHAIN_A_SERIES_DEFAULT = "GPRD"
CHAIN_A_SERIES_AIGPR = "AIGPR"
# Nguong coi chuoi chinh la "qua cu de dung" khi CO khai bao fallback. Bang
# DEFAULT_CHAIN_A_STALE_AFTER_DAYS cua news_pipeline (35) de mot tin bi gan co
# `chain_a_stale` va mot tin kich fallback la CUNG mot moc — hai nguong lech
# nhau se tao vung xam: da fallback nhung van bao stale, hoac nguoc lai.
CHAIN_A_FALLBACK_AFTER_DAYS = 35


def _as_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """Chuan hoa ve tz-aware UTC truoc khi ghi TIMESTAMPTZ — cung ly do voi
    `pipeline.news_pipeline._as_utc` (Statement.published_at co the naive,
    ghi naive vao cot TIMESTAMPTZ phu thuoc session timezone cua Postgres,
    khong dam bao la UTC). Nhan ban nho, khong tao module dung chung cho 1 dong."""
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def get_engine(dsn: str) -> "Engine":
    from sqlalchemy import create_engine
    return create_engine(dsn)


def load_pair_history(engine: "Engine", pair: str, before: pd.Timestamp) -> pd.DataFrame:
    """Lich su statement_scores cua CAP actor>target, CHI truoc `before` (#11).

    Tra DataFrame khop `indices.s_gpr.REQUIRED_SCORE_COLS` — cot khong co gi
    thi tra DataFrame RONG cung khop schema, khong None (caller nap thang vao
    `s_gpr_pair` qua `pd.concat`).

    `statement_scores` PK la (statement_id, model_version, rubric_version) —
    MOT statement co the co NHIEU hang neu tung duoc cham lai voi model/rubric
    khac (nang cap model chang han). `DISTINCT ON (s.id) ... ORDER BY s.id,
    sc.scored_at DESC` lay dung BAN CHAM MOI NHAT cho moi statement — thieu no,
    statement do vao S-GPR NHIEU LAN (mot lan/version), lam sai het rolling sum.
    """
    from sqlalchemy import text

    actor, target = pair.split(">")
    sql = text("""
        SELECT published_at, source, actor_country, target_country, v,
               specificity, speaker_role
        FROM (
            SELECT DISTINCT ON (s.id)
                   s.id, s.published_at, s.source, sc.actor_country,
                   sc.target_country, sc.v, sc.specificity, s.speaker_role
            FROM statements s
            JOIN statement_scores sc ON sc.statement_id = s.id
            WHERE sc.actor_country = :actor AND sc.target_country = :target
              AND s.published_at < :before
            ORDER BY s.id, sc.scored_at DESC
        ) latest
        ORDER BY published_at
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


def _load_raw_chain_a(engine: "Engine", as_of: pd.Timestamp,
                      series_id: str) -> pd.Series:
    """Chuoi THO chan A (chua tinh JUMP) cua MOT series_id, point-in-time (#11).

    Chi dung hang co `available_at <= as_of` — dung `date` lam proxy la
    look-ahead bias (CLAUDE.md #11, khop `ingest/gpr_daily.py`).

    `ext_series` PK la (series_id, date, data_version) — MOI LAN tai lai file
    GPR va gan `data_version` moi (khuyen nghi da dua ra: "moi lan tai lai =
    mot data_version moi") se tao THEM mot hang cho CUNG mot date. Khong loc,
    truy van se tra ve hang TRUNG NGAY — series dua vao `shocks.jump()` (rolling
    window tren VI TRI hang, khong phai tren ngay lich) se dem trung ngay
    nhieu lan va lam sai het cua so rolling. `DISTINCT ON (date) ... ORDER BY
    date, loaded_at DESC` lay dung ban ghi MOI NAP GAN NHAT cho moi ngay.
    """
    from sqlalchemy import text

    start = (as_of - pd.Timedelta(days=JUMP_HISTORY_DAYS)).date()
    sql = text("""
        SELECT date, value FROM (
            SELECT DISTINCT ON (date) date, value
            FROM ext_series
            WHERE series_id = :series_id AND date >= :start
              AND available_at <= :as_of
            ORDER BY date, loaded_at DESC
        ) latest
        ORDER BY date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"series_id": series_id, "start": start,
                                            "as_of": as_of.to_pydatetime()})
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["value"].to_numpy(),
                     index=pd.to_datetime(df["date"], utc=True))


def load_jump_series(
    engine: "Engine",
    as_of: pd.Timestamp,
    series_id: str = CHAIN_A_SERIES_DEFAULT,
    fallback_series_id: str | None = None,
    fallback_after_days: int = CHAIN_A_FALLBACK_AFTER_DAYS,
) -> pd.Series:
    """Chuoi JUMP chan A tinh den `as_of` — point-in-time (#11).

    `series_id` mac dinh 'GPRD' -> HANH VI KHONG DOI so voi ban truoc khi tham
    so hoa. Truoc day gia tri nay hard-code trong SQL, muon thu chuoi khac
    (vd AI-GPR da ingest qua `ingest/ai_gpr.py`) buoc phai sua ma nguon.

    `fallback_series_id`: chuoi du phong, CHI dung khi chuoi chinh rong hoac
    ban ghi moi nhat cach `as_of` qua `fallback_after_days` ngay. Mac dinh None
    = KHONG fallback (giu nguyen hanh vi cu: chuoi chinh cu thi tra ve chinh no,
    caller tu gan co `chain_a_stale`).

    ⚠️ Fallback DOI THUOC DO, khong phai doi cach doc cung mot thuoc do:
    E3 (`docs/reports/E3_aigpr_jump_*.md`) do duoc GPRD va AI-GPR co CUNG tan
    suat kich S4 (~5.2%, on dinh qua 3 giai doan — nen KHONG phai hieu chuan
    lai q95/q99 nhu `docs/16` §5 tung khang dinh), NHUNG chi trung nhau khoang
    mot phan nam so ngay kich (Jaccard 0.203). Vi vay chuoi da dung duoc ghi
    vao `Series.attrs["series_id"]` — caller PHAI neu ro trong output thay vi
    de nguoi doc tuong mot ngay S4 luon den tu cung mot thuoc do.
    """
    from ..econometrics.shocks import jump as compute_jump

    used = series_id
    s = _load_raw_chain_a(engine, as_of, series_id)
    if fallback_series_id is not None:
        last = s.index.max() if len(s) else None
        stale = last is None or (as_of - last).days > fallback_after_days
        if stale:
            alt = _load_raw_chain_a(engine, as_of, fallback_series_id)
            alt_last = alt.index.max() if len(alt) else None
            # Chi doi khi chuoi du phong THAT SU moi hon — fallback sang mot
            # chuoi cung cu (hoac cung rong) chi lam mat dau vet nguon goc.
            if alt_last is not None and (last is None or alt_last > last):
                s, used = alt, fallback_series_id
    if s.empty:
        out = pd.Series(dtype=float)
        out.attrs["series_id"] = used
        return out
    out = compute_jump(s, min_periods=JUMP_MIN_PERIODS)
    # `attrs` KHONG tu dong truyen qua compute_jump (pandas chi giu attrs o mot
    # so phep toan) — gan lai TAI DAY, sau khi tinh. Quen dong nay thi caller
    # doc attrs se thay rong va tuong dang dung chuoi mac dinh.
    out.attrs["series_id"] = used
    return out


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
            "published_at": _as_utc(stmt.published_at).to_pydatetime(),
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
