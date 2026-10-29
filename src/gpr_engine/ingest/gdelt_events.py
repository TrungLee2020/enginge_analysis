"""Ingest chan C (GDELT 2.0 Events) vao ext_series: ty trong QuadClass 3/4 theo ngay.

Nguon: bo thu tin GPR cua repport_v2 (`collect_gpr.py layer-a` / `gdelt-backfill`) tai
file export 15 phut cua GDELT 2.0 Events va GHI SAN so dem theo slot:
    data/gdelt_events/<YYYY-MM>/<YYYY-MM-DD>.jsonl   (ngay UTC, moi dong mot slot)
    {"slot": ISO, "n": int, "q": [q1..q4], "m": [...], "watch_n": int, "watch_q": [...], ...}
Module nay CHI gop slot -> ngay va nap (CLAUDE.md #2: chi ingest, khong tu ma hoa su kien).

Series (daily, ngay UTC):
    GDELT_EVENTS_N            so su kien da ma hoa trong ngay
    GDELT_QUAD3_SHARE         ty trong QuadClass 3 (xung dot loi noi)
    GDELT_QUAD4_SHARE         ty trong QuadClass 4 (xung dot vat chat)
    GDELT_WATCH_N / GDELT_WATCH_QUAD3_SHARE / GDELT_WATCH_QUAD4_SHARE
                              cung the, chi su kien co actor thuoc watch_countries
                              cua collector (config/gpr_watchlist.json ben repport_v2)

Ngay THIEU slot (collector nghi, GDELT 404) bi BO, khong nap: ty trong van gan dung
nhung GDELT_EVENTS_N se thap gia, va mot ngay thieu nua cuoi la ngay thieu dung
gio My — sai lech co he thong, khong phai nhieu. Nguong: MIN_SLOTS / 96.

`available_at` = het ngay + PUBLISH_LAG (file slot cuoi 23:45 xuat hien ~00:00-00:15
UTC; lay 01:00 cho than trong) — CLAUDE.md #11.

⚠️ CHUA NOI vao Escalation Ladder. `pipeline/news_pipeline._pair_indicator_frame` van
de quad3_pct/quad4_pct = NaN. Chan C la lop du lieu moi -> phai chung minh incremental
IC truoc (CLAUDE.md #6, #1). Khi qua cong: phan vi EXPANDING strict `<`
(`indices.s_gpr.expanding_percentile`), doc qua `load_series(as_of=...)`, va
config/ladder_v1.yaml da khai bao san nguong (quad3 > 75, quad4 > 90).

Vi du:
  python -m gpr_engine.ingest.gdelt_events --path data/gdelt_events --dsn postgresql://...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .versioning import RUNNING_VERSION, add_version_args, apply_snapshot

DEFAULT_PATH = "data/gdelt_events"
SLOTS_PER_DAY = 96
MIN_SLOTS = 92
PUBLISH_LAG = pd.Timedelta(days=1, hours=1)     # tu 00:00 UTC cua ngay quan sat
SOURCE = "gdelt_events_collector"

SERIES = ("GDELT_EVENTS_N", "GDELT_QUAD3_SHARE", "GDELT_QUAD4_SHARE",
          "GDELT_WATCH_N", "GDELT_WATCH_QUAD3_SHARE", "GDELT_WATCH_QUAD4_SHARE")


def load_slots(path: str) -> pd.DataFrame:
    """Moi slot mot hang: slot (UTC), n, q3, q4, watch_n, wq3, wq4. Raise neu thu muc rong."""
    root = Path(path)
    files = sorted(root.glob("*/*.jsonl"))
    if not files:
        raise FileNotFoundError(
            f"Khong co file slot nao duoi {path}/<YYYY-MM>/<YYYY-MM-DD>.jsonl. "
            "Chay collector ben repport_v2: python collect_gpr.py gdelt-backfill --start ... --end ...")
    rows = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            q, wq = r["q"], r.get("watch_q") or [0, 0, 0, 0]
            if len(q) != 4 or len(wq) != 4:
                raise ValueError(f"{f}: slot {r.get('slot')} khong co du 4 QuadClass")
            rows.append({"slot": pd.Timestamp(r["slot"]), "n": int(r["n"]), "q3": int(q[2]), "q4": int(q[3]),
                         "watch_n": int(r.get("watch_n") or 0), "wq3": int(wq[2]), "wq4": int(wq[3])})
    df = pd.DataFrame(rows)
    df["slot"] = pd.to_datetime(df["slot"], utc=True)
    return df.drop_duplicates("slot", keep="last").sort_values("slot").reset_index(drop=True)


def daily(slots: pd.DataFrame, min_slots: int = MIN_SLOTS) -> pd.DataFrame:
    """Gop slot -> ngay UTC; bo ngay co it hon min_slots slot. Ty trong NaN khi n = 0."""
    g = slots.assign(date=slots["slot"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)) \
             .groupby("date").agg(slots=("slot", "size"), n=("n", "sum"), q3=("q3", "sum"), q4=("q4", "sum"),
                                  watch_n=("watch_n", "sum"), wq3=("wq3", "sum"), wq4=("wq4", "sum"))
    g = g[g["slots"] >= min_slots]
    share = lambda a, b: (a / b).where(b > 0)  # noqa: E731
    return pd.DataFrame({
        "GDELT_EVENTS_N": g["n"].astype(float),
        "GDELT_QUAD3_SHARE": share(g["q3"], g["n"]),
        "GDELT_QUAD4_SHARE": share(g["q4"], g["n"]),
        "GDELT_WATCH_N": g["watch_n"].astype(float),
        "GDELT_WATCH_QUAD3_SHARE": share(g["wq3"], g["watch_n"]),
        "GDELT_WATCH_QUAD4_SHARE": share(g["wq4"], g["watch_n"]),
    }).reset_index()


def to_long(wide: pd.DataFrame, source_version: str, data_version: str) -> pd.DataFrame:
    long = wide.melt(id_vars=["date"], value_vars=list(SERIES), var_name="series_id", value_name="value")
    long["freq"] = "daily"
    long["source"] = SOURCE
    long["available_at"] = (pd.to_datetime(long["date"]) + PUBLISH_LAG).dt.tz_localize("UTC")
    long["date"] = pd.to_datetime(long["date"]).dt.date
    long["source_version"] = source_version
    long["data_version"] = data_version
    return long.dropna(subset=["value"]).reset_index(drop=True)


def ingest_versioned(path: str, dsn: str, source_version: str, *, min_slots: int = MIN_SLOTS,
                     mode: str = "delta", running_version: str = RUNNING_VERSION):
    long = to_long(daily(load_slots(path), min_slots), source_version, running_version)
    return apply_snapshot(long, dsn, prefix="gdelt_events", description=f"GDELT Events {source_version}",
                          mode=mode, running_version=running_version)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host/db")
    ap.add_argument("--source-version", default="gdelt_events_collector_v1")
    ap.add_argument("--min-slots", type=int, default=MIN_SLOTS)
    add_version_args(ap)
    args = ap.parse_args()
    rep = ingest_versioned(args.path, args.dsn, args.source_version, min_slots=args.min_slots,
                           mode=args.snapshot, running_version=args.running_version)
    print(f"GDELT Events | {len(SERIES)} series | {args.path}")
    print(rep.summary())


if __name__ == "__main__":
    main()
