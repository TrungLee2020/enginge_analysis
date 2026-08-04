"""statement_scorer.py — TANG 2 do luong (chan B): encoder loc -> LLM cham. 🏭 production-path

Spec: docs/00 §2.3 (rubric ±1.0) + §2.4 (prompt) · docs/11 §7 (pipeline 2 tang
ECB LGPT) · docs/14 §3.1 (quy tac contamination) · docs/15 §0 (phan cong).

PHAN CONG (docs/15 §0 — vi pham la loi thiet ke, khong phai loi style):
    LLM chi DO LUONG: v, commitment, specificity, channel, target. Moi con so
    thi truong/vi mo den tu cong thuc (γ table, analogue) — LLM KHONG sinh so,
    KHONG cham gate, KHONG chon spec. Schema JSON o day co dinh nghia truong;
    truong la — parse loi, khong nhan.

PIPELINE 2 TANG (ECB LGPT, docs/11 §7):
    encoder loc truoc (p(geopolitical) >= ~0.6) -> moi dua LLM cham. Dung rieng
    model lon cho tat ca thi giam false negative nhung chi phi + do tre thanh
    nut that. Encoder la callable tiem vao (fine-tuned encoder that o Phase 2;
    test dung fake) — module nay KHONG tu train encoder.

CONTAMINATION (docs/14 §3.1 — bat buoc):
    1. Prompt ghi tuong minh: cham VAN BAN phat ngon, khong cham hau qua;
       khong tham chieu su kien sau published_at.
    2. `training_cutoff` cua model cham la THAM SO BAT BUOC — vao metadata moi
       bang diem (§3.1.4). Moi claim du bao chan B chi kiem tren du lieu SAU
       cutoff nay; backfill truoc cutoff tran claim = measurement/association.

VERSIONING (CLAUDE.md #4 + docs/11 §7):
    model_version + rubric_version + prompt_version + temperature co dinh +
    cache theo hash noi dung. Thieu mot cai la data_version cua report mat
    nghia vi mot nua pipeline khong xac dinh.

`published_at` chinh xac den PHUT voi nguon daily (CLAUDE.md #5) — guard o
`Statement`: nguon cadence="daily" ma timestamp dung 00:00:00 gan nhu chac chan
la cot DATE bi ep kieu, raise thay vi de event-study sau nay sai lech ca ngay.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Callable, Iterable, MutableMapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

RUBRIC_VERSION = "r1"      # bang neo docs/00 §2.3 — doi bang neo thi bump
PROMPT_VERSION = "p1"      # docs/00 §2.4 + quy tac contamination docs/14 §3.1.1
DEFAULT_TEMPERATURE = 0.1  # ECB LGPT (docs/11 §7): giam phuong sai, tai lap duoc
DEFAULT_ENCODER_THRESHOLD = 0.6

# Taxonomy CHAM DIEM — theo docs/00 §2.4 (nguon chan ly khi mau thuan).
# ⚠️ docs/14 §1.1 va docs/15 tang 2 noi "taxonomy 4 kenh" {energy, trade,
# financial, military} (kenh TRUYEN DAN cua bang γ). Hai taxonomy KHONG trung:
# sanction/diplomacy/tech chua co cho trong 4 kenh. Mapping 6->4 la quyet dinh
# thiet ke dang MO — xem CHANNEL_TO_TRANSMISSION ben duoi, KHONG tu bia.
SCORING_CHANNELS = ("trade", "military", "sanction", "diplomacy", "energy", "tech")
COMMITMENTS = ("rhetoric", "conditional", "announced_action")

# Mapping sang kenh truyen dan (bang γ). Chi ghi cac cap HIEN NHIEN; sanction/
# diplomacy/tech -> None cho toi khi user chot (docs/15 §6.3). Tra None nghia la
# "phat ngon nay chua tra duoc vao cot kenh cua bang γ" — dung im lang nhet bua.
TRANSMISSION_CHANNELS = ("energy", "trade", "financial", "military")
CHANNEL_TO_TRANSMISSION: dict[str, str] = {
    "trade": "trade", "energy": "energy", "military": "military",
}

_SCORE_KEYS = frozenset({
    "v", "actor_country", "target_country", "channel",
    "commitment", "specificity", "rationale",
})

# Bang neo rubric (docs/00 §2.3) nhung vao prompt — SUA O DOC TRUOC roi moi sua
# day va bump RUBRIC_VERSION, khong sua nguoc.
_RUBRIC_ANCHORS = """\
| v range      | level                        | description / example |
|--------------|------------------------------|-----------------------|
| -1.0 .. -0.6 | strong conciliation          | signing, concession, lifting sanctions ("agreed to lift tariffs") |
| -0.5 .. -0.1 | de-escalation                | offer to negotiate, positive language ("constructive dialogue") |
|  0           | neutral                      | procedural, no bearing on the relationship |
| +0.1 .. +0.3 | grievance                    | complaint, concern, summoning ambassador ("expressed deep concern") |
| +0.4 .. +0.6 | warning / conditional threat | "will impose tariffs if", threatened but not enacted |
| +0.7 .. +0.8 | ultimatum / military threat  | explicit deadline, threat of force ("all options on the table" + deadline) |
| +0.9 .. +1.0 | announced action             | enacted: tariffs effective, mobilisation, blockade ("effective immediately") |"""

SYSTEM_PROMPT = f"""\
You are scoring official statements for geopolitical escalation intensity.
Input: one official statement (speech excerpt, press release, or post),
with metadata: {{source, date, speaker, speaker_role}}.

Score v in [-1.0, +1.0]:
  negative = de-escalatory/conciliatory, 0 = neutral/procedural,
  positive = escalatory. Use the anchor scale:

{_RUBRIC_ANCHORS}

Rules:
- Score the STATEMENT's content, not the underlying situation.
- Score the statement's TEXT only, never its consequences. Do not use any
  knowledge of events after the statement's date; do not let known outcomes
  influence the score.
- A specific threat with conditions/deadlines scores higher than vague bluster.
- Reporting/quoting another party's threat is NOT the speaker escalating.
- Historical commemoration, condolences, culture/sports -> v = 0.
Return strict JSON, exactly these keys and nothing else:
{{"v": float, "actor_country": ISO3|null, "target_country": ISO3|null,
 "channel": "trade|military|sanction|diplomacy|energy|tech"|null,
 "commitment": "rhetoric|conditional|announced_action",
 "specificity": float, "rationale": "<= 25 words"}}"""


class ScoreParseError(ValueError):
    """Output LLM khong dat contract JSON strict — khong nhan, khong sua ho."""


@dataclass(frozen=True)
class Statement:
    """Mot phat ngon dau vao (khop bang `statements`, docs/00 §6).

    cadence: "daily" (B3-B8 — realtime, published_at phai den PHUT, #5) |
             "slow" (B1 UNGDC annual, B2 BIS — chi can ngay).
    midnight_ok: nguon daily co timestamp 00:00 THAT (hiem) phai bat co nay
        tuong minh — mac dinh coi 00:00:00 la cot date bi ep kieu va raise.
    """
    source: str
    published_at: pd.Timestamp
    speaker: str
    speaker_role: str
    text: str
    speaker_country: str | None = None
    url: str | None = None
    lang: str = "en"
    cadence: str = "daily"
    midnight_ok: bool = False

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("Statement.text rong — khong co gi de cham.")
        ts = pd.Timestamp(self.published_at)
        if pd.isna(ts):
            raise ValueError("published_at la NaT — bat buoc co (CLAUDE.md #5).")
        object.__setattr__(self, "published_at", ts)
        if self.cadence not in ("daily", "slow"):
            raise ValueError(f"cadence phai 'daily'|'slow', nhan {self.cadence!r}")
        if (self.cadence == "daily" and not self.midnight_ok
                and ts == ts.normalize()):
            raise ValueError(
                f"published_at={ts} dung 00:00:00 voi nguon daily {self.source!r} — "
                "gan nhu chac chan la cot DATE bi ep kieu, khong phai timestamp phut "
                "(CLAUDE.md #5: nguon realtime khong bao gio chi luu ngay). Neu dung "
                "la nua dem that, dat midnight_ok=True mot cach CO CHU DICH.")


def build_messages(stmt: Statement) -> list[dict[str, str]]:
    """Prompt 2 message: system = rubric + rules; user = metadata + van ban."""
    meta = {
        "source": stmt.source,
        "date": stmt.published_at.isoformat(),
        "speaker": stmt.speaker,
        "speaker_role": stmt.speaker_role,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"metadata: {json.dumps(meta, ensure_ascii=False)}\n"
                    f"statement:\n{stmt.text}"},
    ]


def content_hash(stmt: Statement, model_version: str,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
    """Khoa cache: van ban + metadata vao prompt + moi truc version.

    Doi bat ky truc nao (rubric/prompt/model/temperature) la diem cu VO HIEU —
    hash doi nen khong bao gio doc nham diem cua spec khac (docs/11 §7).
    """
    h = hashlib.sha256()
    for part in (RUBRIC_VERSION, PROMPT_VERSION, model_version,
                 f"{temperature:.3f}", stmt.source, stmt.speaker,
                 stmt.speaker_role, stmt.text):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def _iso3_or_none(val: Any, key: str) -> str | None:
    if val is None:
        return None
    if isinstance(val, str) and len(val) == 3 and val.isalpha():
        return val.upper()
    raise ScoreParseError(f"{key}={val!r} khong phai ISO3 hoac null.")


def parse_score(raw: str) -> dict[str, Any]:
    """Parse + validate output LLM theo contract JSON STRICT (docs/00 §2.4).

    Strict nghia la: dung du 7 key, khong thua khong thieu; moi truong dung
    kieu/mien. Sai o dau raise ScoreParseError o do — KHONG sua ho, KHONG
    clip ve mien hop le (clip la LLM sinh so ngoai rubric ma minh hop thuc hoa).
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ScoreParseError(f"Khong phai JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ScoreParseError(f"Phai la object JSON, nhan {type(obj).__name__}.")
    keys = set(obj)
    if keys != _SCORE_KEYS:
        raise ScoreParseError(
            f"Sai bo key: thieu {sorted(_SCORE_KEYS - keys)}, "
            f"thua {sorted(keys - _SCORE_KEYS)}.")

    v = obj["v"]
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not -1.0 <= v <= 1.0:
        raise ScoreParseError(f"v={v!r} ngoai [-1, 1] hoac khong phai so.")
    spec = obj["specificity"]
    if (not isinstance(spec, (int, float)) or isinstance(spec, bool)
            or not 0.0 <= spec <= 1.0):
        raise ScoreParseError(f"specificity={spec!r} ngoai [0, 1].")
    if obj["channel"] is not None and obj["channel"] not in SCORING_CHANNELS:
        raise ScoreParseError(
            f"channel={obj['channel']!r} khong thuoc {SCORING_CHANNELS} | null.")
    if obj["commitment"] not in COMMITMENTS:
        raise ScoreParseError(
            f"commitment={obj['commitment']!r} khong thuoc {COMMITMENTS}.")
    if not isinstance(obj["rationale"], str):
        raise ScoreParseError("rationale phai la chuoi.")
    return {
        "v": float(v),
        "actor_country": _iso3_or_none(obj["actor_country"], "actor_country"),
        "target_country": _iso3_or_none(obj["target_country"], "target_country"),
        "channel": obj["channel"],
        "commitment": obj["commitment"],
        "specificity": float(spec),
        "rationale": obj["rationale"],
    }


def to_transmission_channel(channel: str | None) -> str | None:
    """Kenh cham diem (6 gia tri, docs/00) -> kenh truyen dan bang γ (4 gia tri).

    sanction/diplomacy/tech tra None — mapping chua chot (docs/15 §6.3), tra
    None de nguoi dung thay khoang trong thay vi bi nhet bua vao mot kenh.
    """
    if channel is None:
        return None
    if channel not in SCORING_CHANNELS:
        raise ValueError(f"channel={channel!r} khong thuoc {SCORING_CHANNELS}")
    return CHANNEL_TO_TRANSMISSION.get(channel)


@dataclass(frozen=True)
class ScorerConfig:
    """Truc versioning cua mot dot cham — moi truong deu vao bang diem.

    training_cutoff BAT BUOC (docs/14 §3.1.4): moi claim du bao chan B chi kiem
    duoc tren du lieu SAU moc nay; thieu no thi bang diem khong phan biet duoc
    dau la backfill nhiem hindsight.
    """
    model_version: str
    training_cutoff: dt.date
    temperature: float = DEFAULT_TEMPERATURE
    rubric_version: str = RUBRIC_VERSION
    prompt_version: str = PROMPT_VERSION


# LLM client: (messages, temperature) -> chuoi JSON. Tiem vao de test khong can
# mang; production dung openai_chat_client() ben duoi.
LLMClient = Callable[[list[dict[str, str]], float], str]
# Encoder loc: text -> p(geopolitical) trong [0,1].
EncoderFn = Callable[[str], float]


def score_statement(
    stmt: Statement,
    llm: LLMClient,
    config: ScorerConfig,
    encoder: EncoderFn | None = None,
    encoder_threshold: float = DEFAULT_ENCODER_THRESHOLD,
    cache: MutableMapping[str, dict] | None = None,
    max_retries: int = 1,
) -> dict[str, Any] | None:
    """Cham MOT phat ngon. Tra None neu encoder loc rot (duoi threshold).

    Retry: output hong contract thi gui lai KEM thong bao loi toi da
    `max_retries` lan (JSON strict la contract, khong phai hy vong); van hong
    thi raise ScoreParseError — de caller ghi nhan that bai, khong nhet diem bia.
    """
    encoder_p = None
    if encoder is not None:
        encoder_p = float(encoder(stmt.text))
        if encoder_p < encoder_threshold:
            return None

    key = content_hash(stmt, config.model_version, config.temperature)
    if cache is not None and key in cache:
        parsed = dict(cache[key])
    else:
        messages = build_messages(stmt)
        last_err: ScoreParseError | None = None
        parsed = None
        for _ in range(1 + max_retries):
            raw = llm(messages, config.temperature)
            try:
                parsed = parse_score(raw)
                break
            except ScoreParseError as e:
                last_err = e
                messages = [*messages,
                            {"role": "assistant", "content": raw},
                            {"role": "user",
                             "content": f"Invalid output: {e}. Return ONLY the "
                                        "strict JSON object specified."}]
        if parsed is None:
            raise ScoreParseError(
                f"Sau {1 + max_retries} lan van hong contract: {last_err}")
        if cache is not None:
            cache[key] = dict(parsed)

    # actor tu METADATA nguon khi co (docs/00 §2.1 — gia tri (2) cua chan B:
    # actor biet chac tu nguon, khong doan); LLM chi la fallback.
    actor = stmt.speaker_country or parsed["actor_country"]
    return {
        "published_at": stmt.published_at,
        "source": stmt.source,
        "speaker": stmt.speaker,
        "speaker_role": stmt.speaker_role,
        "actor_country": actor,
        "actor_country_llm": parsed["actor_country"],
        "target_country": parsed["target_country"],
        "v": parsed["v"],
        "channel": parsed["channel"],
        "commitment": parsed["commitment"],
        "specificity": parsed["specificity"],
        "rationale": parsed["rationale"],
        "encoder_p": encoder_p,
        "model_version": config.model_version,
        "rubric_version": config.rubric_version,
        "prompt_version": config.prompt_version,
        "temperature": config.temperature,
        "training_cutoff": config.training_cutoff,
        "content_hash": key,
    }


SCORE_COLUMNS = [
    "published_at", "source", "speaker", "speaker_role",
    "actor_country", "actor_country_llm", "target_country",
    "v", "channel", "commitment", "specificity", "rationale", "encoder_p",
    "model_version", "rubric_version", "prompt_version", "temperature",
    "training_cutoff", "content_hash",
]


def score_statements(
    stmts: Iterable[Statement],
    llm: LLMClient,
    config: ScorerConfig,
    encoder: EncoderFn | None = None,
    encoder_threshold: float = DEFAULT_ENCODER_THRESHOLD,
    cache: MutableMapping[str, dict] | None = None,
    max_retries: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cham mot lo phat ngon -> (bang diem, bang bi loai).

    Bang diem khop schema `statement_scores` (docs/00 §6) + truc versioning.
    Bang bi loai ghi RO ly do (encoder_filtered | parse_error) — mot phat ngon
    roi khoi mau la mot su kien phai truy duoc, khong bien mat im lang.
    """
    rows: list[dict] = []
    dropped: list[dict] = []
    for stmt in stmts:
        try:
            row = score_statement(stmt, llm, config, encoder, encoder_threshold,
                                  cache, max_retries)
        except ScoreParseError as e:
            dropped.append({"published_at": stmt.published_at,
                            "source": stmt.source, "speaker": stmt.speaker,
                            "reason": "parse_error", "detail": str(e)})
            continue
        if row is None:
            dropped.append({"published_at": stmt.published_at,
                            "source": stmt.source, "speaker": stmt.speaker,
                            "reason": "encoder_filtered", "detail": None})
            continue
        rows.append(row)

    scored = pd.DataFrame(rows, columns=SCORE_COLUMNS)
    drop_df = pd.DataFrame(
        dropped, columns=["published_at", "source", "speaker", "reason", "detail"])
    return scored, drop_df


def openai_chat_client(model: str = "gpt-4o-mini") -> LLMClient:
    """LLMClient dua tren OpenAI SDK (GPT-4o-mini cho backfill, CLAUDE.md stack).

    Import luoi de test/offline khong can package. JSON mode cua API chi ep
    "la JSON" — contract strict van do parse_score giu.
    """
    from openai import OpenAI
    client = OpenAI()

    def _call(messages: list[dict[str, str]], temperature: float) -> str:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            response_format={"type": "json_object"})
        return resp.choices[0].message.content or ""

    return _call
