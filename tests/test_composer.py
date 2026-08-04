"""Test composer tầng 4 (M6) — Measurement Card + Model Brief.

Ba lớp bảo vệ phải cùng hoạt động, và mỗi lớp bắt một loại lỗi khác nhau:
  - Guard P1 bắt SỐ bịa;
  - trần claim bắt TỪ NGỮ vượt mức nhận dạng (không có số nào sai);
  - cổng nhãn spec kép bắt việc gọi ANTICIPATED là cú sốc.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gpr_engine.econometrics.analogue import AnalogueResult, Neighbour
from gpr_engine.pipeline.vn_exposure import vn_exposure_note
from gpr_engine.reporting.composer import (
    TIER_CLAIM_CEILING,
    ClaimCeilingViolation,
    GammaCell,
    MeasurementPayload,
    assert_claim_ceiling,
    claim_footer,
    compose_measurement_card,
    compose_model_brief,
    compose_vn_note,
)
from gpr_engine.reporting.guard import GuardViolation

EVENT = {"headline": "Áp thuế bổ sung lên hàng Trung Quốc, hiệu lực 01/08.",
         "source": "truth_social", "url": "https://example.invalid/p/1",
         "actor": "USA", "target": "CHN", "channel": "trade",
         "commitment": "announced_action", "role": "head_of_state"}
META = {"published_at": "2026-07-18 14:07", "model_version": "gpt-4o-mini-2024-07-18",
        "rubric_version": "r1"}
PAYLOAD = MeasurementPayload(
    v=0.92, specificity=0.85, actor_weight=1.0, s_gpr_now=4.8, s_gpr_prev=2.1,
    s_gpr_pctile=94.0, jump=0.62, jump_pctile=96.0, ladder_state=4,
    ladder_prev_state=2, days_in_state=11, detection_seconds=41)


# ---------------------------------------------------------------------------
# Measurement Card
# ---------------------------------------------------------------------------
def test_card_contains_measurements_and_claim():
    card = compose_measurement_card(EVENT, PAYLOAD, META)
    assert "+0.92" in card and "94" in card and "41 giây" in card
    assert "S2 đe dọa" in card and "S4 hành động" in card and "CHUYỂN BẬC" in card
    assert claim_footer("card") in card
    assert "KHÔNG phải dự báo" in card


def test_card_guard_blocks_fabricated_number():
    """Sửa template để chèn số không có trong payload -> guard chặn."""
    bad = MeasurementPayload(**{**PAYLOAD.__dict__, "v": 0.92})
    with pytest.raises(GuardViolation):
        # actor_weight 1.0 hợp lệ; 7.77 thì không — mô phỏng bằng event bịa số.
        compose_measurement_card({**EVENT, "headline": "Thuế tăng 7.77 điểm."},
                                 bad, META)


def test_card_rejects_forecast_wording():
    """Card claim `measurement` — một động từ dự báo là nhảy mức nhận dạng."""
    with pytest.raises(ClaimCeilingViolation, match="DỰ BÁO"):
        assert_claim_ceiling("card", "IP dự kiến giảm trong hai tháng tới.")


def test_card_ceiling_is_measurement():
    assert TIER_CLAIM_CEILING["card"] == "measurement"


# ---------------------------------------------------------------------------
# Model Brief
# ---------------------------------------------------------------------------
def _analogue(n=6, dispersed=False) -> AnalogueResult:
    return AnalogueResult(
        as_of=pd.Timestamp("2026-07-18"), horizon=6, outcome_name="vix", n=n,
        median=2.1, q25=(-0.4 if dispersed else 0.4), q75=5.2,
        share_same_sign=0.83, dispersed=dispersed,
        neighbours=[Neighbour(pd.Timestamp("2018-03-01"), 0.91, 2.0)])


CELLS = [GammaCell(outcome="ip", horizon=2, beta=-0.7685, pvalue=0.017,
                   standardized=-0.1194, survived_holm=True, survived_battery=True)]
BRIEF_META = {"generated_at": "2026-07-18", "data_version": "f2579b30928f",
              "git_commit": "72c4704", "n_obs": 231}
TRIGGER = {"label": "bản bất thường · kênh thương mại",
           "reason": "JUMP vượt ngưỡng phân vị 96."}


def test_brief_has_three_claim_tiers():
    brief = compose_model_brief(TRIGGER, CELLS, [_analogue()],
                                {"jump_pctile": 96.0}, BRIEF_META)
    for tier in ("card", "analogue", "distribution"):
        assert claim_footer(tier) in brief, f"thiếu trần claim tầng {tier}"


def test_brief_reports_standardized_alongside_raw():
    """docs/16 §2.2 điều kiện 1: đóng góp phải có bản chuẩn hóa, không chỉ thô."""
    brief = compose_model_brief(TRIGGER, CELLS, [_analogue()],
                                {"jump_pctile": 96.0}, BRIEF_META)
    assert "-0.7685" in brief and "-0.1194" in brief
    assert "chuẩn hóa" in brief


def test_brief_silent_when_no_analogues():
    """n<5 -> phần bối cảnh nói rõ là không đủ, không bịa tiền lệ."""
    brief = compose_model_brief(TRIGGER, CELLS, [], {"jump_pctile": 96.0},
                                BRIEF_META,
                                skipped=[{"outcome": "vix", "horizon": 6,
                                          "n_found": 3, "n_required": 5}])
    assert "Không đủ tiền lệ" in brief and "P3" in brief
    assert "bỏ qua" in brief


def test_brief_dispersed_analogue_says_so():
    brief = compose_model_brief(TRIGGER, CELLS, [_analogue(dispersed=True)],
                                {"jump_pctile": 96.0}, BRIEF_META)
    assert "phân tán" in brief and "không kết luận" in brief


def test_brief_guard_blocks_number_outside_payload():
    # sample_caveat là văn xuôi tự do -> số trong đó KHÔNG truy được về payload.
    bad_meta = {**BRIEF_META, "sample_caveat": "hiệu lực chỉ 88.8%"}
    with pytest.raises(GuardViolation):
        compose_model_brief(TRIGGER, CELLS, [_analogue()], {"jump_pctile": 96.0},
                            bad_meta)


def test_brief_rejects_causal_wording_in_analogue_tier():
    with pytest.raises(ClaimCeilingViolation, match="NHÂN QUẢ"):
        assert_claim_ceiling("analogue", "Cú sốc gây ra sụt giảm sản lượng.")


def test_brief_blocks_anticipated_labelled_as_shock():
    """Cổng nhãn spec kép chạy ngay trong composer (docs/16 §2.2 điều kiện 2)."""
    cell = GammaCell(outcome="cú sốc lên IP", horizon=2, beta=-0.5, pvalue=0.04,
                     standardized=-0.05, survived_holm=True,
                     survived_battery=True, component="ANTICIPATED")
    with pytest.raises(ValueError, match="#9|ANTICIPATED"):
        compose_model_brief(TRIGGER, [cell], [_analogue()], {"jump_pctile": 96.0},
                            BRIEF_META)


def test_brief_allows_shock_wording_for_surprise_component():
    cell = GammaCell(outcome="cú sốc lên IP", horizon=2, beta=-0.5, pvalue=0.04,
                     standardized=-0.05, survived_holm=True,
                     survived_battery=True, component="SURPRISE")
    brief = compose_model_brief(TRIGGER, [cell], [_analogue()],
                                {"jump_pctile": 96.0}, BRIEF_META)
    assert "cú sốc lên IP" in brief


# ---------------------------------------------------------------------------
# VN note (tầng 3 VN, chưa có β/θ/λ — chỉ kênh + hướng)
# ---------------------------------------------------------------------------
def test_vn_note_has_association_ceiling_and_no_quant_caveat():
    note = compose_vn_note(vn_exposure_note("trade"), {"generated_at": "2026-08-04"})
    assert claim_footer("vn_note") in note
    assert "chưa có tham số ước lượng" in note.lower()
    assert TIER_CLAIM_CEILING["vn_note"] == "association"


def test_vn_note_rejects_causal_wording():
    """`vn_note` dùng chung trần association với analogue — cùng cấm từ nhân quả."""
    with pytest.raises(ClaimCeilingViolation, match="NHÂN QUẢ"):
        assert_claim_ceiling("vn_note", "Cú sốc này gây ra sụt giảm VN-Index.")


def test_vn_note_omits_meta_line_when_absent():
    note = compose_vn_note(vn_exposure_note("energy"), {})
    assert "_generated:" not in note
