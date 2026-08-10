"""Ingest GPR monthly file (data_gpr_export_YYYYMM.xls, ban 44 nuoc) vao ext_series.

Verified against data_gpr_export_202607.xls:
  1518 dong x 115 cot, monthly 1900-01 -> 2026-06
  44 cot GPRC_*  (recent country GPR, 1985+)
  44 cot GPRHC_* (historical country GPR, 1900+)
  + global: GPR, GPRT, GPRA, GPRH, GPRHT, GPRHA
  dictionary: var_name / var_label o cot cuoi

Guard: neu thieu GPRC_VNM -> raise (tranh nham phai vintage 39 nuoc historical-only).
"""
from __future__ import annotations
import argparse
import pandas as pd
from sqlalchemy import create_engine, text

from .versioning import add_version_args, apply_snapshot

GLOBAL_SERIES = ["GPR", "GPRT", "GPRA", "GPRH", "GPRHT", "GPRHA"]

# Độ trễ publish monthly — LỚN và dễ gây leakage hơn daily rất nhiều.
# `date` ở file là NGÀY ĐẦU THÁNG nhưng giá trị tổng hợp CẢ THÁNG: giá trị của 2026-03-01
# chỉ biết được sau khi tháng 3 kết thúc, tức đầu tháng 4. Coi `date` là thời điểm biết
# = nhìn trước gần một tháng. Đây chính là bẫy docs/08 §4.7 cảnh báo.
# available_at = ngày đầu tháng KẾ TIẾP + PUBLISH_LAG_DAYS.
# GIẢ ĐỊNH THẬN TRỌNG, CHƯA VERIFY với vintage thật — xem G1 data audit.
PUBLISH_LAG_DAYS = 5
PUBLISH_HOUR_UTC = 12


def load_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1", header=0)
    if "GPRC_VNM" not in df.columns:
        raise ValueError(
            "Thieu GPRC_VNM - co the day la vintage cu 39 nuoc (historical-only). "
            "Can ban moi data_gpr_export_YYYYMM.xls tu link 'Download our monthly data'."
        )
    df["month"] = pd.to_datetime(df["month"])
    return df


def available_at(months: pd.Series) -> pd.Series:
    """Ngay dau thang quan sat -> thoi diem som nhat gia tri thang do biet duoc (UTC).

    Gia tri thang M chi biet sau khi thang M ket thuc => moc la dau thang M+1,
    cong them do tre publish. KHONG bao gio dung chinh `date`.
    """
    m = pd.to_datetime(months)
    next_month = m + pd.offsets.MonthBegin(1)
    return (next_month
            + pd.Timedelta(days=PUBLISH_LAG_DAYS)
            + pd.Timedelta(hours=PUBLISH_HOUR_UTC)).dt.tz_localize("UTC")


def to_long(df: pd.DataFrame, source_version: str, data_version: str) -> pd.DataFrame:
    country = [c for c in df.columns if c.startswith(("GPRC_", "GPRHC_"))]
    keep = ["month"] + [c for c in GLOBAL_SERIES if c in df.columns] + country
    long = df[keep].melt(id_vars=["month"], var_name="series_id", value_name="value")
    long = long.rename(columns={"month": "date"})
    long["available_at"] = available_at(long["date"])
    long["date"] = long["date"].dt.date
    long["freq"] = "monthly"
    long["source"] = "gpr_monthly_file"
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
    # Vintage 2026-08 (file trong `data/GPR index/`, phu 1900-01..2026-07).
    ap.add_argument("--path", default="data/GPR index/data_gpr_export_202608.xls")
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--source-version", default="gpr_export_202608")
    add_version_args(ap)
    args = ap.parse_args()

    df = load_dataframe(args.path)
    long = to_long(df, args.source_version, args.running_version)
    rep = apply_snapshot(long, args.dsn, prefix="gpr_monthly",
                         description=f"GPR monthly {args.source_version}",
                         mode=args.snapshot,
                         running_version=args.running_version)
    print(f"GPR monthly | {long['series_id'].nunique()} series | "
          f"range {long['date'].min()} -> {long['date'].max()} | "
          f"available_at = dau thang ke tiep +{PUBLISH_LAG_DAYS}d")
    print(rep.summary())


if __name__ == "__main__":
    main()
