"""Test động cơ SCA (docs/12 §3) — 3 thống kê + moving-block bootstrap dưới null.

Kiểm cốt lõi trước khi tin trên dữ liệu thật (lý do docs/13 §5): SIZE (hiệu ứng
thật=0 → tỉ lệ bác bỏ ≈ danh nghĩa) + POWER (hiệu ứng biết trước → phát hiện được).
Đây là điều kiện docs/12 §3.2 — động cơ resampling phải đúng size trước khi dùng.

Động cơ AGNOSTIC với LP: spec là callable (data, row_idx) -> (coef, pvalue). Test
dùng OLS đơn giản để size/power có nền lý thuyết.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpr_engine.econometrics.sca_engine import (
    dominant_sign_share,
    moving_block_indices,
    sca_statistics,
    stouffer_z,
)


# ---------------------------------------------------------------------------
# Moving-block bootstrap indices
# ---------------------------------------------------------------------------
def test_moving_block_covers_n_and_uses_blocks():
    rng = np.random.default_rng(0)
    idx = moving_block_indices(n=120, block_len=12, rng=rng)
    assert len(idx) == 120                       # trả đúng N hàng
    assert idx.min() >= 0 and idx.max() < 120
    # block: các đoạn liên tiếp độ dài 12 -> có nhiều cặp idx[i+1]==idx[i]+1
    consecutive = np.sum(np.diff(idx) == 1)
    assert consecutive >= 100 * 0.6              # phần lớn là bước +1 (trong block)


def test_moving_block_deterministic_with_seed():
    a = moving_block_indices(100, 10, np.random.default_rng(42))
    b = moving_block_indices(100, 10, np.random.default_rng(42))
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# 3 thống kê
# ---------------------------------------------------------------------------
def test_stouffer_z_combines_pvalues():
    # p nhỏ đồng loạt -> Z lớn dương (nếu z-scores cùng chiều)
    z = stouffer_z(np.array([0.01, 0.02, 0.03]), signs=np.array([1, 1, 1]))
    assert z > 2
    # p ~ 0.5 -> Z ~ 0
    z0 = stouffer_z(np.array([0.5, 0.5, 0.5]), signs=np.array([1, -1, 1]))
    assert abs(z0) < 1.0


def test_dominant_sign_share():
    coefs = np.array([1.0, 2.0, -0.5, 3.0, 0.1])   # 4 dương / 1 âm
    share, sign = dominant_sign_share(coefs)
    assert sign == 1
    assert share == 0.8


def test_sca_statistics_shape():
    coefs = np.array([0.3, 0.5, -0.1, 0.4])
    pvals = np.array([0.04, 0.01, 0.6, 0.08])
    signs = np.sign(coefs)
    stats = sca_statistics(coefs, pvals, signs, alpha=0.05, expected_sign=1)
    assert set(stats) >= {"median_coef", "share_significant", "stouffer_z"}
    # 2/4 spec p<0.05 và dấu dương (0.3@0.04, 0.5@0.01)
    assert stats["share_significant"] == 0.5


# ---------------------------------------------------------------------------
# SIZE — hiệu ứng thật = 0 -> bác bỏ ≈ danh nghĩa (docs/12 §3.2)
# ---------------------------------------------------------------------------
def _ols_spec_factory(x_col, y_col):
    """spec(data, idx) -> (coef, pvalue) bằng OLS y~x trên hàng idx."""
    import statsmodels.api as sm

    def spec(data: pd.DataFrame, idx: np.ndarray):
        d = data.iloc[idx]
        X = sm.add_constant(d[[x_col]].values)
        res = sm.OLS(d[y_col].values, X).fit()
        return float(res.params[1]), float(res.pvalues[1])
    return spec


def test_size_under_null_is_near_nominal():
    """Sinh dữ liệu y độc lập x (hiệu ứng=0). Curve observed KHÔNG được bác bỏ
    quá mức: p-value của thống kê phải ~Uniform → hiếm khi < 0.05.

    Chạy nhiều mẫu độc lập, đếm tỉ lệ curve bị 'bác bỏ null' — phải ≈ 5%, không
    phình lên (điều dễ sai với moving-block trên chuỗi dai dẳng).
    """
    from gpr_engine.econometrics.sca_engine import run_sca

    rng = np.random.default_rng(7)
    n_trials = 40
    B = 200
    rejects = 0
    # vài spec OLS trên các cột x khác nhau (mô phỏng lưới nhỏ)
    for t in range(n_trials):
        n = 200
        # x dai dẳng (AR1) — chỗ moving-block dễ sai size
        x = np.zeros(n)
        e = rng.standard_normal(n)
        for i in range(1, n):
            x[i] = 0.7 * x[i - 1] + e[i]
        y = rng.standard_normal(n)                 # ĐỘC LẬP x -> hiệu ứng thật = 0
        data = pd.DataFrame({"x": x, "y": y})
        specs = [_ols_spec_factory("x", "y")]
        res = run_sca(specs, data, B=B, block_len=20,
                      rng=np.random.default_rng(1000 + t), expected_sign=None)
        if res["pvalue_stouffer"] < 0.05:
            rejects += 1
    rate = rejects / n_trials
    # size không được phình mạnh: cho phép [0, 0.20] với n_trials=40 (dung sai MC rộng)
    assert rate <= 0.20, f"size phình: {rate:.2f} bác bỏ dưới null (kỳ vọng ~0.05)"


def test_power_detects_real_effect():
    """Sinh y = 0.5 x + noise (hiệu ứng THẬT). Động cơ phải bác bỏ null."""
    from gpr_engine.econometrics.sca_engine import run_sca

    rng = np.random.default_rng(3)
    n = 250
    x = rng.standard_normal(n)
    y = 0.5 * x + rng.standard_normal(n)           # hiệu ứng rõ
    data = pd.DataFrame({"x": x, "y": y})
    specs = [_ols_spec_factory("x", "y")]
    res = run_sca(specs, data, B=300, block_len=20,
                  rng=np.random.default_rng(99), expected_sign=1)
    assert res["pvalue_stouffer"] < 0.05, "không phát hiện hiệu ứng thật (power kém)"
    assert res["observed"]["median_coef"] > 0.3
