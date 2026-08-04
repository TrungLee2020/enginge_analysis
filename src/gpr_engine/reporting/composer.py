"""composer.py — TANG 4: Measurement Card + Model Brief (M6). 🏭 production-path

Mau van ban: docs/11 §2.2 (card) va §2.3 (brief). Phan cong: docs/15 §0.

NGUYEN TAC CHI PHOI MODULE NAY — mot cau:
    Cong thuc tinh MOI con so; template rap chung lai; guard doi chieu tung so;
    LLM (neu co) chi duoc viet phan VAN XUOI va cung phai qua guard.

Vi the `compose_*` o day KHONG goi LLM. Chung sinh van ban tu payload bang
template thuan — day la ban NEN, chay duoc ngay ca khi khong co LLM, va la
"su that" ma ban LLM sau nay phai khop. Doi lai thu tu (LLM viet truoc, guard
kiem sau) thi guard chi con bat duoc so, khong bat duoc dien giai.

TRAN CLAIM THEO TANG — in tren MOI output (docs/15 §4):
    card     -> `measurement`      (do luong, KHONG du bao)
    analogue -> `association`      (event-study mo ta)
    phan phoi-> `predictive, chua xac nhan holdout`  (track thang: g0 §2)
Ham `claim_footer` sinh dong nay; khong template nao duoc bo qua no.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..econometrics.analogue import AnalogueResult, describe as describe_analogue
from ..econometrics.shock_axis import check_component_labelling
from ..pipeline.vn_exposure import VNExposure
from .guard import NarrativeBuilder

CLAIM_MEASUREMENT = "measurement"
CLAIM_ASSOCIATION = "association"
CLAIM_PREDICTIVE = "predictive, chưa xác nhận holdout"

# Tran claim theo tang — docs/15 §4. Khong tang nao duoc claim cao hon muc cua no.
# "vn_note": tang 3 VN khi CHUA co beta/theta/lambda da fit (config/params/vn.yaml
# chua co muc `fitted:`) — chi con la mo ta kenh + huong, tran = association,
# GIONG HET tran cua analogue vi cung la "trong nhung dot tuong tu, kenh nay
# thuong di theo huong nay" chu khong phai con so du bao.
TIER_CLAIM_CEILING = {
    "card": CLAIM_MEASUREMENT,
    "analogue": CLAIM_ASSOCIATION,
    "distribution": CLAIM_PREDICTIVE,
    "vn_note": CLAIM_ASSOCIATION,
}

LADDER_NAMES = {0: "S0 bình thường", 1: "S1 khẩu chiến", 2: "S2 đe dọa",
                3: "S3 chuẩn bị/động viên", 4: "S4 hành động"}


class ClaimCeilingViolation(Exception):
    """Mot tang claim cao hon tran cua no (docs/15 §4)."""


def claim_footer(tier: str) -> str:
    if tier not in TIER_CLAIM_CEILING:
        raise ValueError(f"tier={tier!r} không thuộc {tuple(TIER_CLAIM_CEILING)}")
    return f"_claim: {TIER_CLAIM_CEILING[tier]}_"


def assert_claim_ceiling(tier: str, text: str) -> None:
    """Chan tu ngu vuot tran claim cua tang.

    Vi du thuc: mot card viet "du kien IP giam" la nhay tu `measurement` len
    `prediction` chi bang mot dong tu — khong test so nao bat duoc, vi khong co
    so nao sai.
    """
    ceiling = TIER_CLAIM_CEILING[tier]
    # Gỡ dạng PHỦ ĐỊNH trước khi soi: chính câu miễn trừ bắt buộc của card —
    # "Đây là ghi nhận trạng thái, KHÔNG phải dự báo" — chứa từ bị cấm. Không gỡ
    # thì cổng bắt đúng cái câu sinh ra để tuân thủ nó.
    low = re.sub(r"không\s+(?:phải\s+)?(?:là\s+)?(?:dự\s*báo|dự\s*kiến)",
                 " ", text.lower())
    if ceiling == CLAIM_MEASUREMENT:
        banned = ("dự báo", "dự kiến", "sẽ giảm", "sẽ tăng", "kỳ vọng sẽ")
        hits = [w for w in banned if w in low]
        if hits:
            raise ClaimCeilingViolation(
                f"Measurement Card chứa từ ngữ DỰ BÁO {hits} — trần claim của tầng "
                f"này là `{ceiling}` (docs/15 §4). Card ghi nhận trạng thái; nhận "
                "định định lượng thuộc Model Brief.")
    if ceiling == CLAIM_ASSOCIATION:
        banned = ("gây ra", "nguyên nhân", "tác động nhân quả")
        hits = [w for w in banned if w in low]
        if hits:
            raise ClaimCeilingViolation(
                f"Phần analogue chứa từ ngữ NHÂN QUẢ {hits} — trần là `{ceiling}`; "
                "đây là event-study mô tả, không có identification (07v2 §6.4).")


@dataclass(frozen=True)
class MeasurementPayload:
    """Moi so cua card. Guard doi chieu narrative voi CHINH dict nay."""
    v: float
    specificity: float
    actor_weight: float
    s_gpr_now: float
    s_gpr_prev: float
    s_gpr_pctile: float
    jump: float
    jump_pctile: float
    ladder_state: int
    ladder_prev_state: int
    days_in_state: int
    detection_seconds: int


def compose_measurement_card(
    event: Mapping[str, str],
    payload: MeasurementPayload,
    meta: Mapping[str, str],
) -> str:
    """Measurement Card (docs/11 §2.2). Realtime, KHONG du bao.

    `event`: {headline, source, url, actor, target, channel, commitment, role}.
    `meta` : {published_at, model_version, rubric_version}.
    """
    d = payload.__dict__
    b = NarrativeBuilder(payload=d, extra_allowed=(0.6,))
    esc = "⚠️ LEO THANG" if payload.v > 0 else "🕊️ HÒA DỊU"
    b.add(f"### {esc} · {event['actor']} → {event['target']} · kênh "
          f"{event['channel'].upper()}")
    b.add(f"{meta['published_at']} · độ trễ phát hiện: "
          f"{payload.detection_seconds} giây\n")
    b.add(f"**SỰ KIỆN** — {event['headline']}")
    b.add(f"Nguồn: {event['source']} · {event.get('url', '—')}\n")
    b.add("**ĐO LƯỜNG**")
    b.add(f"- v = {payload.v:+.2f} · commitment = {event['commitment']} · "
          f"specificity = {payload.specificity:.2f}")
    b.add(f"- actor_role = {event['role']} (w={payload.actor_weight:.1f})\n")
    b.add("**TRẠNG THÁI**")
    b.add(f"- S-GPR({event['actor']}→{event['target']}): "
          f"{payload.s_gpr_prev:.2f} → {payload.s_gpr_now:.2f} "
          f"(phân vị {payload.s_gpr_pctile:.0f})")
    b.add(f"- Escalation Ladder: {LADDER_NAMES[payload.ladder_prev_state]} → "
          f"**{LADDER_NAMES[payload.ladder_state]}**"
          + (" ⬆ CHUYỂN BẬC" if payload.ladder_state > payload.ladder_prev_state
             else ""))
    b.add(f"- Đã ở bậc trước {payload.days_in_state} ngày")
    b.add(f"- JUMP = {payload.jump:.2f} (phân vị {payload.jump_pctile:.0f})\n")
    b.add("> Đây là ghi nhận trạng thái, KHÔNG phải dự báo. Nhận định định lượng "
          "nằm ở Model Brief.")
    b.add(f"\n_model: {meta['model_version']} · rubric: {meta['rubric_version']}_")
    b.add(claim_footer("card"))
    text = b.render()
    assert_claim_ceiling("card", _body_only(text))
    return text


def _body_only(text: str) -> str:
    """Bo dong tran claim truoc khi kiem tu ngu — chinh no chua chu 'claim'."""
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.strip().startswith("_claim:"))


@dataclass(frozen=True)
class GammaCell:
    """Mot o bang γ dua vao brief. `standardized` BAT BUOC — xem docs/16 §2.2."""
    outcome: str
    horizon: int
    beta: float
    pvalue: float
    standardized: float
    survived_holm: bool
    survived_battery: bool
    component: str | None = None      # None | "ANTICIPATED" | "SURPRISE"


def compose_model_brief(
    trigger: Mapping[str, str],
    gamma_cells: Iterable[GammaCell],
    analogues: Iterable[AnalogueResult],
    payload: Mapping,
    meta: Mapping[str, str],
    skipped: Iterable[Mapping] = (),
) -> str:
    """Model Brief (docs/11 §2.3): γ + analogue + đo lường, mỗi tầng gắn claim.

    `payload` phai chua MOI so xuat hien trong van ban (guard doi chieu). Cac o
    γ va analogue tu dong duoc gom vao payload nen caller khong phai chep tay.
    """
    cells = list(gamma_cells)
    ana = list(analogues)
    skips = [dict(s) for s in skipped]
    full_payload = {
        **dict(payload),
        "_n_obs": meta.get("n_obs"),
        "_gamma": [c.__dict__ for c in cells],
        "_analogue": [{"n": a.n, "median": a.median, "q25": a.q25, "q75": a.q75,
                       "share": a.share_same_sign, "h": a.horizon} for a in ana],
        "_skipped": skips,
    }
    b = NarrativeBuilder(payload=full_payload)
    b.add(f"## Model Brief — {trigger['label']} · {meta['generated_at']}\n")
    b.add(f"**TRẠNG THÁI KÍCH HOẠT** — {trigger['reason']}")
    b.add(claim_footer("card") + "\n")

    b.add("**TRUYỀN DẪN (bảng γ)**")
    if not cells:
        b.add("- Không ô nào của bảng γ đạt điều kiện đưa vào brief này.")
    for c in cells:
        if c.component:
            # docs/16 §2.2 dieu kien 2: nhan phai dung truoc khi in.
            check_component_labelling(c.component, c.outcome)
        flag = "sống sót Holm + battery" if (c.survived_holm and c.survived_battery) \
            else "chưa sống sót đầy đủ"
        b.add(f"- {c.outcome} h={c.horizon}: γ={c.beta:+.4f} "
              f"(chuẩn hóa {c.standardized:+.4f}, p={c.pvalue:.3f}) — {flag}")
    b.add("")

    b.add("**BỐI CẢNH LỊCH SỬ (tiền lệ)**")
    if not ana:
        b.add("- Không đủ tiền lệ để xuất phần này (n<5, cổng P3 docs/11 §6).")
    for a in ana:
        b.add(f"- h={a.horizon} · " + describe_analogue(a))
    for s in skips:
        b.add(f"- _bỏ qua_ {s['outcome']} h={s['horizon']}: chỉ {s['n_found']} "
              f"tiền lệ, cần ≥{s['n_required']} (cổng P3)")
    b.add(claim_footer("analogue") + "\n")

    b.add("**ĐỘ TIN CẬY**")
    # `n_obs` là TRƯỜNG SỐ, không phải câu văn có số. Bản nháp dùng `sample_note`
    # dạng văn xuôi tự do và guard chặn đúng — văn xuôi mang số là chính cái P1
    # sinh ra để cấm, vì số trong câu văn không đối chiếu được với payload.
    b.add(f"- Panel {meta['n_obs']} quan sát"
          + (f" · {meta['sample_caveat']}" if meta.get("sample_caveat") else ""))
    b.add(f"- data_version `{meta['data_version']}` · commit `{meta['git_commit']}`")
    b.add(claim_footer("distribution"))
    text = b.render()
    assert_claim_ceiling("analogue", _body_only(text))
    return text


def compose_vn_note(exposure: VNExposure, meta: Mapping[str, str]) -> str:
    """Phan VIET NAM (tang 3) khi CHUA co beta/theta/lambda da fit cho VN.

    `exposure` tu `pipeline.vn_exposure.vn_exposure_note` — thuan tra bang tu
    vietnam-params.md §2, khong LLM. Khi `has_quant_params=False` (hien tai
    LUON False — xem docstring `vn_exposure.py`), phan nay CHI noi kenh +
    huong, khong mot con so du bao nao — dung nguyen tac cua chinh skill
    gpr-macro-assessment ("khong co tham so uoc luong thi khong co claim dinh
    luong").
    """
    payload = {"has_quant_params": exposure.has_quant_params}
    b = NarrativeBuilder(payload=payload)
    b.add(f"**VIỆT NAM** — kênh: {exposure.exposure_channel}")
    b.add("- Vai trò: spillover (VN hầu như không phải initiator/respondent).")
    b.add(f"- {exposure.direction_note}")
    b.add(f"- Cơ chế: {exposure.mechanism_note}")
    if not exposure.has_quant_params:
        b.add("- Chưa có tham số ước lượng (β/θ/λ) cho VN — chỉ nêu kênh và "
              "hướng, KHÔNG nói độ lớn.")
    if meta.get("generated_at"):
        b.add(f"\n_generated: {meta['generated_at']}_")
    b.add(claim_footer("vn_note"))
    text = b.render()
    assert_claim_ceiling("vn_note", _body_only(text))
    return text
