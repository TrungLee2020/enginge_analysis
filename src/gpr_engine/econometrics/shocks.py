"""shocks.py — G2.0: LEVEL ≠ SHOCK. Decomposition bat buoc truoc moi hoi quy. 🔬

docs/07v2 §2.0, docs/10 D2. Day la MAU CHOT chan moi buoc sau (D3 G2a rerun,
D4 G2b). Nguyen tac #9 (CLAUDE.md): shock la INNOVATION, khong phai level.

Sau bien (tat ca ROLLING, chi dung qua khu — no leakage):
    LEVEL       = ln(1+GPR)                          (giu doi chung, KHONG vao hoi quy shock)
    PERSISTENT  = Ê_{t-1}[LEVEL]   (AR(p) one-step forecast, p chon bang AIC/dev window)
    INNOVATION  = LEVEL − PERSISTENT                 ← shock chinh
    JUMP        = max(0, z_t − q95_rolling)          (duoi, su kien cuc doan)
    GPT_INNOV   = INNOVATION rieng cho threats (GPRD_THREAT)
    GPA_SURPRISE_V1 = GPA − Ê[GPA | GPT lags, GPA lags]   (surrogate, xem ghi chu)

Ky luat chong data-snooping (docs/10 §5): order p cua AR chon bang AIC TREN
DEVELOPMENT WINDOW ONLY (2015-2020), roi KHOA. Khong thu nhieu spec roi chon
cai dep tren toan mau.

PERSISTENT dung AR(p) (khong EWMA) — quyet dinh 2026-07-18: chuan kinh te luong
hon, order chon bang AIC. EWMA giu lam phuong an doi chung neu can sau.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg

from .dataset import log1p_gpr

# Development window (config/backtest.yaml split.development) — AIC chi nhin day.
DEV_WINDOW = ("2015-01-01", "2020-12-31")


# ---------------------------------------------------------------------------
# Chon order AR bang BIC trong tran parsimony (dev window only)
# ---------------------------------------------------------------------------
# Tai sao TRAN p=5 + BIC (chot 2026-07-18 sau robustness, docs/g0 §1.1):
#   - AIC/BIC KHONG co cuc tieu noi voi GPR daily: tu tuong quan duoi dai (regime)
#     day argmin AIC->20+, BIC->14-16. De tieu chi tu do chon = de no duoi bien,
#     spec khong on dinh + snooping order.
#   - Nhung INNOVATION do duoc DA ON DINH tu p~6: corr(innov_p8, innov_p10)=0.99,
#     autocorr innovation ~0.03-0.04 o moi order tu 4..16 -> muc tieu (khu phan da
#     du bao) dat roi, them lag khong doi ket qua thuc chat.
#   - Tran p=5 (1 tuan giao dich) co DIEN GIAI kinh te ("tin trong tuan vua roi"),
#     du khu autocorr (rho1~0.04 tu p=4). BIC phat nang hon AIC -> uu tien parsimony
#     trong tran. Cac lag regime bac cao con lai LP tang 2 kiem soat bang macro-lags.
DEFAULT_MAX_ORDER = 5


def select_ar_order(
    level: pd.Series,
    max_order: int = DEFAULT_MAX_ORDER,
    window: tuple[str, str] = DEV_WINDOW,
    criterion: str = "bic",
) -> int:
    """Chon p cho AR(p) bang BIC (mac dinh) trong [0, max_order], CHI tren dev window.

    Tran parsimony (max_order=5) + BIC la quyet dinh chong snooping order — xem
    ghi chu tren. criterion="aic" giu lai cho doi chung/robustness, KHONG dung
    lam spec chinh (AIC duoi bien).

    docs/10 §5 + docs/g0 §1.1: p nay pre-register trong hypothesis_registry.yaml
    TRUOC khi nhin ket qua G2a. Deterministic -> tai lap duoc.
    """
    if criterion not in ("bic", "aic"):
        raise ValueError(f"criterion phai la 'bic'|'aic', nhan {criterion!r}")
    lo, hi = window
    dev = level.loc[lo:hi].dropna()
    if len(dev) < 10:
        raise ValueError(
            f"Dev window {window} chi co {len(dev)} quan sat — khong du chon order.")
    max_order = min(max_order, max(1, len(dev) // 5))

    best_p, best_ic = 0, np.inf
    for p in range(0, max_order + 1):
        try:
            res = AutoReg(dev.values, lags=p, old_names=False).fit()
        except (ValueError, np.linalg.LinAlgError):
            continue
        ic = res.bic if criterion == "bic" else res.aic
        if ic < best_ic:
            best_ic, best_p = ic, p
    return best_p


# ---------------------------------------------------------------------------
# PERSISTENT — Ê_{t-1}[Level] bang AR(p) rolling one-step-ahead
# ---------------------------------------------------------------------------
def persistent_ar(
    level: pd.Series,
    order: int,
    min_train: int = 60,
) -> pd.Series:
    """Du bao 1 buoc E_{t-1}[Level_t] bang AR(order), EXPANDING window.

    Voi moi t (chi so >= min_train), fit AR(order) tren level[:t] (dung du lieu
    <= t-1) roi du bao level_t. KHONG BAO GIO cham level_t tro di -> no leakage.

    order=0: du bao = trung binh mau qua khu (drift-only).
    Tra ve series cung index; NaN cho vung warm-up (< min_train).
    """
    if order < 0:
        raise ValueError("order phai >= 0")
    lvl = level.dropna()
    vals = lvl.values
    n = len(vals)
    out = np.full(n, np.nan)

    start = max(min_train, order + 2)
    for t in range(start, n):
        hist = vals[:t]  # chi qua khu: level_0 .. level_{t-1}
        if order == 0:
            out[t] = hist.mean()
            continue
        try:
            res = AutoReg(hist, lags=order, old_names=False).fit()
            # du bao mot buoc tiep theo (= level_t)
            out[t] = res.predict(start=len(hist), end=len(hist))[0]
        except (ValueError, np.linalg.LinAlgError):
            out[t] = hist.mean()
    return pd.Series(out, index=lvl.index, name=level.name).reindex(level.index)


def innovation(
    level_or_raw: pd.Series,
    order: int | None = None,
    min_train: int = 60,
    max_order: int = DEFAULT_MAX_ORDER,
    window: tuple[str, str] = DEV_WINDOW,
    is_level: bool = False,
) -> pd.Series:
    """INNOVATION = LEVEL − PERSISTENT (§2.0). Shock chinh cho Local Projection.

    level_or_raw: mac dinh la GPR THO (se log1p thanh LEVEL). is_level=True neu
      da la LEVEL (bo qua log1p) — dung cho test / chuoi da bien doi.
    order: neu None, chon bang BIC trong tran parsimony (select_ar_order).
    """
    level = level_or_raw if is_level else log1p_gpr(level_or_raw)
    if order is None:
        order = select_ar_order(level, max_order=max_order, window=window)
    pers = persistent_ar(level, order=order, min_train=min_train)
    return (level - pers).rename(level.name)


# ---------------------------------------------------------------------------
# JUMP — phan duoi tren nguong q95 rolling
# ---------------------------------------------------------------------------
def jump(
    raw_or_level: pd.Series,
    window: int = 250,
    q: float = 0.95,
    min_periods: int | None = None,
) -> pd.Series:
    """JUMP_t = max(0, z_t − q_rolling), z chuan hoa rolling (chi qua khu).

    z_t = (x_t − mean_{roll}) / std_{roll} voi mean/std tinh tren cua so LUI
    (shift 1 -> khong gom x_t). q_rolling = phan vi q cua z tren cua so lui.
    Su dung shift(1) de dam bao khong nhin thay chinh minh / tuong lai.
    """
    x = raw_or_level.dropna()
    min_periods = min_periods or max(20, window // 4)

    roll = x.rolling(window, min_periods=min_periods)
    mu = roll.mean().shift(1)
    sd = roll.std().shift(1)
    z = (x - mu) / sd

    # nguong q95 cua z, tren cua so lui (khong gom z_t)
    thr = z.rolling(window, min_periods=min_periods).quantile(q).shift(1)
    j = (z - thr).clip(lower=0.0)
    return j.rename(raw_or_level.name).reindex(raw_or_level.index)


# ---------------------------------------------------------------------------
# GPA_SURPRISE_V1 — surrogate (spec day du can S-GPR + Ladder, chua ton tai)
# ---------------------------------------------------------------------------
def gpa_surprise_v1(
    gpa: pd.Series,
    gpt: pd.Series,
    k_lags: int = 5,
    min_train: int = 120,
) -> pd.Series:
    """GPA_SURPRISE_V1 = GPA − Ê[GPA | GPT_{t-1..t-k}, GPA_{t-1..t-k}] (rolling OLS).

    SURROGATE cua §2.2: spec day du condition them tren S-GPR + Escalation Ladder
    (chua ton tai — G5/G6). Ten cot mang hau to _V1 de KĐ9 sau nay khong lan hai
    spec (docs/10 D2). Ê fit rolling expanding, chi qua khu -> no leakage.
    """
    df = pd.concat([gpa.rename("gpa"), gpt.rename("gpt")], axis=1).dropna()
    n = len(df)
    lag_cols = []
    for k in range(1, k_lags + 1):
        df[f"gpa_l{k}"] = df["gpa"].shift(k)
        df[f"gpt_l{k}"] = df["gpt"].shift(k)
        lag_cols += [f"gpa_l{k}", f"gpt_l{k}"]
    df = df.dropna()
    y = df["gpa"].values
    X = np.column_stack([np.ones(len(df)), df[lag_cols].values])

    out = np.full(len(df), np.nan)
    for t in range(max(min_train, X.shape[1] + 2), len(df)):
        Xtr, ytr = X[:t], y[:t]  # chi qua khu
        beta, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
        out[t] = y[t] - X[t] @ beta
    return pd.Series(out, index=df.index, name="GPA_SURPRISE_V1").reindex(gpa.index)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def build_shocks(
    gpr_raw: pd.DataFrame,
    series: Sequence[str] = ("GPRD",),
    ar_window: tuple[str, str] = DEV_WINDOW,
    max_order: int = DEFAULT_MAX_ORDER,
    min_train: int = 60,
    jump_window: int = 250,
    orders: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Sinh <S>_LEVEL / <S>_PERSISTENT / <S>_INNOV / <S>_JUMP cho moi series.

    gpr_raw: wide, cot la GPR THO (se log1p). series: cot xu ly.
    orders: neu cho san order/series thi dung, nguoc lai chon bang BIC (dev window).
    Order da chon duoc gan vao attrs de report ghi lai (registry).

    Threats (GPRD_THREAT) -> INNOV cung la GPT_INNOV (§2.0). Khong tinh rieng ham;
    goi ten o tang panel.
    """
    orders = dict(orders or {})
    out = pd.DataFrame(index=gpr_raw.index)
    chosen: dict[str, int] = {}

    for s in series:
        if s not in gpr_raw.columns:
            raise KeyError(f"series {s!r} khong co trong gpr_raw (cot: {list(gpr_raw.columns)})")
        raw = gpr_raw[s]
        level = log1p_gpr(raw)
        p = orders.get(s)
        if p is None:
            p = select_ar_order(level, max_order=max_order, window=ar_window)
        chosen[s] = p

        pers = persistent_ar(level, order=p, min_train=min_train)
        out[f"{s}_LEVEL"] = level
        out[f"{s}_PERSISTENT"] = pers
        out[f"{s}_INNOV"] = level - pers
        out[f"{s}_JUMP"] = jump(raw, window=jump_window)

    out.attrs["ar_orders"] = chosen
    out.attrs["ar_window"] = ar_window
    return out


__all__ = [
    "DEV_WINDOW",
    "DEFAULT_MAX_ORDER",
    "select_ar_order",
    "persistent_ar",
    "innovation",
    "jump",
    "gpa_surprise_v1",
    "build_shocks",
]
