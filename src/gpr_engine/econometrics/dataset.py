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

# Nhom THANG (ingest/macro_monthly.py): outcome vi mo thuc + battery + cuoc bien.
# Ten noi bo trung khop cot ma `data_files.transform_real_macro`/
# `transform_benchmark`/`transform_freight` sinh ra, de hai duong (DB va file) ra
# cung ten cot cho tang 2.
MONTHLY_MACRO_SERIES = {
    "INDPRO": "ip",
    "CPI": "cpi",
    "INFL_EXP": "infl_exp",
    "EPU_US": "epu_us",
    "EPU_GLOBAL": "epu_global",
    "FREIGHT_PPI": "freight",
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


def fill_weekend(
    gpr: pd.Series,
    trading_days,
    *,
    aggregation: str,
) -> pd.Series:
    """Gan GPR ngay nghi vao ngay giao dich KE TIEP.

    ``aggregation`` phai duoc chot theo y nghia bien: ``mean`` cho LEVEL/INNOVATION
    va ``max`` cho JUMP. Max giu lai cu soc duoi xay ra vao cuoi tuan thay vi lam
    phang no bang trung binh. Tra ve series chi tren ``trading_days``.
    """
    if aggregation not in {"mean", "max"}:
        raise ValueError("aggregation phai la 'mean' hoac 'max'")
    trading = pd.DatetimeIndex(pd.to_datetime(trading_days)).sort_values()
    g = gpr.copy()
    g.index = pd.to_datetime(g.index)
    g = g.sort_index()

    if trading.empty:
        return pd.Series(dtype=float, index=trading)

    out = {}
    # Gioi han cua so dau tien o phien lam viec truoc do. Ban cu lay TOAN BO
    # lich su <= ngay dau tien neu caller bat dau giua mau, lam sai gia tri dau.
    prev = trading[0] - pd.offsets.BDay(1)
    for d in trading:
        window = g.loc[(g.index > prev) & (g.index <= d)]
        if len(window):
            out[d] = window.mean() if aggregation == "mean" else window.max()
        else:
            out[d] = np.nan
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
                data_version: str = "v1",
                revision_aware: bool = True) -> pd.DataFrame:
    """Doc cac series_id tu ext_series -> DataFrame wide, index=date.

    Moi cot la mot series_id (gia tri tho, chua transform).

    `data_version` mac dinh "v1" = ban CHAY (`versioning.RUNNING_VERSION`), luon
    la ban moi nhat: `ingest/versioning.py` UPSERT ngay moi + gia tri revise vao
    dung nhan nay, va chep ban CU sang nhan archive rieng. Truyen nhan archive de
    doc lai mot vintage cu.

    as_of: neu dat, chi tra ve du lieu da biet tinh den thoi diem do
      (`available_at <= as_of`) — xem docs/08 §4.7, docs/09 §2.8: loc theo `date`
      thay vi `available_at` la look-ahead bias. Bo trong = lay toan bo (phan
      tich hoi cuu, KHONG dung de sinh tin hieu).

    revision_aware (chi co tac dung khi co `as_of`): voi moi (series_id, date),
      dung GIA TRI DANG CO HIEU LUC tai `as_of` thay vi gia tri hom nay. GPR
      tinh lai hoi to that (do 2026-08-09: 42 ngay, median |Δ| 42.9 diem tren
      thang ~300), nen replay ma bo qua dieu nay la doc so da duoc sua ve sau.
      Ban CU nam o cac nhan archive do `ingest/versioning.py` sinh, kem
      `revised_at` = luc no bi thay the; "con hieu luc tai as_of" nghia la
      `revised_at > as_of`, va neu co nhieu ban thi lay ban bi thay the SOM NHAT
      sau as_of.

      ⚠️ KHONG loc bang `loaded_at <= as_of`: lam vay la tron "luc ta nap" voi
      "luc gia tri biet duoc". Toan bo DB nay nap ngay 2026-08-09, nen dieu kien
      do se tra VE RONG cho moi as_of truoc hom nay — dung ky thuat, vo dung
      thuc te. (Da mac dung loi nay mot lan, giu ghi chu de khong lap lai.)
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(dsn)
    params: dict = {"ids": series_ids, "data_version": data_version}
    extra = ""
    if freq:
        extra = " AND freq = :freq"
        params["freq"] = freq

    if as_of is None:
        q = text(f"""
            SELECT series_id, date, value FROM ext_series
            WHERE series_id = ANY(:ids) AND data_version = :data_version{extra}
            ORDER BY date
        """)
    else:
        params["as_of"] = (pd.Timestamp(as_of, tz="UTC")
                           if pd.Timestamp(as_of).tzinfo is None
                           else pd.Timestamp(as_of))
        if not revision_aware:
            q = text(f"""
                SELECT series_id, date, value FROM ext_series
                WHERE series_id = ANY(:ids) AND data_version = :data_version
                  AND available_at <= :as_of{extra}
                ORDER BY date
            """)
        else:
            # prio=1: ban archive con hieu luc tai as_of (bi thay the SAU as_of),
            #         lay ban bi thay the som nhat.
            # prio=2: ban chay — dung cho moi (series, date) chua tung bi revise.
            q = text(f"""
                SELECT DISTINCT ON (series_id, date) series_id, date, value
                FROM (
                    SELECT series_id, date, value, 1 AS prio, revised_at
                    FROM ext_series
                    WHERE series_id = ANY(:ids) AND data_version <> :data_version
                      AND revised_at IS NOT NULL AND revised_at > :as_of
                      AND available_at <= :as_of{extra}
                    UNION ALL
                    SELECT series_id, date, value, 2 AS prio, NULL::timestamptz
                    FROM ext_series
                    WHERE series_id = ANY(:ids) AND data_version = :data_version
                      AND available_at <= :as_of{extra}
                ) t
                ORDER BY series_id, date, prio, revised_at
            """)
    with engine.connect() as conn:
        long = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    if long.empty:
        return pd.DataFrame()
    long = long.sort_values("date")
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


def load_monthly_macro_raw(dsn: str, as_of: str | pd.Timestamp | None = None,
                           data_version: str = "v1") -> pd.DataFrame:
    """Doc nhom THANG (ip/cpi/infl_exp/epu/freight) tu ext_series — MUC THO.

    CO Y tra ve muc tho, khong transform: bon nhom nay dung bon phep bien doi
    khac nhau (100·Δln INDPRO · Δln CPI · sai phan infl_exp · log1p EPU · Δln
    freight) va cac phep do da co o `data_files.transform_*`. Goi transform o day
    la fork quy uoc sang noi thu hai — dung thu ma docs/07 §0 cam.

    ⚠️ INDPRO/CPI/PPI revise hoi to; ban trong DB la vintage MOI NHAT ke tu lan
    nap dau. Point-in-time that phai qua ALFRED — xem docstring
    `ingest/macro_monthly.py`.
    """
    return load_series(dsn, list(MONTHLY_MACRO_SERIES.keys()), freq="monthly",
                       as_of=as_of, data_version=data_version).rename(
                           columns=MONTHLY_MACRO_SERIES)
