"""news_pipeline.py — orchestrator "MOT tin vao -> MOT ket qua ra". 🏭 production-path

Ghep cac khoi da co (khong viet lai kinh te luong): scoring.statement_scorer
(cham diem) -> indices.s_gpr + econometrics.ladder (trang thai) ->
pipeline.gamma_lookup (tang 2, vi mo toan cau) -> pipeline.vn_exposure (tang 3
VN, dinh tinh) -> reporting.composer (van ban, Guard P1 chan o cua ra).

Moi I/O (Postgres, file gamma) duoc TIEM VAO qua callable, dung pattern
`LLMClient` da co trong statement_scorer.py — `process_news_item` la ham thuan,
test bang fake, khong can Postgres/Kafka that. `process_news_item_live` la lop
mong noi callable that vao Postgres + file gamma, dung cho
`scripts/run_news_service.py`.

⚠️ Hai gioi han THAT cua V1 (xem ke hoach da duyet — khong am tham bo qua):
  - `analogues=[]` luon rong: batch_analogues can dung panel thang xay tu FRED,
    qua nang de chay MOI tin. Model Brief van hop le khi rong (composer da xu
    ly "khong du tien le").
  - Tang 3 VN CHUA dinh luong (xem `pipeline.vn_exposure` docstring) — chi
    kenh + huong.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pandas as pd

from ..econometrics.ladder import (
    DEFAULT_LADDER_CONFIG,
    LadderConfig,
    classify_ladder,
    load_ladder_config,
)
from ..indices.s_gpr import (
    DEFAULT_ROLE_WEIGHTS_INIT,
    REQUIRED_SCORE_COLS,
    expanding_percentile,
    pair_key,
    s_gpr_pair,
)
from ..reporting.composer import (
    ClaimCeilingViolation,
    GammaCell,
    MeasurementPayload,
    compose_measurement_card,
    compose_model_brief,
    compose_vn_note,
)
from ..reporting.guard import GuardViolation
from ..scoring.statement_scorer import (
    EncoderFn,
    LLMClient,
    ScorerConfig,
    Statement,
    score_statement,
    to_transmission_channel,
)
from .gamma_lookup import commitment_to_gamma_channel
from .vn_exposure import vn_exposure_note

DEFAULT_S_GPR_WINDOW = 7
DEFAULT_MIN_PERIODS = 60
MACRO_OUTCOMES = {"oil", "dxy", "vix", "us10y", "ip", "cpi", "infl_exp", "freight"}
# Nguon GPR (Caldara-Iacoviello) xac nhan cap nhat ~1 lan/thang (quanh ngay 10,
# https://www.policyuncertainty.com/gpr.html) cho ban quoc gia/thang; ban DAILY
# (GPRD, dung o day) CHUA xac nhan duoc cadence that (trang chinh chan fetch tu
# dong). 35 ngay = ~1 chu ky thang + dem — CHINH LAI cho khop cadence THAT ban
# quan sat duoc sau khi van hanh, dung dung so nay lam chan ly.
DEFAULT_CHAIN_A_STALE_AFTER_DAYS = 35

# Callable tiem vao — production doc that tu Postgres/file, test dung fake.
HistoryProvider = Callable[[str], pd.DataFrame]           # pair -> lich su statement_scores
JumpSeriesProvider = Callable[[pd.Timestamp], pd.Series]  # as_of -> chuoi JUMP tho (chain A)
GammaLoader = Callable[[str], tuple[list[GammaCell], str]]  # gamma_channel -> (cells, file)


def _as_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """Chuan hoa ve tz-aware UTC.

    `statement_scorer.Statement.published_at` KHONG bat buoc co tzinfo (nhieu
    test/caller da dung Timestamp naive tu truoc — xem tests/test_statement_scorer.py,
    tests/test_chain_b_pipeline.py) nen KHONG sua contract cua Statement o day.
    Nhung pipeline nay so sanh/join `as_of` voi cac chuoi tz-aware UTC tu
    Postgres (`ext_series.available_at`, `statement_scores`) — tron naive voi
    aware la `TypeError` cua pandas (da kiem chung), khong phai gia thuyet.
    Day la RANH GIOI cua pipeline nay: gia dinh UTC khi thieu tzinfo, KHONG
    raise — hop ly vi moi nguon du lieu con lai trong he thong nay (DB, test
    fixture, `generated_at` mac dinh) deu la UTC.
    """
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


@dataclass(frozen=True)
class ExcludedResult:
    """Tin bi encoder loc — khong cham, khong tinh gi them (statement_scorer.score_statement trả None)."""
    stmt: Statement
    reason: str = "encoder_filtered"


@dataclass(frozen=True)
class NewsAssessment:
    """Ket qua day du cua MOT tin — payload nay la thu duoc persist + publish Kafka."""
    stmt: Statement
    score: dict
    pair_identified: bool
    gamma_channel: str
    transmission_channel: str | None
    s_gpr_now: float
    s_gpr_prev: float
    s_gpr_pctile: float
    ladder_state: int
    ladder_prev_state: int
    days_in_state: int
    ladder_computed: bool           # False: ladder_state=0 la GIA TRI MAC
                                    # DINH (tinh hong), KHONG phai S0 that
    jump: float
    jump_pctile: float
    chain_a_last_available: pd.Timestamp | None  # ngay moi nhat co du lieu GPRD
    chain_a_stale: bool             # True: JUMP=0/S4 khong len co the do THIEU
                                    # du lieu chain-A, khong phai do that su yen
    measurement_card: str | None   # None neu khong xac dinh duoc actor/target
    measurement_card_error: str | None  # ly do card=None khi CO xac dinh pair
                                        # nhung Guard P1/tran claim chan (vd
                                        # rationale LLM chua so khong khop payload)
    macro_brief: str
    vn_note: str
    gamma_data_version: str
    generated_at: dt.datetime

    def as_dict(self) -> dict:
        """Dang phang de publish JSON len Kafka / ghi news_assessment."""
        d = {k: v for k, v in self.__dict__.items() if k not in ("stmt", "score")}
        d["published_at"] = self.stmt.published_at.isoformat()
        d["source"] = self.stmt.source
        d["speaker"] = self.stmt.speaker
        d["speaker_role"] = self.stmt.speaker_role
        d["generated_at"] = self.generated_at.isoformat(timespec="seconds")
        d["chain_a_last_available"] = (self.chain_a_last_available.isoformat()
                                       if self.chain_a_last_available is not None else None)
        d["v"] = self.score["v"]
        d["channel"] = self.score["channel"]
        d["commitment"] = self.score["commitment"]
        d["actor_country"] = self.score["actor_country"]
        d["target_country"] = self.score["target_country"]
        d["content_hash"] = self.score["content_hash"]
        return d


def _pair_indicator_frame(
    history: pd.DataFrame,
    current_row: dict,
    jump_series: pd.Series,
    window: int,
    min_periods: int,
    role_weights: Mapping[str, float] | None,
) -> tuple[pd.DataFrame, pd.Series]:
    """S-GPR + JUMP percentile (ca hai EXPANDING, khong nhin tuong lai) -> ladder input.

    quad3_pct/quad4_pct luon NaN (chan C GDELT chua ingest — han che THAT, ghi
    trong config/ladder_v1.yaml, khong phai loi o day).
    """
    combined = pd.concat(
        [history[REQUIRED_SCORE_COLS], pd.DataFrame([current_row])[REQUIRED_SCORE_COLS]],
        ignore_index=True)
    pair_idx = s_gpr_pair(combined, window=window, role_weights=role_weights)
    pair = pair_key(current_row["actor_country"], current_row["target_country"])
    series = (pair_idx[pair_idx["pair"] == pair]
              .set_index("date")["s_gpr"].sort_index())
    s_gpr_pct = expanding_percentile(series, min_periods=min_periods)

    jump_pct = expanding_percentile(jump_series.sort_index(), min_periods=min_periods)

    indicators = pd.DataFrame({"s_gpr_pair_pct": s_gpr_pct}).join(
        pd.DataFrame({"jump_pct": jump_pct}), how="outer").sort_index()
    indicators["quad3_pct"] = float("nan")
    indicators["quad4_pct"] = float("nan")
    return indicators, series


def process_news_item(
    stmt: Statement,
    llm: LLMClient,
    config: ScorerConfig,
    history_provider: HistoryProvider,
    jump_series_provider: JumpSeriesProvider,
    gamma_loader: GammaLoader,
    encoder: EncoderFn | None = None,
    role_weights: Mapping[str, float] | None = None,
    ladder_config: LadderConfig | None = None,
    s_gpr_window: int = DEFAULT_S_GPR_WINDOW,
    min_periods: int = DEFAULT_MIN_PERIODS,
    detection_seconds: int | None = None,
    now: dt.datetime | None = None,
    chain_a_stale_after_days: int = DEFAULT_CHAIN_A_STALE_AFTER_DAYS,
) -> NewsAssessment | ExcludedResult:
    """Xu ly MOT tin: cham -> S-GPR/Ladder -> gamma tang 2 -> VN tang 3 -> compose.

    `history_provider(pair)`: tra lich su statement_scores CUA CAP actor>target,
    CHI gom ban ghi co `published_at` TRUOC tin hien tai (khong bao gom tin
    hien tai, khong nhin tuong lai — trach nhiem cua caller, giong quy uoc
    `available_at` cua CLAUDE.md #11) — cot khop REQUIRED_SCORE_COLS.
    `jump_series_provider(as_of)`: tra chuoi JUMP THO (chain A, GPRD daily) tinh
    den `as_of`, dung tinh phan vi tai cho (`caller tinh percentile`, dung tinh
    than econometrics.ladder — ladder chi so sanh nguong, khong tu tinh).
    `gamma_loader(gamma_channel)`: tra (danh sach GammaCell, ten file da doc).

    Hai suy giam co kiem soat (khong crash, khong am tham mat tin):
    - `speaker_role` la ma bang trong so w(role) (`DEFAULT_ROLE_WEIGHTS_INIT`
      hoac `role_weights` tiem vao) -> `measurement_card=None` +
      `measurement_card_error` ghi ro ly do, S-GPR/Ladder cho tin nay bi bo
      qua (khong the tinh w(role)), nhung gamma/VN note van phat binh thuong.
    - chain A (GPRD) khong co du lieu toi `as_of` (qua `chain_a_stale_after_days`
      ngay so voi ban ghi moi nhat) -> `chain_a_stale=True`, ghi vao
      `sample_caveat` cua macro_brief. JUMP/Ladder S4 khi do co the chi phan
      anh "thieu du lieu", KHONG phai "that su yen ang" — dung doc hai ca do
      nhu nhau.
    """
    generated_at = now or dt.datetime.now(dt.timezone.utc)
    score = score_statement(stmt, llm, config, encoder=encoder)
    if score is None:
        return ExcludedResult(stmt=stmt)
    # score["published_at"] la ban sao THO cua stmt.published_at (co the naive
    # — xem _as_utc). Chuan hoa NGAY tai day: no se duoc noi (pd.concat) voi
    # `history` tz-aware trong _pair_indicator_frame, va pandas raise
    # ValueError "Cannot mix tz-aware with tz-naive values" khi to_datetime()
    # mot cot lan lon hai loai — da kiem chung, khong phai gia thuyet.
    score["published_at"] = _as_utc(score["published_at"])

    as_of = _as_utc(stmt.published_at).normalize()
    jump_series = jump_series_provider(as_of)
    jump_val = float(jump_series.loc[as_of]) if as_of in jump_series.index else 0.0
    chain_a_last_available = jump_series.index.max() if len(jump_series) else None
    chain_a_stale = (chain_a_last_available is None
                     or (as_of - chain_a_last_available).days > chain_a_stale_after_days)

    gamma_channel = commitment_to_gamma_channel(score["commitment"])
    gamma_cells, gamma_file = gamma_loader(gamma_channel)

    transmission_channel = to_transmission_channel(score["channel"])
    vn = vn_exposure_note(transmission_channel)

    sample_caveat = ("γ tầng 2 chưa tách theo kênh truyền dẫn "
                     "energy/trade/financial/military — dùng proxy "
                     "commitment→channel(pooled/act/threat), xem "
                     "pipeline/gamma_lookup.py")
    if chain_a_stale:
        last_str = (chain_a_last_available.date().isoformat()
                   if chain_a_last_available is not None else "chưa có dữ liệu")
        sample_caveat += (f" · ⚠️ chain A (GPRD) mới nhất {last_str}, quá "
                          f"{chain_a_stale_after_days} ngày so với tin này — "
                          "JUMP/Ladder S4 có thể im lặng vì THIẾU dữ liệu, "
                          "không phải vì thật sự yên ắng.")
    meta = {"generated_at": generated_at.isoformat(timespec="seconds"),
            "data_version": gamma_file, "git_commit": "n/a",
            "n_obs": len(gamma_cells), "sample_caveat": sample_caveat}
    trigger = {"label": f"tin: {stmt.source}/{stmt.speaker}",
               "reason": f"v={score['v']:+.2f}, commitment={score['commitment']}, "
                         f"channel={score['channel']}"}
    macro_brief = compose_model_brief(
        trigger, gamma_cells, [], {"v": score["v"],
                                   "chain_a_stale_after_days": chain_a_stale_after_days},
        meta, skipped=[])
    vn_note_text = compose_vn_note(vn, {"generated_at": meta["generated_at"]})

    pair_identified = bool(score["actor_country"] and score["target_country"])
    measurement_card = None
    measurement_card_error = None
    s_gpr_now = s_gpr_prev = s_gpr_pctile = 0.0
    ladder_state = ladder_prev_state = days_in_state = 0
    jump_pctile = 0.0
    # True CHI SAU KHI ladder_state/days_in_state duoc tinh xong thanh cong —
    # phan biet "ladder_state=0 vi that su S0" voi "ladder_state=0 vi tinh
    # hong (vd role la)". process_news_item_live doc co nay de KHONG ghi de
    # mot trang thai dung truoc do trong DB bang so 0 gia (xem store.py).
    ladder_computed = False

    if pair_identified:
        try:
            pair = pair_key(score["actor_country"], score["target_country"])
            history = history_provider(pair)
            indicators, s_gpr_series = _pair_indicator_frame(
                history, score, jump_series, s_gpr_window, min_periods, role_weights)

            s_gpr_now = float(s_gpr_series.loc[as_of]) if as_of in s_gpr_series.index else 0.0
            prior = s_gpr_series.loc[:as_of]
            s_gpr_prev = float(prior.iloc[-2]) if len(prior) >= 2 else 0.0
            s_gpr_pctile = float(indicators["s_gpr_pair_pct"].loc[as_of]) \
                if as_of in indicators.index and pd.notna(indicators["s_gpr_pair_pct"].loc[as_of]) else 0.0
            jump_pctile = float(indicators["jump_pct"].loc[as_of]) \
                if as_of in indicators.index and pd.notna(indicators["jump_pct"].loc[as_of]) else 0.0

            cfg = ladder_config or load_ladder_config(DEFAULT_LADDER_CONFIG)
            ladder_df = classify_ladder(indicators, cfg)
            if as_of in ladder_df.index:
                ladder_state = int(ladder_df["state"].loc[as_of])
                days_in_state = int(ladder_df["days_in_state"].loc[as_of])
                prior_states = ladder_df["state"].loc[:as_of]
                ladder_prev_state = int(prior_states.iloc[-2]) if len(prior_states) >= 2 \
                    else ladder_state
            ladder_computed = True

            # w(role) dung DUNG bang da dung de tinh s_gpr_now o tren (khong
            # hard-code — CLAUDE.md #7).
            weights = role_weights or DEFAULT_ROLE_WEIGHTS_INIT
            actor_weight = weights[stmt.speaker_role]
            event = {"headline": score["rationale"], "source": stmt.source,
                     "url": stmt.url or "—", "actor": score["actor_country"],
                     "target": score["target_country"], "channel": score["channel"] or "—",
                     "commitment": score["commitment"], "role": stmt.speaker_role}
            payload = MeasurementPayload(
                v=score["v"], specificity=score["specificity"], actor_weight=actor_weight,
                s_gpr_now=s_gpr_now, s_gpr_prev=s_gpr_prev, s_gpr_pctile=s_gpr_pctile,
                jump=jump_val, jump_pctile=jump_pctile, ladder_state=ladder_state,
                ladder_prev_state=ladder_prev_state, days_in_state=max(days_in_state, 1),
                detection_seconds=detection_seconds if detection_seconds is not None
                else int((generated_at - _as_utc(stmt.published_at).to_pydatetime())
                        .total_seconds()))
            card_meta = {"published_at": stmt.published_at.isoformat(),
                        "model_version": config.model_version,
                        "rubric_version": config.rubric_version}
            measurement_card = compose_measurement_card(event, payload, card_meta)
        except KeyError as e:
            # speaker_role (cua tin nay HOAC cua mot ban ghi lich su cung cap)
            # khong co trong w(role) — KHONG duoc am tham gan trong so ngam
            # (#7), nhung cung KHONG duoc de mot vai tro la lam mat ca tin:
            # suy giam co kiem soat, S-GPR/Ladder bo qua, gamma/VN note van phat.
            measurement_card_error = (
                f"Vai trò phát ngôn không nhận diện được trong bảng trọng số "
                f"w(role): {e} — bỏ qua S-GPR/Ladder cho tin này.")
        except (GuardViolation, ClaimCeilingViolation) as e:
            # `rationale` cua LLM co the chua so khong khop payload (vd "25%")
            # — Guard P1 CHAN dung theo thiet ke, khong phai loi. Suy giam co
            # kiem soat: macro_brief/vn_note van phat, card ghi ro ly do vang
            # mat thay vi lam sap ca pipeline vi mot dong rationale.
            measurement_card_error = str(e)

    return NewsAssessment(
        stmt=stmt, score=score, pair_identified=pair_identified,
        gamma_channel=gamma_channel, transmission_channel=transmission_channel,
        s_gpr_now=s_gpr_now, s_gpr_prev=s_gpr_prev, s_gpr_pctile=s_gpr_pctile,
        ladder_state=ladder_state, ladder_prev_state=ladder_prev_state,
        days_in_state=days_in_state, ladder_computed=ladder_computed,
        jump=jump_val, jump_pctile=jump_pctile,
        chain_a_last_available=chain_a_last_available, chain_a_stale=chain_a_stale,
        measurement_card=measurement_card, measurement_card_error=measurement_card_error,
        macro_brief=macro_brief, vn_note=vn_note_text, gamma_data_version=gamma_file,
        generated_at=generated_at)


def process_news_item_live(
    stmt: Statement,
    dsn: str,
    llm: LLMClient,
    config: ScorerConfig,
    encoder: EncoderFn | None = None,
    gamma_reports_dir: str = "docs/reports",
    ladder_config_path: str = str(DEFAULT_LADDER_CONFIG),
    chain_a_stale_after_days: int = DEFAULT_CHAIN_A_STALE_AFTER_DAYS,
) -> NewsAssessment | ExcludedResult:
    """Wrapper production: noi Postgres + file gamma that vao `process_news_item`.

    Nap lazy de import module nay khong ep phai co sqlalchemy/psycopg2 luc test
    (fakes trong test khong dung ham nay).
    """
    from pathlib import Path

    from ..service import store
    from .gamma_lookup import load_published_gamma

    engine = store.get_engine(dsn)
    ladder_cfg = load_ladder_config(ladder_config_path)

    def history_provider(pair: str) -> pd.DataFrame:
        return store.load_pair_history(engine, pair, before=_as_utc(stmt.published_at))

    def jump_series_provider(as_of: pd.Timestamp) -> pd.Series:
        return store.load_jump_series(engine, as_of)

    def gamma_loader(channel: str):
        return load_published_gamma(channel, outcomes=MACRO_OUTCOMES,
                                    reports_dir=Path(gamma_reports_dir))

    result = process_news_item(
        stmt, llm, config, history_provider, jump_series_provider, gamma_loader,
        encoder=encoder, ladder_config=ladder_cfg,
        chain_a_stale_after_days=chain_a_stale_after_days)

    statement_id = store.insert_statement(engine, stmt)
    if isinstance(result, ExcludedResult):
        return result
    store.insert_statement_score(engine, statement_id, result.score)
    # CHI ghi khi ladder THAT SU tinh duoc (xem NewsAssessment.ladder_computed).
    # Ghi vo dieu kien tren pair_identified se ghi de mot trang thai DUNG cua
    # ngay hom do bang 0/S0 GIA khi lan xu ly nay hong (vd role la — #7).
    if result.pair_identified and result.ladder_computed:
        pair = pair_key(result.score["actor_country"], result.score["target_country"])
        store.upsert_ladder_state(engine, pair, _as_utc(stmt.published_at).normalize().date(),
                                  result.ladder_state, result.days_in_state,
                                  ladder_cfg.version)
    store.insert_news_assessment(engine, statement_id, result)
    return result
