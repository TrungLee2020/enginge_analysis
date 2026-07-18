"""data_files.py — nap du lieu OFFLINE (file + FRED) cho research cascade. 🔬

Day la ban song song file-based cua dataset.load_global_macro (vốn doc tu
PostgreSQL). G2a la research offline (docs/05), khong bat buoc co PG — module
nay doc GPR daily tu data/*.xls va keo Oil/DXY/VIX/US10Y tu FRED, cache lai CSV
de chay lai khong can mang.

Transform van dung dataset.transform_global_macro / log1p_gpr — KHONG lap lai
quy uoc bien doi (docs/07 §0). Chi khac nguon I/O.

Khong dung trong production. Production di qua ext_series (dataset.load_*).
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from ..ingest.gpr_daily import SERIES as GPR_DAILY_SERIES
from ..ingest.market_data import FRED_MAP
from .dataset import log1p_gpr, transform_global_macro

DEFAULT_GPR_DAILY = "data/data_gpr_daily_recent.xls"
DEFAULT_CACHE_DIR = "data/cache"

# Cac macro dua vao tang 2 mac dinh — DU 4 KENH global.
#   - dxy dung chuoi NOI DAI (load_dxy_spliced): DTWEXM (major, 1973->2019) noi
#     DTWEXBGS (broad, 2006->) o cap return, phu 1990+ (overlap corr Δln=0.926).
#     Nho vay dxy khong con cat mau nhu ban broad-only 2006+.
CORE_MACRO = ["oil", "dxy", "vix", "us10y"]


# ---------------------------------------------------------------------------
# GPR daily tu file
# ---------------------------------------------------------------------------
def load_gpr_daily(path: str = DEFAULT_GPR_DAILY) -> pd.DataFrame:
    """Doc GPRD/GPRD_ACT/GPRD_THREAT tu file -> wide, index=date (DatetimeIndex).

    Dung dung parser cua ingest.gpr_daily (guard cot thieu). Gia tri THO,
    chua transform.
    """
    df = pd.read_excel(path, sheet_name="Sheet1", header=0)
    missing = [c for c in [*GPR_DAILY_SERIES, "date"] if c not in df.columns]
    if missing:
        raise ValueError(
            f"File thieu cot bat buoc: {missing}. Cot hien co: {list(df.columns)}")
    df = df[["date", *GPR_DAILY_SERIES]].dropna(subset=["date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def transform_gpr_shocks(gpr_wide: pd.DataFrame, method: str = "zscore") -> pd.DataFrame:
    """Bien doi shock GPR daily cho hoi quy tang 2. Giu ten cot goc.

    method:
      - "innovation" (G2.0, docs/07v2 §2.0): shock = LEVEL − Ê_{t-1}[LEVEL], AR(p)
        rolling one-step (p chon bang AIC tren dev window). Day la SHOCK HOP LE cho
        hoi quy tang 2 (CLAUDE.md #9). Cot giu ten goc (GPRD -> GPRD la innovation).
      - "zscore" (LEVEL, doi chung): chuan hoa (x-mean)/std. GPRD ~ 10..370, γ doc la
        "phan ung / 1 do lech chuan". La LEVEL -> run_tier2 tu danh dau INELIGIBLE (#9).
      - "log1p": log(1+GPR). Quy uoc docs/07 §0 danh RIENG cho country-GPR nuoc nho
        (mean/std ≈ 0.05, lech phai manh). Ap len GPRD toan cau se ep 370→5.9, lam
        phang spike khung hoang -> KHONG dung cho daily global. Giu tuy chon de tuong thich.

    Tai sao khong log1p GPRD: docs/07 §0 bien minh log1p bang phan phoi country-GPR
    nuoc nho; GPRD daily khong thuoc phan phoi do. Standardize giu duoc bien do spike.
    """
    if method == "innovation":
        # innovation() log1p GPR thanh LEVEL roi tru persistent; ap tung cot, order/AIC.
        from .shocks import innovation
        return gpr_wide.apply(lambda col: innovation(col))
    if method == "log1p":
        return gpr_wide.apply(log1p_gpr)
    if method == "zscore":
        return (gpr_wide - gpr_wide.mean()) / gpr_wide.std()
    raise ValueError(
        f"method khong ho tro: {method!r} (dung 'innovation' | 'zscore' | 'log1p')")


# ---------------------------------------------------------------------------
# Macro tu FRED (co cache)
# ---------------------------------------------------------------------------
def _cache_path(cache_dir: str) -> Path:
    return Path(cache_dir) / "global_macro_raw.csv"


def load_global_macro_fred(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Keo Oil(BRENT)/DXY/VIX/US10Y tu FRED (raw, chua transform), co cache CSV.

    refresh=False va cache ton tai -> doc cache (khong goi mang).
    Tra ve wide raw: cot BRENT/DXY/VIX/US10Y, index=date.
    """
    cache = _cache_path(cache_dir)
    if cache.exists() and not refresh:
        raw = pd.read_csv(cache, parse_dates=["date"]).set_index("date").sort_index()
        return raw

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    cols = {}
    for sid, code in FRED_MAP.items():
        s = pdr.DataReader(code, "fred", start, end)[code]
        cols[sid] = s
    raw = pd.DataFrame(cols)
    raw.index.name = "date"
    raw = raw.sort_index()

    cache.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(cache)
    return raw


# FRED code cho DXY nối dài. DTWEXBGS chi 2006+; DTWEXM (major currencies)
# 1973 -> 2019-12 (FRED ngung cap nhat). Noi o CAP RETURN (Δln): broad uu tien
# khi co, fallback major. Overlap 2006-2019 corr(Δln)=0.926 -> splice hop le.
FRED_DXY_BROAD = "DTWEXBGS"
FRED_DXY_MAJOR = "DTWEXM"


def _dxy_cache(cache_dir: str) -> Path:
    return Path(cache_dir) / "dxy_spliced_raw.csv"


def splice_dxy_returns(broad: pd.Series, major: pd.Series) -> pd.Series:
    """Ghep Δln DXY: broad uu tien, fallback major. PURE (test khong can mang).

    broad/major la MUC (level) tho. Ghep o cap return vi hai ro tien khac muc.
    """
    r_broad = np.log(broad.dropna()).diff()
    r_major = np.log(major.dropna()).diff()
    idx = r_broad.index.union(r_major.index)
    dxy = r_broad.reindex(idx)
    dxy[dxy.isna()] = r_major.reindex(idx)[dxy.isna()]  # fallback major
    dxy = dxy.dropna().rename("dxy")
    dxy.index.name = "date"
    return dxy


def load_dxy_spliced(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.Series:
    """Δln DXY noi dai (major<->broad) — Series ten 'dxy', index=date.

    Tra ve TRUC TIEP log-return (da transform), vi hai ro tien khac muc nen khong
    the ghep muc; ghep return moi hop ly. broad uu tien, fallback major.
    """
    cache = _dxy_cache(cache_dir)
    if cache.exists() and not refresh:
        s = pd.read_csv(cache, parse_dates=["date"]).set_index("date")["dxy"]
        return s.sort_index()

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    broad = pdr.DataReader(FRED_DXY_BROAD, "fred", start, end)[FRED_DXY_BROAD]
    major = pdr.DataReader(FRED_DXY_MAJOR, "fred", start, end)[FRED_DXY_MAJOR]
    dxy = splice_dxy_returns(broad, major)

    cache.parent.mkdir(parents=True, exist_ok=True)
    dxy.to_frame().to_csv(cache)
    return dxy


def load_macro_transformed(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    dxy_spliced: bool = True,
) -> pd.DataFrame:
    """FRED raw -> {oil, dxy, vix, us10y} da transform (dataset.transform_global_macro).

    dxy_spliced=True: thay cot dxy bang chuoi noi dai major<->broad (1985+ thay vi
    chi 2006+). False: giu dxy = Δln DTWEXBGS (chi 2006+).
    """
    raw = load_global_macro_fred(start, end, cache_dir, refresh)
    out = transform_global_macro(raw)
    if dxy_spliced:
        out["dxy"] = load_dxy_spliced(start, end, cache_dir, refresh).reindex(out.index)
    return out


# ---------------------------------------------------------------------------
# Panel hop nhat cho tang 2
# ---------------------------------------------------------------------------
def build_tier2_panel(
    gpr_path: str = DEFAULT_GPR_DAILY,
    start: str = "1990-01-02",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    macro_vars: Iterable[str] = CORE_MACRO,
    shock_method: str = "zscore",
    ffill_limit: int = 3,
) -> pd.DataFrame:
    """Panel san sang cho estimate_tier2, tren LUOI NGAY GIAO DICH LIEN TUC.

    Vi sao khong join "inner" tho: GPRD la ngay lich, macro la business day, va
    cac chuoi FRED thua ngay le khac nhau -> panel co NaN rai rac. estimate_tier2
    dropna THEO TUNG horizon nen moi horizon chay tren mau khac nhau (lech uoc
    luong) va shift(k) cho AR-lag vuot qua khe NaN. Sua: dung luoi bdate lien tuc,
    ffill macro toi da ffill_limit ngay (le/holiday), roi complete-case 1 lan.

    Params
    ------
    macro_vars : cac kenh macro dua vao (mac dinh CORE_MACRO = du 4 kenh; dxy da noi dai).
    shock_method : "zscore" (mac dinh, cho GPRD toan cau) | "log1p".
    ffill_limit : so ngay toi da ffill gia tri macro qua ngay le.

    Truc thoi gian la bdate_range lien tuc -> shift(k) = dung 1 ngay giao dich.
    """
    gpr_raw = load_gpr_daily(gpr_path)
    gpr = transform_gpr_shocks(gpr_raw, method=shock_method)
    macro = load_macro_transformed(start, end, cache_dir, refresh)

    cols = [c for c in macro_vars if c in macro.columns]
    macro = macro[cols]

    end_ts = pd.Timestamp(end) if end else max(macro.index.max(), gpr.index.max())
    grid = pd.bdate_range(pd.Timestamp(start), end_ts)

    macro_g = macro.reindex(grid).ffill(limit=ffill_limit)
    gpr_g = gpr.reindex(grid).ffill(limit=ffill_limit)

    panel = macro_g.join(gpr_g, how="inner").sort_index()
    # Complete-case 1 lan -> moi horizon dung cung mau, AR-lag khong vuot NaN.
    return panel.dropna()
