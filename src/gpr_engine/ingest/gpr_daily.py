"""Ingest GPR daily file (data_gpr_daily_recent.xls) into ext_series.

Reference implementation — verified against user's file:
  columns: DAY, N10D, GPRD, GPRD_ACT, GPRD_THREAT, date, GPRD_MA30, GPRD_MA7, event, ...
  range:   1985-01-01 -> 2026-06-29 (15,155 rows)

Claude Code: dùng làm khuôn mẫu. Áp dụng cùng pattern (idempotent UPSERT,
guard cột thiếu) cho gpr_monthly.py và market_data.py.
"""
from __future__ import annotations
import argparse
import pandas as pd
from sqlalchemy import create_engine, text

SERIES = ["GPRD", "GPRD_ACT", "GPRD_THREAT"]  # 3 chuỗi cần cho chân A daily

# Độ trễ publish: GPR daily của Caldara-Iacoviello tính từ báo chí ngày D, đăng lên
# matteoiacoviello.com trong ngày D+1. `available_at = date + lag` — KHÔNG phải `date`.
# Dùng `date` làm thời điểm quyết định = look-ahead bias (docs/08 §4.7, docs/09 §2.8).
# GIẢ ĐỊNH THẬN TRỌNG, CHƯA VERIFY với vintage thật — xem G1 data audit.
PUBLISH_LAG_DAYS = 1
PUBLISH_HOUR_UTC = 12  # giờ trong ngày D+1 coi như đã đọc được


def load_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1", header=0)
    missing = [c for c in SERIES + ["date"] if c not in df.columns]
    if missing:
        raise ValueError(f"File thiếu cột bắt buộc: {missing}. Cột hiện có: {list(df.columns)}")
    df = df[["date"] + SERIES].dropna(subset=["date"]).copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def available_at(dates: pd.Series) -> pd.Series:
    """date quan sát -> thời điểm sớm nhất giá trị đó biết được (UTC)."""
    return (pd.to_datetime(dates)
            + pd.Timedelta(days=PUBLISH_LAG_DAYS)
            + pd.Timedelta(hours=PUBLISH_HOUR_UTC)).dt.tz_localize("UTC")


def to_long(df: pd.DataFrame, source_version: str, data_version: str) -> pd.DataFrame:
    long = df.melt(id_vars=["date"], value_vars=SERIES,
                   var_name="series_id", value_name="value")
    long["freq"] = "daily"
    long["source"] = "gpr_daily_file"
    long["available_at"] = available_at(long["date"])
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/data_gpr_daily_recent.xls")
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host/db")
    ap.add_argument("--source-version", default="gpr_daily_recent_202606",
                    help="vintage của file nguồn")
    ap.add_argument("--data-version", default="v1")
    args = ap.parse_args()

    df = load_dataframe(args.path)
    long = to_long(df, args.source_version, args.data_version)
    n = upsert(long, args.dsn)
    print(f"Upserted {n} rows | series={SERIES} | "
          f"range {df['date'].min()} -> {df['date'].max()} | "
          f"available_at = date +{PUBLISH_LAG_DAYS}d")


if __name__ == "__main__":
    main()
