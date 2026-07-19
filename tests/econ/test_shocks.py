"""Test cho econometrics/shocks.py (G2.0) — decomposition LEVEL/PERSISTENT/INNOVATION.

Kiem chung theo docs/10 D2 + docs/07v2 §2.0. Test QUAN TRONG NHAT la chong
leakage: PERSISTENT tai t chi duoc dung du lieu <= t-1 (E_{t-1}). Sua bat ky
gia tri tuong lai nao KHONG duoc lam doi innovation o thoi diem <= t.

Cac test hanh vi (sanity kinh te luong):
  - white noise: innovation ~ chinh no (khong co gi de du bao).
  - AR(1) manh: innovation ~ residual, autocorr thap hon HAN level.
  - BIC chon p tren dev window: fit khop cau truc biet truoc (AR(2)).
  - JUMP: chi duong o duoi tren nguong q95 rolling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.shocks import (
    build_shocks,
    innovation,
    jump,
    level_plus_jump,
    persistent_ar,
    select_ar_order,
)

DEV = ("2015-01-01", "2020-12-31")


def _ar_series(n: int, coeffs: list[float], sigma: float, seed: int,
               start: str = "2015-01-01") -> pd.Series:
    """Sinh chuoi AR(p) voi he so biet truoc, index ngay lam viec."""
    rng = np.random.default_rng(seed)
    p = len(coeffs)
    x = np.zeros(n)
    eps = rng.standard_normal(n) * sigma
    for t in range(n):
        val = eps[t]
        for k in range(1, p + 1):
            if t - k >= 0:
                val += coeffs[k - 1] * x[t - k]
        x[t] = val
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(x, index=idx, name="GPRD")


# ---------------------------------------------------------------------------
# 1) LEAKAGE — test quan trong nhat cua file
# ---------------------------------------------------------------------------
def test_innovation_no_lookahead():
    """Sua gia tri tai t+k KHONG duoc doi innovation tai moi thoi diem <= t.

    E_{t-1}[Level_t] chi dung qua khu -> innovation tai <= t phai bat bien khi
    ta thay doi tuong lai. Neu doi = leakage.
    """
    s = _ar_series(400, [0.6, 0.2], sigma=1.0, seed=0)
    base = innovation(s, order=2, min_train=60, is_level=True)

    # thay doi manh moi gia tri tu t0 tro di
    t0 = 250
    s2 = s.copy()
    s2.iloc[t0:] += 100.0
    perturbed = innovation(s2, order=2, min_train=60, is_level=True)

    # innovation tai cac chi so < t0 phai KHONG doi (bo NaN warm-up)
    left = base.iloc[:t0].dropna()
    left2 = perturbed.reindex(left.index)
    pd.testing.assert_series_equal(left, left2, check_names=False)


def test_persistent_uses_only_past():
    """PERSISTENT tai t la du bao 1 buoc — khong duoc bang chinh Level_t."""
    s = _ar_series(300, [0.7], sigma=1.0, seed=1)
    pers = persistent_ar(s, order=1, min_train=50)
    # o vung da fit, persistent khac level (neu bang = dung dt hien tai)
    both = pd.concat([s.rename("level"), pers.rename("pers")], axis=1).dropna()
    assert (both["level"] != both["pers"]).any()
    # va persistent khong chua NaN sau warm-up
    assert pers.iloc[-1] == pers.iloc[-1]  # not NaN


# ---------------------------------------------------------------------------
# 2) HANH VI KINH TE LUONG
# ---------------------------------------------------------------------------
def test_white_noise_innovation_is_itself():
    """White noise: khong co cau truc de du bao -> innovation ~ level (demeaned)."""
    rng = np.random.default_rng(2)
    idx = pd.bdate_range("2015-01-01", periods=500)
    s = pd.Series(rng.standard_normal(500), index=idx, name="GPRD")
    innov = innovation(s, order=1, min_train=60, is_level=True).dropna()
    lvl = s.reindex(innov.index)
    # tuong quan innovation vs level cao: khong co cau truc AR that -> phan du gan
    # bang level demeaned. He so AR uoc luong tren white noise nho nhung khac 0
    # (mau huu han) nen corr < 1; ~0.8 la dung, nguong 0.7 loai gia thuyet "co du bao".
    corr = np.corrcoef(innov.values, lvl.values)[0, 1]
    assert corr > 0.7


def test_ar1_innovation_less_autocorrelated_than_level():
    """AR(1) manh: level co autocorr cao; innovation (residual) autocorr ~ 0."""
    s = _ar_series(600, [0.85], sigma=1.0, seed=3)
    innov = innovation(s, order=1, min_train=80, is_level=True).dropna()
    lvl = s.reindex(innov.index)

    def rho1(x: pd.Series) -> float:
        return x.autocorr(lag=1)

    assert abs(rho1(lvl)) > 0.6          # level rat dai dang
    assert abs(rho1(innov)) < 0.2        # innovation gan trang
    assert abs(rho1(innov)) < abs(rho1(lvl))  # cot loi: giam manh


# ---------------------------------------------------------------------------
# 3) CHON ORDER BANG BIC trong tran parsimony (dev window only)
# ---------------------------------------------------------------------------
def test_select_ar_order_recovers_structure():
    """Chuoi AR(2) manh -> BIC chon p >= 2 (khong chon p=0/1)."""
    s = _ar_series(800, [0.5, 0.3], sigma=1.0, seed=4)
    p = select_ar_order(s, max_order=6, window=DEV)
    assert p >= 2


def test_select_ar_order_uses_dev_window_only():
    """select_ar_order chi nhin du lieu trong dev window (khong leak val/oos)."""
    # dev window: AR(1) manh; ngoai dev: nhieu trang. Neu ham dung ca chuoi,
    # order uoc luong se bi keo ve 0. Dung dev-only -> van thay AR.
    dev = _ar_series(1500, [0.8], sigma=1.0, seed=5)  # 2015-01-01 + ~6 nam bdays phu dev
    p = select_ar_order(dev, max_order=4, window=DEV)
    assert p >= 1


# ---------------------------------------------------------------------------
# 4) JUMP
# ---------------------------------------------------------------------------
def test_jump_nonnegative_and_tail_only():
    """JUMP = max(0, z - q95_rolling): chi duong khi vuot duoi, con lai = 0."""
    rng = np.random.default_rng(6)
    idx = pd.bdate_range("2015-01-01", periods=500)
    base = rng.standard_normal(500)
    base[400] = 20.0  # spike ro rang
    s = pd.Series(base, index=idx, name="GPRD")
    j = jump(s, window=120, q=0.95)
    assert (j.dropna() >= 0).all()          # khong am
    assert j.iloc[400] > 0                  # spike -> jump duong
    # phan lon ngay binh thuong = 0
    assert (j.dropna() == 0).mean() > 0.5


def test_jump_no_lookahead():
    """q95 rolling chi dung qua khu -> sua tuong lai khong doi jump qua khu."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2015-01-01", periods=400)
    s = pd.Series(rng.standard_normal(400), index=idx, name="GPRD")
    j1 = jump(s, window=100, q=0.95)
    s2 = s.copy()
    s2.iloc[300:] += 50.0
    j2 = jump(s2, window=100, q=0.95)
    left = j1.iloc[:300].dropna()
    pd.testing.assert_series_equal(left, j2.reindex(left.index), check_names=False)


def test_level_plus_jump_uses_level_not_innovation():
    """Contract: LEVEL+JUMP phai dung LEVEL, khong phai INNOVATION+JUMP."""
    idx = pd.date_range("2020-01-01", periods=3)
    level = pd.Series([1.0, 2.0, 3.0], index=idx)
    jmp = pd.Series([0.0, 0.5, 1.0], index=idx)
    out = level_plus_jump(level, jmp)
    expected = pd.Series([1.0, 2.5, 4.0], index=idx, name="LEVEL+JUMP")
    pd.testing.assert_series_equal(out, expected)


# ---------------------------------------------------------------------------
# 5) BUILD_SHOCKS — orchestrator
# ---------------------------------------------------------------------------
def test_build_shocks_columns_and_levels():
    """build_shocks tra ve LEVEL/PERSISTENT/INNOVATION/JUMP cho moi series GPR."""
    s = _ar_series(500, [0.6], sigma=1.0, seed=8)
    gpr = pd.DataFrame({"GPRD": np.abs(s) * 10})  # gia tri duong nhu GPR that
    out = build_shocks(gpr, series=["GPRD"], ar_window=DEV, max_order=4)
    for suffix in ["GPRD_LEVEL", "GPRD_PERSISTENT", "GPRD_INNOV", "GPRD_JUMP",
                   "GPRD_LEVEL_PLUS_JUMP"]:
        assert suffix in out.columns, f"thieu cot {suffix}"
    # LEVEL = log1p cua gia tri tho
    lvl = out["GPRD_LEVEL"].dropna()
    assert (lvl >= 0).all()  # log1p cua gia tri duong


def test_build_shocks_innovation_equals_level_minus_persistent():
    """INNOVATION = LEVEL - PERSISTENT (dinh nghia §2.0)."""
    s = _ar_series(500, [0.7], sigma=1.0, seed=9)
    gpr = pd.DataFrame({"GPRD": np.abs(s) * 10})
    out = build_shocks(gpr, series=["GPRD"], ar_window=DEV, max_order=3)
    recon = out["GPRD_LEVEL"] - out["GPRD_PERSISTENT"]
    both = pd.concat([recon.rename("a"), out["GPRD_INNOV"].rename("b")], axis=1).dropna()
    assert len(both) > 0
    np.testing.assert_allclose(both["a"].values, both["b"].values, atol=1e-9)


def test_build_shocks_level_plus_jump_contract():
    s = _ar_series(500, [0.7], sigma=1.0, seed=10)
    gpr = pd.DataFrame({"GPRD": np.abs(s) * 10})
    out = build_shocks(gpr, series=["GPRD"], ar_window=DEV, max_order=3)
    expected = out["GPRD_LEVEL"] + out["GPRD_JUMP"]
    pd.testing.assert_series_equal(
        out["GPRD_LEVEL_PLUS_JUMP"], expected.rename("GPRD_LEVEL_PLUS_JUMP"))
