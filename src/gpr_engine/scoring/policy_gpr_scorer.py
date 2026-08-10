"""policy_gpr_scorer.py — do DO HIEN DIEN cua rui ro dia chinh tri trong van ban Fed.

🔬 research. Chua noi vao duong production nao (CLAUDE.md #1: chua qua cong kiem
dinh thi khong vao service).

CAU HOI NO TRA LOI — va cau hoi no KHONG tra loi:
    TRA LOI: trong mot van ban chinh sach (FOMC statement/minutes), rui ro dia
      chinh tri xuat hien o muc do nao, qua kenh nao, va co duoc trinh bay nhu
      mot yeu to ANH HUONG toi quyet dinh hay chi duoc nhac qua.
    KHONG tra loi: Fed hawkish hay dovish. Do la truc KHAC, va voi My no da co
      ban do sach hon tu gia phai sinh quanh cua so FOMC (xem docstring
      `ingest/fomc.py`). Cham hawkish/dovish bang LLM o day la dung sai module.

VI SAO RUBRIC RIENG, KHONG DUNG LAI `statement_scorer` (±1.0 leo thang):
    `docs/17` §4.6 ghi thang: khoi chinh sach phai co rubric RIENG, khong dung
    lai thang leo thang. Hai construct khac han nhau —
      ±1.0 leo thang do MOT BEN LAM GI (de doa/nhuong bo) — chu the la nguoi
        phat ngon, va dau cua diem la huong hanh dong cua chinh ho;
      rubric o day do MOT VAN BAN NOI VE rui ro cua BEN THU BA nhu mot dieu
        kien ngoai canh — Fed khong "leo thang", Fed mo ta.
    Ep chung mot thang se cho ra so co ve doc duoc nhung khong co nghia
    (Fed noi "cang thang Trung Dong lam tang gia nang luong" KHONG phai Fed leo
    thang muc +0.6).

TRAN CLAIM: `measurement`. Module nay mo ta VAN BAN NOI GI. Noi "GPR anh huong
    quyet dinh cua Fed" la buoc len muc `association` va can hoi quy, khong phai
    can them mot truong JSON.

KENH: dung dung 4 kenh TRUYEN DAN cua bang γ (energy/trade/financial/military)
    chu khong phai 6 kenh cham diem cua docs/00. Ly do: dau ra cua module nay de
    doi chieu voi bang γ tang 2 — tra ve mot taxonomy roi phai map 6->4 (mapping
    do dang MO, `docs/15` §6.3) la tu tao them mot buoc mo ho khong can thiet.

CONTAMINATION + VERSIONING: cung hop dong voi `statement_scorer` —
    `training_cutoff` bat buoc, prompt cam dung kien thuc sau ngay cong bo,
    cache theo hash phu MOI truc version.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

# pg2 (2026-08-09): them loai tru THIEN TAI. Do tren ket qua that cua pg1 —
# 2/134 van ban co salience>0 la thien tai bi cham thanh dia chinh tri
# ("Hurricane Rita caused further disruption to energy production", sal 0.39;
# "Gasoline prices rose in the aftermath of the hurricanes", sal 0.40). Model
# neo vao "gian doan nguon cung nang luong" roi suy ra dia chinh tri — dung kieu
# lech ma `docs/17` §5 da ghi ("cham cao o day, hay nham thu khac thanh GPR").
# ⚠️ Bump version lam TOAN BO cache pg1 vo hieu (content_hash phu ca hai truc) —
# do la CO Y: diem cham bang prompt khac khong duoc tron vao mot chuoi.
RUBRIC_VERSION = "pg2"
PROMPT_VERSION = "pg2"
DEFAULT_TEMPERATURE = 0.1

# Trung khop `statement_scorer.TRANSMISSION_CHANNELS` — xem docstring module.
CHANNELS = ("energy", "trade", "financial", "military")
DIRECTIONS = ("risk_up", "risk_down", "neutral")

_KEYS = frozenset({"gpr_salience", "channel", "direction", "binding",
                   "evidence", "rationale"})

_SALIENCE_ANCHORS = """\
| gpr_salience | meaning |
|--------------|---------|
| 0.0          | no geopolitical content at all |
| 0.1 .. 0.3   | passing mention in a list of risks, no elaboration |
| 0.4 .. 0.6   | a discussed factor: at least one sentence explaining a channel |
| 0.7 .. 0.9   | a prominent theme: repeated, tied to the outlook or to specific prices |
| 1.0          | central: the document frames the decision mainly around it |"""

SYSTEM_PROMPT = f"""\
You are measuring how present GEOPOLITICAL RISK is in a central-bank policy
document (FOMC statement or minutes).

Geopolitical risk means: war, military conflict or threat of it, terrorism,
sanctions, blockades or shipping-route disruption, and inter-state political
tension. It does NOT include: ordinary domestic politics, fiscal debates,
debt-ceiling episodes, elections, regulation, or purely economic uncertainty.
It does NOT include NATURAL events either — hurricanes, earthquakes, floods,
storms, droughts, wildfires, pandemics — even when they disrupt energy supply
or raise oil prices. A supply disruption is geopolitical only if its cause is
a state, an armed group, or a political decision.

Score gpr_salience in [0, 1] using these anchors:

{_SALIENCE_ANCHORS}

Rules:
- Measure what the TEXT says. Do not judge whether the risk is real or
  whether the policy decision was right.
- Use no knowledge of events after the document's date. Do not let known
  outcomes affect the score.
- `binding` is true ONLY if the text presents geopolitical risk as bearing on
  the decision or the outlook (e.g. it enters the risk assessment). A mention
  in a background list is not binding.
- `channel` = the transmission channel the text actually describes, or null if
  none is described. Do not infer a channel the text does not mention.
- `evidence` must be a VERBATIM quote from the document, <= 25 words. If
  gpr_salience is 0, use an empty string.
Return strict JSON, exactly these keys and nothing else:
{{"gpr_salience": float, "channel": "energy|trade|financial|military"|null,
 "direction": "risk_up|risk_down|neutral", "binding": bool,
 "evidence": "<= 25 words, verbatim", "rationale": "<= 25 words"}}"""


class ScoreParseError(ValueError):
    """Output LLM khong dat contract JSON strict — khong nhan, khong sua ho."""


@dataclass(frozen=True)
class PolicyScorerConfig:
    model_version: str
    training_cutoff: dt.date
    temperature: float = DEFAULT_TEMPERATURE
    rubric_version: str = RUBRIC_VERSION
    prompt_version: str = PROMPT_VERSION


# Cung chu ky voi `statement_scorer.LLMClient` — CO Y, de dung lai
# `statement_scorer.openai_chat_client(model, base_url, api_key)` cho ca hai
# scorer thay vi viet client thu hai. Client do chay voi BAT KY endpoint tuong
# thich OpenAI, ke ca vLLM tu host:
#     from gpr_engine.scoring.statement_scorer import openai_chat_client
#     llm = openai_chat_client(model="Qwen/Qwen3-14B",
#                              base_url="http://<vllm-host>:8000/v1",
#                              api_key="dummy")   # vLLM bo qua, SDK van doi co
# ⚠️ Client do dat `response_format={"type":"json_object"}`. vLLM chi ho tro cai
# nay khi bat guided decoding; ban khong bat se bao loi ngay o request dau —
# do la loi CAU HINH, khong phai loi contract, dung sua bang cach noi long parse.
LLMClient = Callable[[list[dict[str, str]], float], str]


def split_document(text: str, max_chars: int = 12000) -> list[str]:
    """Chia van ban dai thanh cac doan <= max_chars, cat o ranh gioi cau.

    VI SAO CHIA CHU KHONG CAT: minutes dai 36.000-46.000 ky tu (do that
    2026-08-09). Cat lay 12.000 ky tu dau la bo ~2/3 van ban, va phan bi bo
    KHONG ngau nhien — muc "Staff Review" va "Participants' Views" (noi ban ve
    rui ro) nam o GIUA/CUOI, con phan dau la thu tuc. Cat se lam salience cua
    minutes tut xuong mot cach HE THONG, tuc do sai lech theo loai van ban.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + 1 + len(sent) > max_chars:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip() if cur else sent
        while len(cur) > max_chars:          # mot "cau" dai bat thuong
            parts.append(cur[:max_chars])
            cur = cur[max_chars:]
    if cur:
        parts.append(cur)
    return parts


def build_messages(doc, max_chars: int = 12000, chunk: str | None = None,
                   chunk_index: int = 0, n_chunks: int = 1) -> list[dict[str, str]]:
    """Prompt 2 message cho MOT doan. `doc` la `ingest.fomc.FomcDocument`.

    `chunk=None` -> dung doan dau tien cua `split_document`. Metadata ghi ro
    dang cham doan may / tong bao nhieu, de LLM khong coi mot doan giua la ca
    van ban.
    """
    text = chunk if chunk is not None else split_document(doc.text, max_chars)[0]
    meta = {
        "doc_type": doc.doc_type,
        "date": pd.Timestamp(doc.published_at).isoformat(),
        "title": doc.title,
        "chunk": f"{chunk_index + 1}/{n_chunks}",
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"metadata: {json.dumps(meta, ensure_ascii=False)}\n"
                    f"document:\n{text}"},
    ]


def content_hash(doc, model_version: str,
                 temperature: float = DEFAULT_TEMPERATURE,
                 chunk: str | None = None) -> str:
    """Khoa cache: noi dung doan + moi truc version. Doi truc nao -> diem cu VO HIEU."""
    h = hashlib.sha256()
    for part in (RUBRIC_VERSION, PROMPT_VERSION, model_version,
                 f"{temperature:.3f}", doc.doc_type,
                 doc.text if chunk is None else chunk):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def parse_score(raw: str) -> dict[str, Any]:
    """Parse + validate STRICT. Sai o dau raise o do — KHONG clip, KHONG sua ho."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ScoreParseError(f"Khong phai JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ScoreParseError(f"Phai la object JSON, nhan {type(obj).__name__}.")
    keys = set(obj)
    if keys != _KEYS:
        raise ScoreParseError(
            f"Sai bo key: thieu {sorted(_KEYS - keys)}, thua {sorted(keys - _KEYS)}.")

    sal = obj["gpr_salience"]
    if (not isinstance(sal, (int, float)) or isinstance(sal, bool)
            or not 0.0 <= sal <= 1.0):
        raise ScoreParseError(f"gpr_salience={sal!r} ngoai [0, 1] hoac khong phai so.")
    if obj["channel"] is not None and obj["channel"] not in CHANNELS:
        raise ScoreParseError(f"channel={obj['channel']!r} khong thuoc {CHANNELS} | null.")
    if obj["direction"] not in DIRECTIONS:
        raise ScoreParseError(f"direction={obj['direction']!r} khong thuoc {DIRECTIONS}.")
    if not isinstance(obj["binding"], bool):
        raise ScoreParseError("binding phai la bool.")
    for k in ("evidence", "rationale"):
        if not isinstance(obj[k], str):
            raise ScoreParseError(f"{k} phai la chuoi.")

    # Rang buoc NOI TAI cua rubric: khong co noi dung dia chinh tri thi khong the
    # vua "khong co" vua "co kenh/binding". LLM tra bo truong tu mau thuan la dau
    # hieu no dang doan chu khong doc — bat o day thay vi de vao bang diem.
    if sal == 0.0 and (obj["channel"] is not None or obj["binding"]):
        raise ScoreParseError(
            "gpr_salience=0 nhung van co channel/binding — bo truong tu mau thuan.")
    if obj["binding"] and sal < 0.1:
        raise ScoreParseError(
            f"binding=true nhung gpr_salience={sal} gan 0 — tu mau thuan.")
    return {
        "gpr_salience": float(sal),
        "channel": obj["channel"],
        "direction": obj["direction"],
        "binding": bool(obj["binding"]),
        "evidence": obj["evidence"],
        "rationale": obj["rationale"],
    }


def _normalise(s: str) -> str:
    """Chuan hoa de doi chieu trich dan: dau nhay cong, khoang trang, hoa/thuong."""
    s = s.replace("‘", "'").replace("’", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_evidence(evidence: str, source_text: str,
                    partial_ratio: float = 0.5) -> str:
    """`evidence` co THAT SU nam trong van ban goc khong. MAY kiem, khong can nguoi.

    Rubric bat trich NGUYEN VAN, nen day la cong chong BIA chay duoc hoan toan tu
    dong — khac han viec do noi dung (do thi phai de LLM, vi anh huong dia chinh
    tri KHONG doi hoi van ban chua tu khoa nao).

    Do tren ket qua that pg1 (403 van ban, 134 co evidence): 92,5% khop nguyen
    van, 0,7% khop mot phan, **6,7% KHONG khop** — tuc ty le bia do duoc, khong
    phai lo xa.

    Tra: "exact" | "partial" | "missing" | "empty".
    """
    ev = _normalise(evidence or "")
    if not ev:
        return "empty"
    src = _normalise(source_text or "")
    if ev in src:
        return "exact"
    head = ev[: max(1, int(len(ev) * partial_ratio))]
    return "partial" if len(ev) > 20 and head in src else "missing"


# --- Cong thu hai: LLM tham dinh, KHONG phai nguoi cham tay ------------------
JUDGE_PROMPT = """\
You are auditing another model's measurement of a central-bank policy document.

You are given: the document, and a proposed measurement of how present
GEOPOLITICAL RISK is in it (gpr_salience in [0,1], plus channel/direction/
binding and a supporting quote).

Judge the MEASUREMENT, not the policy. Ask:
- Is the salience level defensible given what the document actually says?
- Does the supporting quote come from this document and support the claim?
- Is `binding` justified (the text ties geopolitical risk to the decision or
  the outlook), or was it asserted?
- Was something NON-geopolitical counted as geopolitical? Natural events
  (hurricanes, earthquakes, pandemics), domestic politics, fiscal debates and
  ordinary economic uncertainty are NOT geopolitical risk. A supply disruption
  counts only if a state, an armed group, or a political decision caused it.

Geopolitical influence does NOT require any particular keyword: a document can
describe the influence without naming it. Judge the substance, not vocabulary.

Return strict JSON, exactly these keys and nothing else:
{"agree": bool, "suggested_salience": float, "problem": "none|salience_too_high|
salience_too_low|quote_unsupported|binding_unjustified|not_geopolitical",
 "note": "<= 25 words"}"""

_JUDGE_KEYS = frozenset({"agree", "suggested_salience", "problem", "note"})
JUDGE_PROBLEMS = ("none", "salience_too_high", "salience_too_low",
                  "quote_unsupported", "binding_unjustified", "not_geopolitical")


def parse_judgement(raw: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ScoreParseError(f"Judge khong tra JSON: {e}") from e
    if not isinstance(obj, dict) or set(obj) != _JUDGE_KEYS:
        raise ScoreParseError(f"Judge sai bo key: {sorted(set(obj))}")
    s = obj["suggested_salience"]
    if not isinstance(s, (int, float)) or isinstance(s, bool) or not 0.0 <= s <= 1.0:
        raise ScoreParseError(f"suggested_salience={s!r} ngoai [0, 1].")
    if not isinstance(obj["agree"], bool):
        raise ScoreParseError("agree phai la bool.")
    if obj["problem"] not in JUDGE_PROBLEMS:
        raise ScoreParseError(f"problem={obj['problem']!r} khong thuoc {JUDGE_PROBLEMS}.")
    if not isinstance(obj["note"], str):
        raise ScoreParseError("note phai la chuoi.")
    return {"agree": bool(obj["agree"]), "suggested_salience": float(s),
            "problem": obj["problem"], "note": obj["note"]}


def judge_score(doc, score: dict[str, Any], llm: LLMClient,
                config: PolicyScorerConfig, max_chars: int = 12000,
                max_retries: int = 1) -> dict[str, Any]:
    """Cong THU HAI bang LLM: tham dinh mot phep do da co.

    Vi sao dung LLM chu khong phai tu khoa: anh huong dia chinh tri KHONG doi
    hoi van ban chua tu nao cu the — mot doan co the mo ta anh huong ma khong
    goi ten no. Gate bang tu khoa se bo sot dung nhung ca dang quan tam nhat.

    ⚠️ GIOI HAN PHAI DOC: hai LLM dong y voi nhau la do TIN CAY (reliability),
    KHONG phai do DUNG (validity). Chung chia se du lieu huan luyen nen chia se
    ca thien lech — lech "gian doan nang luong => dia chinh tri" (bao Rita, pg1)
    rat co the qua duoc cong nay. Dung `judge` de KHOANH VUNG can soi, dung dung
    no de tuyen bo ket qua dung.
    """
    payload = {k: score.get(k) for k in
               ("gpr_salience", "channel", "direction", "binding", "evidence")}
    text = split_document(doc.text, max_chars)[0]
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user",
         "content": f"document:\n{text}\n\nproposed measurement: "
                    f"{json.dumps(payload, ensure_ascii=False)}"},
    ]
    last_err: ScoreParseError | None = None
    for _ in range(1 + max_retries):
        raw = llm(messages, config.temperature)
        try:
            return parse_judgement(raw)
        except ScoreParseError as e:
            last_err = e
            messages = [*messages, {"role": "assistant", "content": raw},
                        {"role": "user",
                         "content": f"Invalid output: {e}. Return ONLY the JSON."}]
    raise ScoreParseError(f"Judge hong contract sau {1 + max_retries} lan: {last_err}")


def _score_chunk(doc, chunk: str, idx: int, n: int, llm: LLMClient,
                 config: PolicyScorerConfig,
                 cache: MutableMapping[str, dict] | None,
                 max_retries: int) -> dict[str, Any]:
    key = content_hash(doc, config.model_version, config.temperature, chunk)
    if cache is not None and key in cache:
        return dict(cache[key])
    messages = build_messages(doc, chunk=chunk, chunk_index=idx, n_chunks=n)
    last_err: ScoreParseError | None = None
    for _ in range(1 + max_retries):
        raw = llm(messages, config.temperature)
        try:
            parsed = parse_score(raw)
            if cache is not None:
                cache[key] = dict(parsed)
            return parsed
        except ScoreParseError as e:
            last_err = e
            messages = [*messages,
                        {"role": "assistant", "content": raw},
                        {"role": "user",
                         "content": f"Invalid output: {e}. Return ONLY the "
                                    "strict JSON object specified."}]
    raise ScoreParseError(f"Sau {1 + max_retries} lan van hong contract: {last_err}")


def aggregate_chunks(scores: list[dict[str, Any]],
                     weights: list[int]) -> dict[str, Any]:
    """Gop diem cac doan ve MOT hang cho van ban.

    `gpr_salience` = trung binh CO TRONG SO theo do dai doan — do la "do hien
      dien tren toan van ban", dung nghia rubric.
    `gpr_salience_max` = doan dam dac nhat. Giu RIENG vi hai cau hoi khac nhau:
      minutes nhac dam mot doan roi thoi se co mean thap ma max cao, va do la
      thong tin that chu khong phai nhieu.
    `binding` = BAT KY doan nao binding. Mot doan noi GPR anh huong trien vong
      la du de van ban do "co binding" — lay trung binh cua bool la vo nghia.
    channel/direction/evidence lay tu doan salience CAO NHAT: dai dien cho noi
      dung dia chinh tri chinh cua van ban, khong tron lan cac doan noi chuyen khac.
    """
    if not scores:
        raise ValueError("Khong co doan nao de gop.")
    total = float(sum(weights)) or 1.0
    mean = sum(s["gpr_salience"] * w for s, w in zip(scores, weights)) / total
    top = max(scores, key=lambda s: s["gpr_salience"])
    return {
        "gpr_salience": round(mean, 4),
        "gpr_salience_max": max(s["gpr_salience"] for s in scores),
        "channel": top["channel"],
        "direction": top["direction"],
        "binding": any(s["binding"] for s in scores),
        "evidence": top["evidence"],
        "rationale": top["rationale"],
        "n_chunks": len(scores),
    }


def score_document(
    doc,
    llm: LLMClient,
    config: PolicyScorerConfig,
    cache: MutableMapping[str, dict] | None = None,
    max_retries: int = 1,
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Cham MOT van ban (chia doan neu dai). Retry khi hong contract, het thi raise.

    Khong nuot loi: mot van ban cham that bai phai lo ra o caller, khong duoc
    thay bang diem 0 (0 la mot GIA TRI CO NGHIA trong rubric nay — "khong co noi
    dung dia chinh tri" — nen dung no lam gia tri that bai la lam hong chuoi do).
    """
    chunks = split_document(doc.text, max_chars)
    if not chunks:
        raise ValueError(f"{getattr(doc, 'doc_id', '?')}: van ban rong.")
    scores = [_score_chunk(doc, c, i, len(chunks), llm, config, cache, max_retries)
              for i, c in enumerate(chunks)]
    agg = aggregate_chunks(scores, [len(c) for c in chunks])
    return {
        "doc_id": doc.doc_id,
        "doc_type": doc.doc_type,
        "published_at": pd.Timestamp(doc.published_at),
        "url": getattr(doc, "url", None),
        "n_chars": len(doc.text),
        **agg,
        # Cong chong BIA, chay tu dong tren MOI hang — khong doi nguoi kiem.
        "evidence_check": verify_evidence(agg["evidence"], doc.text),
        "model_version": config.model_version,
        "rubric_version": config.rubric_version,
        "prompt_version": config.prompt_version,
        "temperature": config.temperature,
        "training_cutoff": config.training_cutoff,
    }
