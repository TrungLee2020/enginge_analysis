"""Ingest market & channel series (G1.3) vao ext_series.

Chan A can cac chuoi thi truong lam bien kiem soat cho econometrics (VIX, DXY,
Oil, US10Y) va cac chuoi VN lam bien phu thuoc (VN-Index, VN30, USD/VND).

Nguon:
  - Macro/global: FRED (uu tien, co published series on dinh) hoac yfinance fallback.
  - VN (VN-Index, VN30, USD/VND, thanh khoan HOSE): nguon noi bo BeaverX. O day chi
    de DUONG NOI qua config (dsn/endpoint), KHONG hardcode API key/URL — theo design.

Cung pattern voi gpr_daily.py: load -> to_long -> upsert idempotent (UPSERT theo PK).
Chay lai khong nhan doi.

Vi du:
  python -m gpr_engine.ingest.market_data --dsn postgresql://... --source fred \\
      --start 1990-01-01
"""
from __future__ import annotations

import argparse
import datetime as dt
from typing import Callable

import pandas as pd
from sqlalchemy import create_engine, text

# series_id noi bo -> ma nguon. Giu series_id ngan, on dinh (dung trong econometrics).
# FRED codes: https://fred.stlouisfed.org
FRED_MAP: dict[str, str] = {
    "BRENT": "DCOILBRENTEU",   # Brent crude, USD/bbl, daily
    "DXY": "DTWEXBGS",         # Trade-weighted USD index, broad goods (proxy DXY)
    "VIX": "VIXCLS",           # CBOE VIX, daily
    "US10Y": "DGS10",          # 10Y Treasury yield, daily
}

# yfinance fallback tickers (khi khong co/khong voi toi FRED).
YF_MAP: dict[str, str] = {
    "BRENT": "BZ=F",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "US10Y": "^TNX",           # x10 so voi yield thuc; chuan hoa /10 khi load
}

# Cac chuoi VN lay tu nguon noi bo BeaverX (khong phai FRED/yfinance).
VN_SERIES = ["VNINDEX", "VN30", "USDVND"]

# Moc coi nhu gia dong cua phien D da biet (UTC). 23h de bao phu ca US close (21:00 UTC)
# lan cac thi truong dong som hon. Xem available_at() — cong vao `date` de chong leakage.
CLOSE_HOUR_UTC = 23


# ---------------------------------------------------------------------------
# Loaders — moi loader tra ve DataFrame long: [series_id, date, value]
# ---------------------------------------------------------------------------
def _long(series_id: str, s: pd.Series) -> pd.DataFrame:
    out = s.rename("value").reset_index()
    out.columns = ["date", "value"]
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["series_id"] = series_id
    return out[["series_id", "date", "value"]].dropna(subset=["value"])


def load_fred(series_ids: list[str], start: str, end: str | None) -> pd.DataFrame:
    """Tai tu FRED qua pandas-datareader. series_ids la series_id noi bo."""
    from pandas_datareader import data as pdr

    frames = []
    for sid in series_ids:
        code = FRED_MAP.get(sid)
        if code is None:
            raise ValueError(f"'{sid}' khong co trong FRED_MAP. Co: {list(FRED_MAP)}")
        raw = pdr.DataReader(code, "fred", start, end)[code]
        frames.append(_long(sid, raw))
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def load_yfinance(series_ids: list[str], start: str, end: str | None) -> pd.DataFrame:
    """Fallback: tai Close tu yfinance."""
    import yfinance as yf

    frames = []
    for sid in series_ids:
        ticker = YF_MAP.get(sid)
        if ticker is None:
            raise ValueError(f"'{sid}' khong co trong YF_MAP. Co: {list(YF_MAP)}")
        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
        close = hist["Close"]
        if sid == "US10Y":          # ^TNX niem yet x10 so voi yield %
            close = close / 10.0
        frames.append(_long(sid, close))
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def load_vn_placeholder(series_ids: list[str], *_args, **_kwargs) -> pd.DataFrame:
    """Cho VN-Index/VN30/USD-VND tu BeaverX. Chua co duong noi thuc -> khong im lang
    lam sai: raise ro rang de nguoi van hanh cau hinh nguon noi bo.
    """
    raise NotImplementedError(
        "VN series (VNINDEX/VN30/USDVND) lay tu nguon noi bo BeaverX. "
        "Cau hinh endpoint/DSN noi bo roi thay ham nay bang loader that. "
        f"Yeu cau: {series_ids}"
    )


SOURCES: dict[str, Callable[..., pd.DataFrame]] = {
    "fred": load_fred,
    "yfinance": load_yfinance,
    "beaverx": load_vn_placeholder,
}


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["series_id", "date", "value"])


# ---------------------------------------------------------------------------
# Upsert — idempotent, giong het gpr_daily.py
# ---------------------------------------------------------------------------
def available_at(dates: pd.Series) -> pd.Series:
    """date phien -> thoi diem gia dong cua biet duoc (UTC).

    Khac GPR: gia dong cua cua phien D biet ngay trong ngay D (sau khi dong cua),
    khong tre sang D+1. Dat moc cuoi ngay D theo UTC de bao phu moi mui gio thi truong.
    Luu y: FRED co the REVISE mot so series (vd US10Y) sau khi publish lan dau;
    khi bat dau lay vintage that thi ghi revised_at + tang data_version, dung ghi de.
    """
    return (pd.to_datetime(dates)
            + pd.Timedelta(hours=CLOSE_HOUR_UTC)).dt.tz_localize("UTC")


def upsert(long: pd.DataFrame, dsn: str, source: str,
           source_version: str = "", data_version: str = "v1") -> int:
    if long.empty:
        return 0
    long = long.copy()
    long["freq"] = "daily"
    long["source"] = source
    long["available_at"] = available_at(long["date"])
    long["source_version"] = source_version or source
    long["data_version"] = data_version
    engine = create_engine(dsn)
    sql = text("""
        INSERT INTO ext_series (series_id, date, value, freq, source,
                                available_at, source_version, data_version)
        VALUES (:series_id, :date, :value, :freq, :source,
                :available_at, :source_version, :data_version)
        ON CONFLICT (series_id, date, data_version)
        DO UPDATE SET value = EXCLUDED.value, loaded_at = now()
    """)
    with engine.begin() as conn:
        conn.execute(sql, long.to_dict(orient="records"))
    return len(long)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host/db")
    ap.add_argument("--source", default="fred", choices=list(SOURCES),
                    help="fred (macro) | yfinance (fallback) | beaverx (VN series)")
    ap.add_argument("--series", nargs="*", default=None,
                    help="series_id can tai; mac dinh theo source")
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--end", default=None, help="mac dinh: hom nay")
    ap.add_argument("--data-version", default="v1")
    args = ap.parse_args()

    end = args.end or dt.date.today().isoformat()
    if args.series:
        series_ids = args.series
    elif args.source == "beaverx":
        series_ids = VN_SERIES
    else:
        series_ids = list(FRED_MAP)

    long = SOURCES[args.source](series_ids, args.start, end)
    n = upsert(long, args.dsn, source=args.source, data_version=args.data_version)
    if n:
        print(f"Upserted {n} rows | source={args.source} | series={series_ids} | "
              f"range {long['date'].min()} -> {long['date'].max()}")
    else:
        print(f"Khong co du lieu | source={args.source} | series={series_ids}")


if __name__ == "__main__":
    main()
