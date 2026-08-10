"""Ingest macro THANG tu FRED vao ext_series: outcome vi mo thuc + battery + cuoc bien.

Bo sung khoang trong cuoi cua duong DB: `ingest/market_data.py` chi lo 4 chuoi
DAILY (BRENT/DXY/VIX/US10Y), trong khi tang 2 con can outcome vi mo thuc
(ip/cpi/infl_exp), battery benchmark (EPU US/Global) va kenh vat ly (cuoc bien).
Ba nhom nay truoc gio CHI ton tai o duong research file (`data_files.py`), nen
panel tang 2 khong dung duoc tu DB.

Luu tri GIA TRI THO (muc chi so), giong moi ingest khac. Transform (100·Δln
INDPRO, Δln CPI, sai phan infl_exp, log1p EPU, Δln freight) la viec cua
`dataset.py`/`data_files.py` — KHONG bien doi o day, neu khong thi mot quy uoc
transform ton tai o hai noi va se lech nhau.

⚠️ HAI CANH BAO PHAI DOC TRUOC KHI DUNG CHO BACKTEST
1. HIEU CHINH HOI TO. INDPRO revise toi 5 nam sau publish, CPIAUCSL revise nhieu
   ky, PPI cung revise. Ban keo tu FRED LUON la vintage MOI NHAT — khong phai cai
   nguoi ra quyet dinh thay luc do. `ingest/versioning.py` giu duoc vintage TU
   LUC TA BAT DAU NAP tro di, nhung KHONG dung lai duoc qua khu truoc do. Point-
   in-time that cho nhom nay phai qua **ALFRED** (FRED co API vintage rieng, can
   API key). Voi uoc luong γ mo ta truyen dan thi ban nay chap nhan duoc; voi
   backtest sinh tin hieu thi KHONG.
2. `available_at` duoi day la GIA DINH THAN TRONG, CHUA VERIFY voi lich publish
   that (cung tinh trang voi PUBLISH_LAG_DAYS cua gpr_daily.py/gpr_monthly.py).
   Than trong = dat MUON hon lich that -> thieu du lieu chu khong look-ahead.
"""
from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd

from .versioning import add_version_args, apply_snapshot

# series_id trong ext_series -> ma FRED. Ten VIET HOA, khong trung bat cu
# series_id daily nao (PK khong chua `freq` — xem chot chan trong versioning.py).
#
# ⚠️ Ma FRED o day phai TRUNG KHIT `data_files.FRED_REAL_MACRO` /
# `FRED_BENCHMARK` / `FRED_FREIGHT`. Khong import lai duoc (data_files import tu
# ingest, nguoc lai la vong tron) nen rang buoc bang test:
# `test_macro_monthly_codes_match_research_path`.
FRED_MONTHLY: dict[str, str] = {
    "INDPRO": "INDPRO",                  # Industrial Production index, SA
    "CPI": "CPIAUCSL",                   # CPI-U all items, SA
    "INFL_EXP": "MICH",                  # Michigan 1-year inflation expectation
    "EPU_US": "USEPUINDXM",              # US Economic Policy Uncertainty
    "EPU_GLOBAL": "GEPUCURRENT",         # Global EPU (GDP-weighted), 1997+
    "FREIGHT_PPI": "PCU483111483111",    # PPI deep sea freight, US
}

# Do tre publish theo TUNG series: gia tri thang M chi biet sau khi M ket thuc,
# moc som nhat = dau thang M+1 + so ngay duoi day. Lay tron LEN so voi lich that.
#   INDPRO/CPI  : BLS/Fed cong bo ~giua thang ke tiep -> 18 ngay.
#   FREIGHT_PPI : PPI ra sau CPI vai ngay -> 20 ngay.
#   MICH        : ban final ra cuoi chinh thang do -> +5 da la than trong.
#   EPU_*       : cap nhat dau thang ke tiep -> 7 ngay.
PUBLISH_LAG_DAYS: dict[str, int] = {
    "INDPRO": 18, "CPI": 18, "FREIGHT_PPI": 20,
    "INFL_EXP": 5, "EPU_US": 7, "EPU_GLOBAL": 7,
}
PUBLISH_HOUR_UTC = 12


def load_fred_monthly(series_ids: list[str], start: str,
                      end: str | None) -> pd.DataFrame:
    """Keo tu FRED -> long [series_id, date, value]. `date` = dau thang quan sat."""
    from pandas_datareader import data as pdr

    frames = []
    for sid in series_ids:
        code = FRED_MONTHLY.get(sid)
        if code is None:
            raise ValueError(
                f"'{sid}' khong co trong FRED_MONTHLY. Co: {list(FRED_MONTHLY)}")
        raw = pdr.DataReader(code, "fred", start, end)[code].dropna()
        out = raw.rename("value").reset_index()
        out.columns = ["date", "value"]
        out["series_id"] = sid
        frames.append(out[["series_id", "date", "value"]])
    if not frames:
        return pd.DataFrame(columns=["series_id", "date", "value"])
    return pd.concat(frames, ignore_index=True)


def available_at(dates: pd.Series, series_id: str) -> pd.Series:
    """Dau thang quan sat -> thoi diem SOM NHAT gia tri thang do biet duoc (UTC).

    Gia tri thang M tong hop CA THANG nen moc som nhat la dau thang M+1, cong do
    tre publish rieng cua series. Dung chinh `date` lam moc = nhin truoc gan mot
    thang — dung bay ma docs/08 §4.7 canh bao.
    """
    if series_id not in PUBLISH_LAG_DAYS:
        raise ValueError(f"Chua khai do tre publish cho {series_id!r}. "
                         "Dat mot gia tri THAN TRONG vao PUBLISH_LAG_DAYS, "
                         "khong duoc mac dinh 0.")
    nxt = pd.to_datetime(dates) + pd.offsets.MonthBegin(1)
    return (nxt + pd.Timedelta(days=PUBLISH_LAG_DAYS[series_id])
            + pd.Timedelta(hours=PUBLISH_HOUR_UTC)).dt.tz_localize("UTC")


def to_long(raw: pd.DataFrame, source_version: str,
            data_version: str) -> pd.DataFrame:
    out = raw.copy()
    out["available_at"] = pd.concat(
        [available_at(g["date"], sid) for sid, g in out.groupby("series_id")]
    ).sort_index()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["freq"] = "monthly"
    out["source"] = "fred_monthly"
    out["source_version"] = source_version
    out["data_version"] = data_version
    return out.dropna(subset=["value"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host/db")
    ap.add_argument("--series", nargs="*", default=None,
                    help=f"mac dinh tat ca: {list(FRED_MONTHLY)}")
    ap.add_argument("--start", default="1985-01-01")
    ap.add_argument("--end", default=None, help="mac dinh: hom nay")
    ap.add_argument("--source-version", default="fred_monthly")
    add_version_args(ap)
    args = ap.parse_args()

    series_ids = args.series or list(FRED_MONTHLY)
    raw = load_fred_monthly(series_ids, args.start,
                            args.end or dt.date.today().isoformat())
    if raw.empty:
        print(f"Khong co du lieu | series={series_ids}")
        return
    long = to_long(raw, args.source_version, args.running_version)
    rep = apply_snapshot(long, args.dsn, prefix="macro_monthly",
                         description=f"FRED monthly {series_ids}",
                         mode=args.snapshot,
                         running_version=args.running_version)
    print(f"macro monthly | series={series_ids} | "
          f"range {long['date'].min()} -> {long['date'].max()}")
    print(rep.summary())


if __name__ == "__main__":
    main()
