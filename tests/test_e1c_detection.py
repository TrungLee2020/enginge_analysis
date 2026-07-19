"""test_e1c_detection.py — logic AUC của E1c (không gọi mạng/FRED).

docs/13 §2.3: AUC bất biến với biến đổi đơn điệu — đây là tính chất cốt lõi sửa
lỗi §1.2 của E1b. Test nó trực tiếp trên dữ liệu tổng hợp có kiểm soát.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_e1c_shock_detection as e1c  # noqa: E402


def _series(vals, start="2000-01-03"):
    idx = pd.bdate_range(start, periods=len(vals))
    return pd.Series(vals, index=idx, name="m")


def test_auc_perfect_separation():
    """Thước đo cao HẲN ở ngày sự kiện -> AUC ~ 1.0."""
    n = 200
    vals = np.zeros(n)
    idx = pd.bdate_range("2000-01-03", periods=n)
    s = pd.Series(vals, index=idx, name="m")
    events = idx[[50, 100, 150]]
    s.loc[events] = 100.0                       # sự kiện cao hẳn
    a, ne, nc = e1c.auc(s, events, window=0, buffer=5)
    assert a > 0.99, f"phân tách hoàn hảo phải cho AUC~1, được {a}"
    assert ne == 3


def test_auc_random_near_half():
    """Thước đo ngẫu nhiên, sự kiện không đặc biệt -> AUC ~ 0.5."""
    rng = np.random.default_rng(0)
    n = 600
    idx = pd.bdate_range("2000-01-03", periods=n)
    s = pd.Series(rng.standard_normal(n), index=idx, name="m")
    events = idx[[100, 200, 300, 400]]          # không liên quan giá trị
    a, ne, nc = e1c.auc(s, events, window=1, buffer=10)
    assert 0.3 < a < 0.7, f"ngẫu nhiên phải ~0.5, được {a}"


def test_auc_invariant_under_monotonic_transform():
    """CỐT LÕI docs/13 §2.3: AUC bất biến với biến đổi đơn điệu tăng.

    Cùng thứ tự -> cùng AUC, dù thang khác hẳn (đây là thứ ngưỡng 2σ KHÔNG có).
    """
    rng = np.random.default_rng(1)
    n = 500
    idx = pd.bdate_range("2000-01-03", periods=n)
    base = rng.standard_normal(n)
    s = pd.Series(base, index=idx, name="m")
    events = idx[[80, 160, 240, 320, 400]]
    s.loc[events] += 1.5                          # sự kiện hơi cao

    a_raw, _, _ = e1c.auc(s, events, window=1, buffer=10)
    # biến đổi đơn điệu tăng: exp (giãn đuôi phải mạnh, như JUMP zero-inflate/skew)
    a_exp, _, _ = e1c.auc(np.exp(s), events, window=1, buffer=10)
    # và log1p sau khi dịch dương (đơn điệu tăng khác)
    a_log, _, _ = e1c.auc(np.log1p(s - s.min() + 1e-6), events, window=1, buffer=10)

    assert abs(a_raw - a_exp) < 1e-9, "AUC phải bất biến với exp (đơn điệu)"
    assert abs(a_raw - a_log) < 1e-9, "AUC phải bất biến với log1p-shift (đơn điệu)"


def test_control_mask_excludes_buffer():
    """Nhóm control loại ±buffer quanh MỌI sự kiện (chống nhiễm)."""
    idx = pd.bdate_range("2000-01-03", periods=100)
    events = pd.DatetimeIndex([idx[50]])
    ev_mask, ctrl_mask = e1c.event_and_control_masks(idx, events, window=1, buffer=10)
    # ngày trong ±10 quanh event KHÔNG được là control
    near = (idx >= events[0] - pd.Timedelta(days=10)) & (idx <= events[0] + pd.Timedelta(days=10))
    assert not (ctrl_mask & near).any(), "control không được chứa ngày trong vùng đệm"
    # event mask chỉ ±1 ngày quanh sự kiện
    assert ev_mask.sum() <= 3


def test_auc_returns_nan_when_too_few():
    """Quá ít sự kiện -> NaN, không crash."""
    s = _series(np.arange(50, dtype=float))
    a, ne, nc = e1c.auc(s, pd.DatetimeIndex([s.index[10]]), window=0, buffer=2)
    assert np.isnan(a)


def test_rank_orders_by_auc():
    table = {
        "A": {"full": {"auc": 0.9}},
        "B": {"full": {"auc": 0.7}},
        "C": {"full": {"auc": 0.95}},
    }
    assert e1c.rank(table) == ["C", "A", "B"]
