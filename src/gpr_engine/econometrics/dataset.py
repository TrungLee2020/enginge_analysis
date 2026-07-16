"""dataset.py — chuan bi du lieu cho cascade 3 tang (G2).

Xem docs/06 §2.2, docs/07 §0 (quy uoc bien doi bat buoc).

Hai nhom ham:
  - PURE (transform, khong I/O): log1p_gpr, dlog, transform_global_macro,
    fill_weekend, align_frames. Test duoc khong can PG.
  - I/O: load_series, load_global_macro doc tu ext_series (PostgreSQL long format).

Quy uoc bat buoc:
  - Moi chi so GPR vao hoi quy: log(1+GPR)  (phan phoi lech phai manh).
  - Gia tai san (Oil, DXY): log-difference (Δln).
  - VIX: giu level. US10Y: sai phan (diff, don vi %).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# series_id trong ext_series -> ten cot chuan hoa noi bo
GLOBAL_MACRO_SERIES = {
    "BRENT": "oil",
    "DXY": "dxy",
    "VIX": "vix",
    "US10Y": "us10y",
}


# ---------------------------------------------------------------------------
# PURE transforms
# ---------------------------------------------------------------------------
def log1p_gpr(s: pd.Series) -> pd.Series:
    """log(1+GPR) — quy uoc bat buoc (docs/07 §0)."""
    return np.log1p(s)


def dlog(s: pd.Series) -> pd.Series:
    """Log-difference (log-return) cho gia tai san."""
    return np.log(s).diff()


def transform_global_macro(raw: pd.DataFrame) -> pd.DataFrame:
    """raw wide co cot BRENT/DXY/VIX/US10Y -> {oil, dxy, vix, us10y} da transform.

    - Oil, DXY: Δln (log-return).
    - VIX: giu level.
    - US10Y: sai phan (thay doi yield, don vi %).
    """
    out = pd.DataFrame(index=raw.index)
    if "BRENT" in raw:
        out["oil"] = dlog(raw["BRENT"])
    if "DXY" in raw:
        out["dxy"] = dlog(raw["DXY"])
    if "VIX" in raw:
        out["vix"] = raw["VIX"]
    if "US10Y" in raw:
        out["us10y"] = raw["US10Y"].diff()
    return out


def fill_weekend(gpr: pd.Series, trading_days) -> pd.Series:
    """Gan GPR ngay nghi vao ngay giao dich KE TIEP (docs/05 G2.1, cach AI-GPR xu ly).

    Voi moi ngay giao dich, lay TRUNG BINH GPR cua no va cac ngay nghi lien truoc
    (ke tu ngay giao dich truoc do). Tra ve series chi tren trading_days.
    """
    trading = pd.DatetimeIndex(pd.to_datetime(trading_days)).sort_values()
    g = gpr.copy()
    g.index = pd.to_datetime(g.index)
    g = g.sort_index()

    out = {}
    prev = None
    for d in trading:
        if prev is None:
            window = g.loc[g.index <= d]
        else:
            window = g.loc[(g.index > prev) & (g.index <= d)]
        out[d] = window.mean() if len(window) else np.nan
        prev = d
    return pd.Series(out).reindex(trading)


def align_frames(*frames: pd.DataFrame, how: str = "inner") -> pd.DataFrame:
    """Gop nhieu DataFrame theo index thoi gian (join). Giu thu tu cot."""
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.join(f, how=how)
    return out


# ---------------------------------------------------------------------------
# I/O — doc tu ext_series (PostgreSQL, long format)
# ---------------------------------------------------------------------------
def load_series(dsn: str, series_ids: list[str], freq: str | None = None,
                as_of: str | pd.Timestamp | None = None,
                data_version: str = "v1") -> pd.DataFrame:
    """Doc cac series_id tu ext_series -> DataFrame wide, index=date.

    Moi cot la mot series_id (gia tri tho, chua transform).

    as_of: neu dat, chi tra ve du lieu da biet tinh den thoi diem do
      (available_at <= as_of) — dung cho backtest/point-in-time. Bo trong = lay
      toan bo (chi dung cho phan tich hoi cuu, KHONG dung de sinh tin hieu).
      Xem docs/08 §4.7, docs/09 §2.8: loc theo `date` thay vi `available_at`
      la look-ahead bias.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(dsn)
    clauses = ["series_id = ANY(:ids)", "data_version = :data_version"]
    params: dict = {"ids": series_ids, "data_version": data_version}
    if freq:
        clauses.append("freq = :freq")
        params["freq"] = freq
    if as_of is not None:
        clauses.append("available_at <= :as_of")
        params["as_of"] = pd.Timestamp(as_of, tz="UTC") if pd.Timestamp(as_of).tzinfo is None \
            else pd.Timestamp(as_of)
    q = text(f"""
        SELECT series_id, date, value
        FROM ext_series
        WHERE {' AND '.join(clauses)}
        ORDER BY date
    """)
    with engine.connect() as conn:
        long = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    wide = long.pivot(index="date", columns="series_id", values="value")
    wide.columns.name = None
    return wide.sort_index()


def load_global_macro(dsn: str, as_of: str | pd.Timestamp | None = None,
                      data_version: str = "v1") -> pd.DataFrame:
    """Doc Oil/DXY/VIX/US10Y tu ext_series va transform (tang 2).

    Returns DataFrame {oil, dxy, vix, us10y} da transform, index=date.
    as_of: xem load_series — point-in-time cho backtest.
    """
    raw = load_series(dsn, list(GLOBAL_MACRO_SERIES.keys()), freq="daily",
                      as_of=as_of, data_version=data_version)
    return transform_global_macro(raw)
