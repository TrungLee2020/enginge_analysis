"""Test pipeline.vn_exposure — tra bang thuan, khong LLM."""
from __future__ import annotations

import pytest

from gpr_engine.pipeline.vn_exposure import (
    TRANSMISSION_CHANNELS,
    VNExposure,
    vn_exposure_note,
)


def test_all_four_channels_mapped():
    for ch in TRANSMISSION_CHANNELS:
        exp = vn_exposure_note(ch)
        assert isinstance(exp, VNExposure)
        assert exp.transmission_channel == ch
        assert exp.has_quant_params is False
        assert exp.claim == "association"


def test_none_channel_is_honest_gap_not_a_guess():
    exp = vn_exposure_note(None)
    assert exp.transmission_channel is None
    assert "chưa xác định" in exp.direction_note.lower()


def test_trade_channel_notes_both_directions():
    exp = vn_exposure_note("trade")
    assert "rủi ro" in exp.direction_note and "cơ hội" in exp.direction_note


def test_unknown_channel_raises():
    with pytest.raises(ValueError, match="không thuộc"):
        vn_exposure_note("sanction")
