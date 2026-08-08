"""test_golden_news_item.py — BẢN THAM CHIẾU: 1 tin vào -> hệ thống tính gì, ra gì.

Mục đích khác các test còn lại: những test kia kiểm TỪNG mảnh (s_gpr, ladder,
guard...); file này ghim TOÀN BỘ chuỗi cho MỘT tin cụ thể, với số liệu TÍNH TAY
kiểm được bằng máy tính bỏ túi. Dùng khi:
  - cần biết "đưa tin X vào thì đúng ra phải ra số bao nhiêu" trước khi tin output;
  - đổi công thức/tham số mà không biết mình vừa phá gì (test này đỏ ngay);
  - đọc để hiểu chuỗi xử lý mà không phải lần theo 400 dòng news_pipeline.py.

CHUỖI XỬ LÝ THẬT (verified 2026-08-08, đọc code + chạy):

  tin (Statement)
    -> score_statement()          LLM đo: v, actor/target, channel, commitment,
                                  specificity, rationale.  [chân B]
    -> as_of = published_at.normalize()          (UTC nửa đêm của ngày tin)
    -> jump_series_provider(as_of)               [chân A: GPRD daily từ ext_series]
         jump_val      = JUMP tại as_of, 0.0 nếu as_of không có trong chuỗi
         chain_a_stale = bản ghi GPRD mới nhất cách as_of > 35 ngày
    -> commitment -> gamma_channel (act|threat) -> bảng γ tầng 2 (Holm + battery b)
    -> channel -> transmission_channel -> VN note (tầng 3, ĐỊNH TÍNH)
    -> nếu pair_identified:
         S-GPR (rolling 7 ngày lịch) + percentile expanding
         Ladder (ngưỡng config/ladder_v1.yaml)
         Measurement Card (qua Guard P1)

CÔNG THỨC ĐÃ ĐỐI CHIẾU docs/00 §2.5 — code khớp nguyên văn:
    S-GPR_{a->b,t}  = Σ_i w(role_i) · max(v_i, 0) · specificity_i  / n_source_day
    S-CONC_{a->b,t} = Σ_i w(role_i) · max(-v_i, 0)                 / n_source_day
    w(role) INIT: head_of_state 1.0 · central_bank_governor 0.8 ·
                  minister 0.6 · spokesperson 0.4        (CLAUDE.md #7: chỉ là KHỞI TẠO)
    S-CONC cố ý KHÔNG nhân specificity (đúng spec §2.5 nguyên văn).
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from gpr_engine.econometrics.ladder import classify_ladder, load_ladder_config
from gpr_engine.indices.s_gpr import (
    DEFAULT_ROLE_WEIGHTS_INIT,
    expanding_percentile,
    s_gpr_pair,
)
from gpr_engine.pipeline.news_pipeline import process_news_item
from gpr_engine.reporting.composer import GammaCell
from gpr_engine.scoring.statement_scorer import ScorerConfig, Statement

CONFIG = ScorerConfig(model_version="golden-v1", training_cutoff=dt.date(2026, 1, 1))
EMPTY_HISTORY = pd.DataFrame(columns=["published_at", "source", "actor_country",
                                      "target_country", "v", "specificity",
                                      "speaker_role"])

# Tin mẫu CHUẨN của file này — mọi con số kỳ vọng bên dưới suy ra từ đây.
NEWS_DATE = pd.Timestamp("2026-08-08 14:07", tz="UTC")
GOLDEN_V = 0.40
GOLDEN_SPECIFICITY = 0.7
GOLDEN_ROLE = "minister"          # w = 0.6


def _golden_stmt(**kw) -> Statement:
    base = {"source": "manual_test", "published_at": NEWS_DATE,
            "speaker": "Test Speaker", "speaker_role": GOLDEN_ROLE,
            "text": "The United States is prepared to impose new sanctions on "
                    "Iran if these nuclear violations continue."}
    base.update(kw)
    return Statement(**base)


def _golden_llm(v=GOLDEN_V, spec=GOLDEN_SPECIFICITY, actor="USA", target="IRN",
                channel="sanction", commitment="conditional",
                rationale="Conditional sanctions threat tied to compliance."):
    def _call(messages, temperature):
        return json.dumps({"v": v, "actor_country": actor, "target_country": target,
                           "channel": channel, "commitment": commitment,
                           "specificity": spec, "rationale": rationale})
    return _call


def _gamma_loader(channel):
    return ([GammaCell(outcome="oil", horizon=1, beta=0.5, pvalue=0.03,
                       standardized=0.5, survived_holm=True, survived_battery=True)],
            "t2_full_holm_golden.csv")


def _no_chain_a(as_of):
    """Chain A rỗng — đúng tình trạng khi chưa ingest GPRD, hoặc GPRD quá cũ."""
    return pd.Series(dtype=float)


def _fresh_chain_a(as_of, jump_at_asof=0.0, days=400):
    """Chuỗi JUMP giả có bản ghi ngay tại as_of (chain A 'tươi')."""
    idx = pd.date_range(end=as_of, periods=days, freq="D", tz="UTC").normalize()
    s = pd.Series(0.0, index=idx)
    s.iloc[-1] = jump_at_asof
    return s


def _run(llm=None, jump_provider=_no_chain_a, history=EMPTY_HISTORY, **stmt_kw):
    return process_news_item(
        _golden_stmt(**stmt_kw), llm or _golden_llm(), CONFIG,
        history_provider=lambda pair: history,
        jump_series_provider=jump_provider,
        gamma_loader=_gamma_loader)


# ---------------------------------------------------------------------------
# 1. S-GPR — công thức docs/00 §2.5, TÍNH TAY được
# ---------------------------------------------------------------------------
def test_s_gpr_equals_hand_computed_value():
    """S-GPR = w(role) · max(v,0) · specificity, 1 phát ngôn 1 nguồn 1 ngày.

    0.6 (minister) × 0.40 (v) × 0.7 (specificity) = 0.168
    Đây ĐÚNG con số quan sát trên chạy thật với Gemini (2026-08-08).
    """
    result = _run()
    assert result.pair_identified is True
    assert result.score["actor_country"] == "USA"
    assert result.score["target_country"] == "IRN"
    expected = DEFAULT_ROLE_WEIGHTS_INIT[GOLDEN_ROLE] * GOLDEN_V * GOLDEN_SPECIFICITY
    assert expected == pytest.approx(0.168)
    assert result.s_gpr_now == pytest.approx(expected)


@pytest.mark.parametrize("role,expected", [
    ("head_of_state", 1.0 * GOLDEN_V * GOLDEN_SPECIFICITY),          # 0.280
    ("central_bank_governor", 0.8 * GOLDEN_V * GOLDEN_SPECIFICITY),  # 0.224
    ("minister", 0.6 * GOLDEN_V * GOLDEN_SPECIFICITY),               # 0.168
    ("spokesperson", 0.4 * GOLDEN_V * GOLDEN_SPECIFICITY),           # 0.112
])
def test_role_weight_scales_s_gpr_linearly(role, expected):
    """Cùng một tin, đổi vai người phát ngôn -> S-GPR tỉ lệ thẳng với w(role)."""
    assert _run(speaker_role=role).s_gpr_now == pytest.approx(expected)


def test_conciliatory_statement_gives_zero_s_gpr_not_negative():
    """v < 0 (hòa giải) -> S-GPR = 0, KHÔNG âm — hai chiều giữ riêng, không net
    (docs/00 §2.5 quy tắc 1). Phần hòa giải nằm ở S-CONC, không trừ vào S-GPR."""
    result = _run(llm=_golden_llm(v=-0.60, rationale="Offer to resume talks."))
    assert result.s_gpr_now == pytest.approx(0.0)


def test_s_conc_does_not_multiply_specificity():
    """S-CONC = w·max(-v,0) — KHÔNG nhân specificity (spec §2.5 nguyên văn).

    Kiểm thẳng trên s_gpr_pair vì NewsAssessment không phát S-CONC ra ngoài.
    """
    scores = pd.DataFrame([{
        "published_at": NEWS_DATE, "source": "s", "actor_country": "USA",
        "target_country": "IRN", "v": -0.60, "specificity": 0.7,
        "speaker_role": "minister"}])
    out = s_gpr_pair(scores)
    assert out["s_conc"].iloc[-1] == pytest.approx(0.6 * 0.60)     # 0.36, KHÔNG ×0.7
    assert out["s_gpr"].iloc[-1] == pytest.approx(0.0)


def test_specificity_scales_s_gpr():
    """specificity là hệ số nhân thẳng: tin mơ hồ (0.1) yếu hơn tin cụ thể (0.9)."""
    vague = _run(llm=_golden_llm(spec=0.1)).s_gpr_now
    precise = _run(llm=_golden_llm(spec=0.9)).s_gpr_now
    assert vague == pytest.approx(0.6 * 0.40 * 0.1)
    assert precise == pytest.approx(0.6 * 0.40 * 0.9)
    assert precise > vague


# ---------------------------------------------------------------------------
# 2. Percentile — vì sao tin ĐẦU TIÊN luôn có pctile = 0
# ---------------------------------------------------------------------------
def test_percentile_is_zero_for_first_item_because_min_periods_60():
    """s_gpr_pctile = 0.0 với tin đầu tiên KHÔNG phải lỗi.

    expanding_percentile(min_periods=60) trả NaN khi chưa đủ 60 quan sát;
    news_pipeline quy NaN -> 0.0. Nghĩa là: percentile CHỈ có nghĩa sau khi cặp
    actor>target đã tích đủ 60 ngày lịch sử. Đọc "pctile=0" của tin đầu là
    "chưa đủ lịch sử để xếp hạng", KHÔNG phải "thấp kỷ lục".
    """
    result = _run()
    assert result.s_gpr_pctile == 0.0
    short = pd.Series(range(10), index=pd.date_range("2026-01-01", periods=10))
    assert expanding_percentile(short, min_periods=60).isna().all()


def test_percentile_becomes_meaningful_after_60_observations():
    """Đủ 60 quan sát thì percentile mới bắt đầu có giá trị — dùng định nghĩa
    STRICT '<' (docs/00: chuỗi zero-inflated dùng '<=' sẽ cho ngày im ắng ~100)."""
    s = pd.Series([1.0] * 60 + [99.0],
                  index=pd.date_range("2026-01-01", periods=61))
    pct = expanding_percentile(s, min_periods=60)
    assert pct.iloc[-1] == pytest.approx(100.0)     # 99 lớn hơn toàn bộ lịch sử
    assert pct.iloc[59] == pytest.approx(0.0)       # 1.0 không lớn hơn cái nào


# ---------------------------------------------------------------------------
# 3. Escalation Ladder — thực tế CHỈ S0 và S4 với ràng buộc dữ liệu hiện tại
# ---------------------------------------------------------------------------
def test_ladder_is_S0_when_chain_a_absent():
    """Không có GPRD -> jump_pct NaN -> S4 không kích -> S0.

    S0 ở đây nghĩa là "không có bằng chứng leo thang bậc cao", KHÔNG phải
    "đã xác nhận yên ắng" — phân biệt bằng cờ chain_a_stale.
    """
    result = _run()
    assert result.ladder_state == 0
    assert result.ladder_computed is True      # tính THÀNH CÔNG ra S0, khác lỗi
    assert result.chain_a_stale is True        # nhưng chain A không có dữ liệu


def test_ladder_reaches_S4_when_jump_percentile_above_95():
    """S4 kích khi jump_pct > 95 (config/ladder_v1.yaml, mode=any).

    Dựng chuỗi JUMP: 400 ngày bằng 0, ngày cuối vọt -> percentile 100 > 95.
    """
    result = _run(jump_provider=lambda as_of: _fresh_chain_a(as_of, jump_at_asof=5.0))
    assert result.jump_pctile > 95.0
    assert result.ladder_state == 4
    assert result.chain_a_stale is False


def test_ladder_S2_unreachable_because_gdelt_not_ingested():
    """S2 cần quad3_pct/quad4_pct (GDELT chân C) — CHƯA ingest, luôn NaN.

    Đây là hạn chế THẬT đã ghi trong config/ladder_v1.yaml, không phải bug.
    Test khóa lại: nếu sau này ingest GDELT thì test này phải được sửa có chủ
    đích, không để S2 âm thầm vẫn chết.
    """
    cfg = load_ladder_config()
    indicators = pd.DataFrame({
        "s_gpr_pair_pct": [99.0],       # thỏa điều kiện S2 thứ nhất
        "quad3_pct": [float("nan")],    # CHƯA CÓ -> không thỏa
        "quad4_pct": [float("nan")],
        "jump_pct": [0.0],
    }, index=pd.DatetimeIndex(["2026-08-08"], name="date"))
    assert int(classify_ladder(indicators, cfg)["state"].iloc[0]) == 0


# ---------------------------------------------------------------------------
# 4. Bảng γ tầng 2 — commitment quyết định đọc cột nào
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("commitment,expected_channel", [
    ("announced_action", "act"),     # hành động đã công bố -> GPRD_ACT
    ("conditional", "threat"),       # đe dọa có điều kiện  -> GPRD_THREAT
    ("rhetoric", "threat"),          # khoa trương          -> GPRD_THREAT
])
def test_commitment_selects_gamma_channel(commitment, expected_channel):
    """⚠️ act/threat ở đây là BIẾN THỂ GPRD dùng làm shock, KHÔNG PHẢI kênh
    truyền dẫn energy/trade/financial/military — proxy có chủ đích, đã ghi rõ
    trong sample_caveat của mọi Model Brief (pipeline/gamma_lookup.py)."""
    result = _run(llm=_golden_llm(commitment=commitment))
    assert result.gamma_channel == expected_channel


# ---------------------------------------------------------------------------
# 5. Kênh truyền dẫn -> VN (tầng 3) — CÒN TRỐNG có chủ đích
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("channel,expected", [
    ("trade", "trade"), ("energy", "energy"), ("military", "military"),
    ("sanction", None), ("diplomacy", None), ("tech", None),
])
def test_channel_to_transmission_leaves_three_unmapped(channel, expected):
    """sanction/diplomacy/tech -> None: 6 kênh chấm điểm KHÔNG phủ hết 4 kênh
    truyền dẫn. Quyết định thiết kế đang MỞ (docs/15 §6.3) — trả None là ĐÚNG,
    đoán bừa mới là sai. Hệ quả thấy trên chạy thật: tin sanction -> VN note
    ghi "chưa xác định kênh"."""
    assert _run(llm=_golden_llm(channel=channel)).transmission_channel == expected


def test_vn_note_never_claims_magnitude_without_fitted_params():
    """config/params/vn.yaml chưa có mục `fitted:` -> VN note chỉ nêu kênh +
    hướng, KHÔNG nói độ lớn. Trần claim = association."""
    note = _run(llm=_golden_llm(channel="energy")).vn_note
    assert "KHÔNG nói độ lớn" in note or "chưa có tham số" in note.lower()
    assert "_claim: association_" in note


# ---------------------------------------------------------------------------
# 6. Guard P1 — số bịa trong rationale bị chặn, phần còn lại VẪN phát
# ---------------------------------------------------------------------------
def test_invented_number_in_rationale_blocks_card_but_not_the_rest():
    """LLM viết số không có trong payload -> Guard P1 chặn measurement_card.

    Đây là hành vi ĐÚNG (đã gặp thật với Gemini: "risk escalated by roughly
    42%"). Quan trọng: chỉ CARD mất, macro_brief/vn_note/S-GPR/ladder vẫn còn —
    suy giảm có kiểm soát, không sập cả tin.
    """
    result = _run(llm=_golden_llm(rationale="Risk escalated by roughly 42% this week."))
    assert result.measurement_card is None
    assert result.measurement_card_error is not None
    assert "Guard P1" in result.measurement_card_error
    # phần còn lại KHÔNG mất
    assert result.macro_brief
    assert result.vn_note
    assert result.s_gpr_now == pytest.approx(0.168)
    assert result.ladder_computed is True


def test_qualitative_rationale_passes_guard_and_produces_card():
    """rationale định tính (đúng quy tắc prompt p2) -> card sinh ra bình thường."""
    result = _run(llm=_golden_llm(
        rationale="Conditional sanctions threat tied to future compliance."))
    assert result.measurement_card_error is None
    assert result.measurement_card is not None
    assert "_claim: measurement_" in result.measurement_card


# ---------------------------------------------------------------------------
# 7. Không xác định được cặp nước -> bỏ qua chỉ số cặp, KHÔNG phải lỗi
# ---------------------------------------------------------------------------
def test_no_country_means_no_pair_index_but_still_emits_brief():
    """LLM trả actor/target = null (tin không nêu nước) -> S-GPR/Ladder/card bỏ
    qua ĐÚNG THIẾT KẾ; macro_brief + vn_note vẫn phát. Đây là nguyên nhân THẬT
    của lần chạy đầu 2026-08-08 (câu mẫu cũ không nêu tên nước)."""
    result = _run(llm=_golden_llm(actor=None, target=None))
    assert result.pair_identified is False
    assert result.s_gpr_now == 0.0
    assert result.ladder_computed is False
    assert result.measurement_card is None
    assert result.measurement_card_error is None   # KHÔNG có lỗi — đúng thiết kế
    assert result.macro_brief and result.vn_note


# ---------------------------------------------------------------------------
# 8. Chain A: AI-GPR ĐÃ ingest nhưng KHÔNG được dùng ở đường serving
# ---------------------------------------------------------------------------
def test_chain_a_defaults_to_GPRD_unchanged():
    """Mặc định VẪN là GPRD sau khi tham số hóa (E3 §6 khuyến nghị 1).

    Trước 2026-08-08 `store.load_jump_series` hard-code `series_id='GPRD'`;
    giờ là tham số. Đổi MẶC ĐỊNH là đổi thước đo shock — E3 đo được GPRD và
    AI-GPR chỉ trùng ~1/5 số ngày kích S4 dù cùng tần suất — nên phải qua
    governance, không phải đổi ngầm. Test khóa đúng điều đó.
    """
    from gpr_engine.pipeline.news_pipeline import DEFAULT_CHAIN_A_SERIES
    from gpr_engine.service import store
    assert store.CHAIN_A_SERIES_DEFAULT == "GPRD"
    assert DEFAULT_CHAIN_A_SERIES == "GPRD"


def test_caveat_names_chain_a_series_when_not_default():
    """Dùng chuỗi khác mặc định -> Model Brief PHẢI nói ra.

    Vì hai chuỗi kích S4 ở những NGÀY khác nhau (Jaccard 0.203), một S4 từ
    AI-GPR không so trực tiếp được với S4 từ GPRD. Im lặng ở đây là để người
    đọc tưởng nhầm hai con số cùng thước đo.
    """
    def _aigpr_provider(as_of):
        s = _fresh_chain_a(as_of)
        s.attrs["series_id"] = "AIGPR"
        return s

    brief = _run(jump_provider=_aigpr_provider).macro_brief
    assert "AIGPR" in brief
    assert "E3_aigpr_jump" in brief    # trỏ report thay vì chép số (Guard P1)

    # Chuỗi mặc định thì KHÔNG thêm cảnh báo thừa
    assert "KHÔNG phải" not in _run(jump_provider=_fresh_chain_a).macro_brief
