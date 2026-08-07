"""Test Guard P1 dùng chung (`reporting/guard.py`) — tầng 4.

Guard phải bắt được số bịa, và quan trọng không kém: phải KHÔNG bắt nhầm hash /
ngày / mã tham chiếu, nếu không người viết sẽ tắt nó đi.

Có một bẫy đã xảy ra thật trong `test_report_guard_p1._e1c_unmatched`: nếu cho
phép fallback `int(x)` với số thập phân thì payload chứa 0 (rất hay gặp) sẽ nuốt
mọi số bịa dạng 0.xxx. Test dưới khóa điều đó.
"""
from __future__ import annotations

import pytest

from gpr_engine.reporting.guard import (
    GuardViolation,
    NarrativeBuilder,
    check_narrative,
    enforce,
    extract_numbers,
    payload_values,
)

PAYLOAD = {
    "n_obs": 231,
    "beta": -0.7685,
    "pvalue": 0.0173,
    "share": 0.489,
    "nested": {"supt_c": 2.61, "cells": [72, 23]},
}


# ---------------------------------------------------------------------------
# Bắt được số bịa
# ---------------------------------------------------------------------------
def test_catches_fabricated_number():
    rep = check_narrative("Hệ số mạnh gấp 37.42 lần baseline.", PAYLOAD)
    assert not rep.ok and "37.42" in rep.unmatched


def test_enforce_raises_with_actionable_message():
    with pytest.raises(GuardViolation, match="1.8|payload"):
        enforce("Cú sốc gấp 9.99× ngày thường.", PAYLOAD)


def test_accepts_numbers_from_payload():
    text = ("Mẫu 231 tháng, γ=-0.7685 (p=0.0173). "
            "Hằng số sup-t 2.61, 23/72 ô vượt dải.")
    assert check_narrative(text, PAYLOAD).ok


def test_accepts_percent_form_of_ratio():
    """payload lưu 0.489 nhưng narrative viết 48.9% — phải chấp nhận."""
    assert check_narrative("48.9% ô đảo chiều kết luận.", PAYLOAD).ok


# ---------------------------------------------------------------------------
# Bẫy: 0 trong payload không được nuốt mọi số thập phân
# ---------------------------------------------------------------------------
def test_zero_in_payload_does_not_swallow_decimals():
    """payload có 0 (n_exo_events=0 khi chưa có gold set) — số bịa 0.87 vẫn phải bị bắt."""
    payload = {"n_exo_events": 0, "n_endo_events": 166}
    rep = check_narrative("AUC đạt 0.87 ở mọi sub-sample.", payload)
    assert not rep.ok and "0.87" in rep.unmatched


def test_integer_fallback_only_for_integers():
    vals = payload_values({"x": 7})
    assert 7.0 in vals
    vals2 = payload_values({"x": 7.35})
    assert 7.0 not in vals2, "số thập phân không được sinh biến thể phần nguyên"


# ---------------------------------------------------------------------------
# Không bắt nhầm
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "data_version `f2579b30928f`, commit `72c4704`.",
    # Bug thật: `news_pipeline` truyền TÊN FILE γ làm data_version. Chỉ miễn hash
    # trần là không đủ — hash trong tên file bị regex "mốc năm" cắt 4 chữ số đầu,
    # đuôi `30928` thành token vô chủ và guard chặn mọi tin trên đường serving.
    "data_version `t2_full_holm_f2579b30928f.csv` · commit `n/a`",
    "Đọc `docs/reports/data/tier2_irf_innovation_8cc9bfb5c3b6_ar5-5-2.csv`.",
    "Sinh lúc 2026-08-03T10:00:00.",
    "Theo docs/14 §6.6 và SCA-01.",
    "Quyết định DEC-2026-08-02-shock-axis đã ký.",
    "Xem KĐ8 và KĐ-E1c.",
    "Ngưỡng 2σ theo IMF GFSR.",
    "Phương pháp MO-PM 2021.",
])
def test_does_not_flag_references(text):
    assert check_narrative(text, PAYLOAD).ok, f"bắt nhầm: {text!r}"


@pytest.mark.parametrize("text", [
    "Hệ số là `2.77` lần ngày thường.",          # số trần trong backtick
    "Ghi chú: `tăng 1.8 lần so với nền`.",       # văn xuôi mang số, nhét backtick
])
def test_backtick_does_not_hide_numbers(text):
    """Miễn trừ code span CHỈ dành cho định danh một token.

    Nếu nới thành "mọi thứ trong backtick" thì bọc backtick là cách né guard —
    đúng loại lỗi (số bịa trong narrative) mà P1 sinh ra để chặn.
    """
    assert not check_narrative(text, PAYLOAD).ok, f"lọt qua guard: {text!r}"


def test_skips_markdown_tables_by_default():
    """Bảng in thẳng từ DataFrame — kiểm chúng là việc của test tính toán."""
    text = "Kết quả:\n| a | b |\n|---|---|\n| 999.123 | 42.7 |\n"
    assert check_narrative(text, PAYLOAD).ok
    assert not check_narrative(text, PAYLOAD, skip_tables=False).ok


def test_extra_allowed_config_numbers():
    assert not check_narrative("Cửa sổ 250 phiên.", PAYLOAD).ok
    assert check_narrative("Cửa sổ 250 phiên.", PAYLOAD, extra_allowed=[250]).ok


def test_extract_numbers_ignores_year_marks():
    assert extract_numbers("Từ 1990 đến 2026, giá trị 3.14.") == ["3.14"]


# ---------------------------------------------------------------------------
# NarrativeBuilder — cửa duy nhất
# ---------------------------------------------------------------------------
def test_builder_guards_on_render():
    b = NarrativeBuilder(payload=PAYLOAD)
    b.add("Mẫu 231 tháng.").add("Hệ số -0.7685.")
    assert "231" in b.render()


def test_builder_blocks_fabricated_number_at_render():
    b = NarrativeBuilder(payload=PAYLOAD).add("Tăng 12.34% so với trước.")
    with pytest.raises(GuardViolation):
        b.render()


def test_builder_render_is_the_only_exit():
    """Không có đường lấy text mà bỏ qua guard — quên gọi guard là không thể."""
    b = NarrativeBuilder(payload=PAYLOAD)
    assert not hasattr(b, "text") and not hasattr(b, "to_string")
    assert callable(b.render)
