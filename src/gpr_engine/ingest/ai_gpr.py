"""Ingest AI-GPR (Iacoviello & Tong 2026) daily + monthly headline series vao ext_series.

Chan A: "chi INGEST, khong tu tinh lai" (CLAUDE.md #2). Tai lieu goc: docs/16 §1.
File nguon TAI TAY tu matteoiacoviello.com/ai_gpr.html (khong tu fetch — CLAUDE.md #4,
domain bi chan o egress policy cua sandbox). Schema da XAC MINH tren file that
2026-08-05 (vintage daily 13b8e8b48d41, monthly 92b9ba3bd38f) — xem AI_GPR_COLUMNS.

Chi ingest 12 chuoi TONG HOP (headline/threat/act/oil-tong/oil-8-vung/AER/NONOIL),
CUNG do granularity voi GPRD/GPRD_ACT/GPRD_THREAT da co (ext_series). CO Y KHONG
ingest 4 file "Country Decompositions" (eventtype/country x eventtype/bilateral/
country x vai tro, docs/16 §1) — nhung file do co cardinality lon (toi 1600+ cot),
CHUA co use case tieu thu trong production, va IC chua duoc chung minh (CLAUDE.md
#6: moi lop du lieu moi phai chung minh incremental IC truoc khi ep vao production).
Ingest 4 file do la viec RIENG, lam sau khi co ly do ro rang.

`AI_GPR_COLUMNS` la nguon CHINH THUC (canonical) cho ten cot — data_files.py (research,
offline) import lai tu day, giong het pattern GPR_DAILY_SERIES/PUBLISH_LAG_DAYS cua
ingest/gpr_daily.py duoc data_files.py import lai. Doi ten cot o day phai dong bo
CUNG COMMIT voi moi test/loader dang dung AI_GPR_COLUMNS (tests/econ/test_ai_gpr_loader.py,
tests/econ/test_ai_gpr_decompositions.py).

Vi du:
  python -m gpr_engine.ingest.ai_gpr --dsn postgresql://... \\
      --path-daily data/ai_gpr_data_daily.csv --path-monthly data/ai_gpr_data_monthly.csv
"""
from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import create_engine, text

from .versioning import RUNNING_VERSION, add_version_args, apply_snapshot

# Ten cot THAT trong file -> series_id dung trong ext_series. Xac minh tren file
# that 2026-08-05 — xem docs/16 §1.
#
# ⚠️ Day la ten cua ban DAILY. Ban MONTHLY phai mang hau to `_M` (xem
# `series_id_for`). Ly do — bug that, phat hien 2026-08-09 khi nap lan dau len
# Postgres SONG (truoc do module nay chi co test mock DB):
#   `ext_series` PK la (series_id, date, data_version) — KHONG CO `freq`. File
#   daily va monthly cua AI-GPR dung CHUNG bo ten cot, va moi ngay dau thang co
#   mat o CA HAI -> cung PK -> ghi de lan nhau. Nap `--freq both` thi monthly
#   chay sau va thang: 11.186 hang (799 ngay dau thang x 14 series) mang gia tri
#   THANG nam trong mot chuoi duoc danh dau `freq='daily'`.
#   Am tham hoan toan: gia tri thang ~ trung binh cua thang nen CUNG THANG DO
#   voi gia tri ngay (avg ngay-dau-thang 212 vs ngay khac 213) — bieu do khong
#   he lo ra. Vi du that: AIGPR_OIL 2026-03-01 = 1844.10 (gia tri THANG 3) trong
#   khi gia tri NGAY 2026-03-01 la 610.53.
#   Quy uoc cua repo von la ten RIENG theo tan suat (GPRD/GPRD_ACT daily vs
#   GPR/GPRT/GPRC_* monthly) — AI-GPR pha quy uoc do, nay sua lai cho khop.
AI_GPR_COLUMNS: dict[str, str] = {
    "GPR_AI": "AIGPR",
    "GPR_AER": "AIGPR_AER",
    "GPR_OIL": "AIGPR_OIL",
    "GPR_NONOIL": "AIGPR_NONOIL",
    "THREATS_GPR_AI": "AIGPR_THREAT",
    "ACTS_GPR_AI": "AIGPR_ACT",
    "GPR_OIL_MiddleEast": "AIGPR_OIL_MIDDLEEAST",
    "GPR_OIL_Russia": "AIGPR_OIL_RUSSIA",
    "GPR_OIL_USA": "AIGPR_OIL_USA",
    "GPR_OIL_Venezuela": "AIGPR_OIL_VENEZUELA",
    "GPR_OIL_Africa": "AIGPR_OIL_AFRICA",
    "GPR_OIL_Americas": "AIGPR_OIL_AMERICAS",
    "GPR_OIL_Asia": "AIGPR_OIL_ASIA",
    "GPR_OIL_NorthSea": "AIGPR_OIL_NORTHSEA",
}

# Hau to cua ban MONTHLY trong ext_series. Xem canh bao o AI_GPR_COLUMNS.
MONTHLY_SUFFIX = "_M"


def series_id_for(column: str, freq: str) -> str:
    """Ten cot trong file -> series_id trong ext_series, TACH theo tan suat.

    Bat buoc phai tach: PK cua ext_series khong chua `freq` nen dung chung ten
    la hai tan suat ghi de len nhau o moi ngay dau thang (bug 2026-08-09).
    """
    if freq not in ("daily", "monthly"):
        raise ValueError(f"freq phai la 'daily' hoac 'monthly', nhan {freq!r}")
    base = AI_GPR_COLUMNS[column]
    return base if freq == "daily" else f"{base}{MONTHLY_SUFFIX}"


def series_ids(freq: str) -> list[str]:
    """Toan bo series_id cua mot tan suat."""
    return [series_id_for(c, freq) for c in AI_GPR_COLUMNS]


# Thu muc doi 2026-08-08 (commit e3bde3b): data/*.csv -> data/AI-GPRs/*.csv.
DEFAULT_PATH_DAILY = "data/AI-GPRs/ai_gpr_data_daily.csv"
DEFAULT_PATH_MONTHLY = "data/AI-GPRs/ai_gpr_data_monthly.csv"

# Do tre publish — GIA DINH THAN TRONG, CHUA VERIFY voi vintage that (cung tinh
# trang thai voi PUBLISH_LAG_DAYS cua ingest/gpr_daily.py va gpr_monthly.py).
# Daily: coi nhu cung do tre 1 ngay voi GPRD goc (ca hai deu tinh tu bao ngay D,
# dang len D+1). Monthly: gia tri thang M chi biet duoc sau khi thang M ket thuc,
# giong het GPRC monthly — dung LAG 5 ngay tu dau thang ke tiep.
PUBLISH_LAG_DAYS_DAILY = 1
PUBLISH_LAG_DAYS_MONTHLY = 5
PUBLISH_HOUR_UTC = 12

_MISSING_MSG = (
    "Khong tim thay {path}. AI-GPR la file TAI TAY (docs/16 §1):\n"
    "  1. Tai tu matteoiacoviello.com/ai_gpr.html\n"
    "  2. Luu vao {path}\n"
    "  3. Doi chieu ten cot that voi AI_GPR_COLUMNS truoc khi ingest that "
    "(gpr_engine.econometrics.data_files.describe_ai_gpr_file)\n"
    "Co y khong tu tai: trang cap nhat dinh ky, fetch ngam lam report cu mat "
    "tai lap (nguyen tac #4)."
)


def load_dataframe(path: str, date_col: str = "Date") -> pd.DataFrame:
    """Doc file AI-GPR THO, doi ten cot, giu wide (index KHONG dat — to_long lam sau).

    Raise (khong lang le bo qua) neu thieu cot ngay hoac bat ky cot nao trong
    AI_GPR_COLUMNS — thieu threats/acts thi tach ACT/THREAT sau do chay tren
    du lieu rong ma khong ai thay (cung ly do voi data_files._load_ai_gpr).
    """
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(_MISSING_MSG.format(path=path))
    df = pd.read_csv(p)
    if date_col not in df.columns:
        raise ValueError(
            f"Khong co cot ngay {date_col!r} trong {path}. Cot thuc te: {list(df.columns)}")
    missing = [c for c in AI_GPR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path} thieu cot {missing}. Cot thuc te: {list(df.columns)}. "
            "Doi chieu bang describe_ai_gpr_file() truoc khi ingest.")
    out = df[[date_col, *AI_GPR_COLUMNS]].rename(columns={date_col: "date", **AI_GPR_COLUMNS})
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date").reset_index(drop=True)


def available_at(dates: pd.Series, freq: str) -> pd.Series:
    """Ngay quan sat -> thoi diem SOM NHAT gia tri do biet duoc (UTC), theo tan suat.

    freq='daily': date + PUBLISH_LAG_DAYS_DAILY (giong GPRD).
    freq='monthly': dau thang KE TIEP + PUBLISH_LAG_DAYS_MONTHLY (giong GPRC monthly)
    — gia tri thang M chi biet sau khi thang M ket thuc, dung `date` lam proxy la
    look-ahead (docs/08 §4.7).
    """
    d = pd.to_datetime(dates)
    if freq == "daily":
        base = d
        lag = PUBLISH_LAG_DAYS_DAILY
    elif freq == "monthly":
        base = d + pd.offsets.MonthBegin(1)
        lag = PUBLISH_LAG_DAYS_MONTHLY
    else:
        raise ValueError(f"freq phai la 'daily' hoac 'monthly', nhan {freq!r}")
    return (base + pd.Timedelta(days=lag) + pd.Timedelta(hours=PUBLISH_HOUR_UTC)).dt.tz_localize("UTC")


def to_long(df: pd.DataFrame, freq: str, source_version: str, data_version: str) -> pd.DataFrame:
    # `load_dataframe` da doi ten cot sang series_id BAN DAILY; ban monthly gan
    # them hau to de khong dung PK voi ban daily (xem `series_id_for`).
    series_cols = list(AI_GPR_COLUMNS.values())
    long = df.melt(id_vars=["date"], value_vars=series_cols,
                   var_name="series_id", value_name="value")
    if freq == "monthly":
        long["series_id"] = long["series_id"] + MONTHLY_SUFFIX
    long["freq"] = freq
    long["source"] = f"ai_gpr_{freq}_file"
    long["available_at"] = available_at(long["date"], freq)
    long["date"] = long["date"].dt.date
    long["source_version"] = source_version
    long["data_version"] = data_version
    return long.dropna(subset=["value"])


def upsert(long: pd.DataFrame, dsn: str) -> int:
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


def ingest_one(path: str, freq: str, dsn: str, source_version: str, data_version: str) -> int:
    """UPSERT tho vao MOT data_version (khong archive ban cu).

    Giu lai vi da co test khoa; duong chinh la `ingest_one_versioned` — no moi
    la cai bat duoc revise (AI-GPR cung tinh lai hoi to nhu GPR goc).
    """
    df = load_dataframe(path)
    long = to_long(df, freq, source_version, data_version)
    return upsert(long, dsn)


def ingest_one_versioned(path: str, freq: str, dsn: str, source_version: str,
                         *, mode: str = "delta",
                         running_version: str = RUNNING_VERSION):
    df = load_dataframe(path)
    long = to_long(df, freq, source_version, running_version)
    return apply_snapshot(long, dsn, prefix=f"ai_gpr_{freq}",
                          description=f"AI-GPR {freq} {source_version}",
                          mode=mode, running_version=running_version)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path-daily", default=DEFAULT_PATH_DAILY)
    ap.add_argument("--path-monthly", default=DEFAULT_PATH_MONTHLY)
    ap.add_argument("--freq", choices=["daily", "monthly", "both"], default="both")
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host/db")
    ap.add_argument("--source-version-daily", default="ai_gpr_daily_202608")
    ap.add_argument("--source-version-monthly", default="ai_gpr_monthly_202608")
    add_version_args(ap)
    args = ap.parse_args()

    for freq, path, sv in (("daily", args.path_daily, args.source_version_daily),
                           ("monthly", args.path_monthly, args.source_version_monthly)):
        if args.freq not in (freq, "both"):
            continue
        rep = ingest_one_versioned(path, freq, args.dsn, sv, mode=args.snapshot,
                                   running_version=args.running_version)
        print(f"AI-GPR {freq} | {len(AI_GPR_COLUMNS)} series | {path}")
        print(rep.summary())


if __name__ == "__main__":
    main()
