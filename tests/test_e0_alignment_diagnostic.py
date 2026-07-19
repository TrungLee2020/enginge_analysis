"""Pure tests cho gate timing của E0 aligned diagnostic."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_e0_alignment_diagnostic as diag  # noqa: E402


def _irf(beta_h1: float, p_h1: float, beta_h2: float, p_h2: float) -> pd.DataFrame:
    return pd.DataFrame({
        "beta": [0.0, beta_h1, beta_h2],
        "pvalue": [1.0, p_h1, p_h2],
    }, index=[0, 1, 2])


def test_alignment_shift_passes_at_preregistered_anchors():
    raw = _irf(-0.2, 0.09, -0.37, 0.008)
    aligned = _irf(-0.35, 0.01, -0.1, 0.3)
    result = diag.evaluate_shift(raw, aligned)
    assert result["passed"] is True
    assert result["raw_anchor_ok"] is True
    assert result["aligned_anchor_ok"] is True


def test_alignment_shift_fails_when_aligned_anchor_is_not_significant():
    raw = _irf(-0.2, 0.09, -0.37, 0.008)
    aligned = _irf(-0.35, 0.20, -0.1, 0.3)
    result = diag.evaluate_shift(raw, aligned)
    assert result["passed"] is False
    assert result["raw_anchor_ok"] is True
    assert result["aligned_anchor_ok"] is False
