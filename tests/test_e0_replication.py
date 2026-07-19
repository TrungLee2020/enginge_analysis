"""test_e0_replication.py — logic pass/fail của E0 harness (không gọi mạng/FRED).

E0 chạy trên dữ liệu thật (FRED) nên không test end-to-end ở CI. Nhưng logic chấm
PASS/FAIL (evaluate) là nơi dễ hỏng âm thầm — test nó trên IRF giả có kiểm soát.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_e0_replication as e0  # noqa: E402


def _irf(betas: dict[int, float], pvals: dict[int, float]) -> pd.DataFrame:
    idx = sorted(betas)
    df = pd.DataFrame({
        "beta": [betas[h] for h in idx],
        "se": [0.1] * len(idx),
        "pvalue": [pvals[h] for h in idx],
        "ci_low": [betas[h] - 0.2 for h in idx],
        "ci_high": [betas[h] + 0.2 for h in idx],
    }, index=idx)
    df.index.name = "horizon"
    return df


def test_pass_when_short_horizon_negative_significant():
    """IP giảm có ý nghĩa ở h=2 (đúng hướng C-I) -> PASS."""
    irf = _irf(
        betas={0: -0.1, 1: -0.23, 2: -0.37, 3: 0.05, 6: 0.06},
        pvals={0: 0.32, 1: 0.09, 2: 0.008, 3: 0.68, 6: 0.64})
    ev = e0.evaluate(irf)
    assert ev["passed"] is True
    assert 2 in ev["neg_sig_horizons"]
    assert ev["trough_horizon"] == 2


def test_fail_when_no_short_negative_significant():
    """Không horizon ngắn nào âm-có-ý-nghĩa -> FAIL (nghi pipeline)."""
    irf = _irf(
        betas={0: 0.1, 1: 0.2, 2: 0.15, 3: 0.05, 6: 0.3},
        pvals={0: 0.4, 1: 0.3, 2: 0.5, 3: 0.6, 6: 0.02})   # h=6 dương có ý nghĩa
    ev = e0.evaluate(irf)
    assert ev["passed"] is False
    assert ev["neg_sig_horizons"] == []


def test_fail_when_negative_but_not_significant():
    """Âm nhưng p>=0.10 -> chưa đủ, FAIL (không phân biệt được với null)."""
    irf = _irf(
        betas={1: -0.3, 2: -0.4, 3: -0.2, 6: -0.1},
        pvals={1: 0.20, 2: 0.15, 3: 0.30, 6: 0.40})
    ev = e0.evaluate(irf)
    assert ev["passed"] is False
