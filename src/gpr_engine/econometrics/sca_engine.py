"""sca_engine.py — Động cơ Specification Curve Analysis (docs/12 §3). 🔬

Deliverable trung tâm của docs/12. Suy diễn CHUNG trên toàn tập spec bằng resampling
(SSN2020, Nature Human Behaviour 4:1208), điều chỉnh cho chuỗi thời gian bằng
moving-block bootstrap.

AGNOSTIC với LP: một spec là callable `spec(data, row_idx) -> (coef, pvalue)`. Động
cơ không biết bên trong là OLS hay quantile — nhờ vậy KIỂM ĐỊNH ĐƯỢC size/power trên
dữ liệu mô phỏng với spec OLS đơn giản trước khi tin trên lưới LP thật (docs/13 §5:
ℓ là phán đoán chưa kiểm; moving-block trên chuỗi dai dẳng dễ sai size; chỉ có 1 lần
chạy trung thực trên dữ liệu thật).

Ba thống kê toàn đường cong (§3.1, báo cáo cả ba):
  T1 median_coef      — trung vị hệ số trên K spec
  T2 share_significant — tỉ lệ spec có ý nghĩa ĐÚNG CHIỀU (dominant sign, §3.4)
  T3 stouffer_z        — gộp p-value liên tục (tránh nhị phân hóa)

Null (§3.2, 6 bước SSN2020 cho dữ liệu quan sát):
  1. Ước lượng K spec trên dữ liệu thật -> K hệ số b̂_k.
  2. Tạo y* dưới null (ở đây: resample phá liên kết x-y, giữ phân phối biên +
     cấu trúc thời gian qua moving-block — tương đương "hiệu ứng thật = 0").
  3-4. Moving-block resample CÙNG bộ hàng cho mọi spec; ước lượng lại.
  5. Lặp B lần (chốt trước).
  6. p-value = % curve null cực đoan ít nhất bằng curve quan sát.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
from scipy import stats as _stats

Spec = Callable[[pd.DataFrame, np.ndarray], tuple[float, float]]


# ---------------------------------------------------------------------------
# Moving-block bootstrap
# ---------------------------------------------------------------------------
def moving_block_indices(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """Sinh N chỉ số bằng moving-block bootstrap (Künsch 1989).

    Rút các khối liên tiếp độ dài block_len (điểm bắt đầu ngẫu nhiên, có hoàn lại),
    nối tới khi đủ n. Giữ cấu trúc phụ thuộc thời gian bên trong mỗi khối — bước 3
    của SSN2020 rút hàng độc lập sẽ phá cấu trúc đó (docs/12 §3.2).
    """
    if block_len < 1 or block_len > n:
        raise ValueError(f"block_len {block_len} không hợp lệ với n={n}")
    n_blocks = int(np.ceil(n / block_len))
    max_start = n - block_len
    starts = rng.integers(0, max_start + 1, size=n_blocks)
    idx = np.concatenate([np.arange(s, s + block_len) for s in starts])
    return idx[:n]


# ---------------------------------------------------------------------------
# Ba thống kê
# ---------------------------------------------------------------------------
def dominant_sign_share(coefs: np.ndarray) -> tuple[float, int]:
    """(tỉ lệ spec cùng DẤU TRỘI, dấu trội). §3.4: báo cáo theo dấu trội vì spec
    không độc lập nên kể cả dưới null cũng không kỳ vọng 50/50."""
    coefs = np.asarray(coefs)
    n_pos = int(np.sum(coefs > 0))
    n_neg = int(np.sum(coefs < 0))
    sign = 1 if n_pos >= n_neg else -1
    share = (n_pos if sign == 1 else n_neg) / len(coefs)
    return float(share), sign


def stouffer_z(pvalues: np.ndarray, signs: np.ndarray) -> float:
    """Stouffer Z (§3.1 T3): gộp p-value liên tục. z_k = Φ⁻¹(1−p_k/2)·sign_k, trả
    trung bình z / √K (giữ đơn vị Z). Tránh nhị phân hóa tùy tiện của T2."""
    p = np.clip(np.asarray(pvalues, dtype=float), 1e-12, 1 - 1e-12)
    signs = np.asarray(signs, dtype=float)
    z_one_sided = _stats.norm.ppf(1 - p / 2.0)     # độ lớn
    z = z_one_sided * signs
    return float(np.sum(z) / np.sqrt(len(z)))


def sca_statistics(coefs: np.ndarray, pvalues: np.ndarray, signs: np.ndarray,
                   alpha: float = 0.05, expected_sign: int | None = None) -> dict:
    """T1/T2/T3 cho một curve (một tập K hệ số)."""
    coefs = np.asarray(coefs, dtype=float)
    pvalues = np.asarray(pvalues, dtype=float)
    signs = np.asarray(signs, dtype=float)

    share, dom_sign = dominant_sign_share(coefs)
    # T2: tỉ lệ có ý nghĩa ĐÚNG CHIỀU. expected_sign=None -> dùng dấu trội.
    target = expected_sign if expected_sign is not None else dom_sign
    sig_right_dir = np.mean((pvalues < alpha) & (np.sign(coefs) == target))
    return {
        "median_coef": float(np.median(coefs)),
        "share_significant": float(sig_right_dir),
        "stouffer_z": stouffer_z(pvalues, signs),
        "dominant_sign": dom_sign,
        "dominant_share": share,
        "n_spec": len(coefs),
    }


# ---------------------------------------------------------------------------
# Ước lượng curve
# ---------------------------------------------------------------------------
def fit_curve(specs: Sequence[Spec], data: pd.DataFrame,
              idx: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Ước lượng mọi spec trên (data trên hàng idx). Trả (coefs, pvalues)."""
    if idx is None:
        idx = np.arange(len(data))
    coefs = np.empty(len(specs))
    pvals = np.empty(len(specs))
    for k, spec in enumerate(specs):
        coefs[k], pvals[k] = spec(data, idx)
    return coefs, pvals


def run_sca(specs: Sequence[Spec], data: pd.DataFrame, B: int = 1000,
            block_len: int = 12, rng: np.random.Generator | None = None,
            alpha: float = 0.05, expected_sign: int | None = None,
            outcome_col: str = "y") -> dict:
    """Chạy SCA đầy đủ: curve quan sát + phân phối null + p-value 3 thống kê.

    Null ĐÚNG NGHĨA SSN2020 bước 2 (hiệu ứng thật = 0): PHÁ liên kết chéo shock↔outcome
    mà GIỮ phân phối biên + tự tương quan của cả hai. Cách làm agnostic-với-spec:
    moving-block resample RIÊNG cột `outcome_col` (block-shuffle theo thời gian), giữ
    các cột shock ở index gốc. Curve null vì thế = "outcome không liên quan shock" —
    KHÁC hẳn resample cả hàng cùng nhau (giữ nguyên liên kết → null sai, mất power).

    p-value = tỉ lệ thống kê null cực đoan ≥ quan sát.
    Trả dict: observed (3 thống kê) + pvalue_median/pvalue_share/pvalue_stouffer.
    """
    rng = rng or np.random.default_rng(0)
    n = len(data)
    if outcome_col not in data.columns:
        raise KeyError(f"outcome_col {outcome_col!r} không có trong data (cột: {list(data.columns)})")
    identity = np.arange(n)

    obs_coefs, obs_pvals = fit_curve(specs, data)
    obs_signs = np.sign(obs_coefs)
    observed = sca_statistics(obs_coefs, obs_pvals, obs_signs, alpha, expected_sign)

    null_median = np.empty(B)
    null_share = np.empty(B)
    null_stouffer = np.empty(B)
    y_orig = data[outcome_col].to_numpy()
    for b in range(B):
        # moving-block CHỈ trên outcome -> phá quan hệ, giữ autocorr của y
        y_idx = moving_block_indices(n, block_len, rng)
        data_null = data.copy()
        data_null[outcome_col] = y_orig[y_idx]
        c, p = fit_curve(specs, data_null, identity)
        s = sca_statistics(c, p, np.sign(c), alpha, expected_sign)
        null_median[b] = s["median_coef"]
        null_share[b] = s["share_significant"]
        null_stouffer[b] = s["stouffer_z"]

    # p-value hai phía cho median & stouffer (đối xứng quanh 0 dưới null);
    # share là một phía (càng cao càng cực đoan).
    def two_sided(null_dist: np.ndarray, obs: float) -> float:
        return float(np.mean(np.abs(null_dist) >= abs(obs)))

    def one_sided(null_dist: np.ndarray, obs: float) -> float:
        return float(np.mean(null_dist >= obs))

    return {
        "observed": observed,
        "pvalue_median": two_sided(null_median, observed["median_coef"]),
        "pvalue_share": one_sided(null_share, observed["share_significant"]),
        "pvalue_stouffer": two_sided(null_stouffer, observed["stouffer_z"]),
        "B": B,
        "block_len": block_len,
        "n_spec": len(specs),
    }


__all__ = [
    "moving_block_indices",
    "dominant_sign_share",
    "stouffer_z",
    "sca_statistics",
    "fit_curve",
    "run_sca",
]
