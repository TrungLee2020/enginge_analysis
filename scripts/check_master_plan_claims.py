"""Kiem tra cac SO LIEU ma master plan (docs/17_master_plan.md) trich dan, tren file THAT.

Guard P1 tinh than: khong go tay so vao doc. Moi con so trong docs/17_master_plan.md §A
(phu luc kiem chung) phai in ra tu script nay.

Chay:
    python scripts/check_master_plan_claims.py

Khong can PostgreSQL, khong can mang. Chi doc file trong data/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Layout file trong repo khong khop DEFAULT_* cua data_files.py (xem docs/17_master_plan.md §C5).
# Script nay do tim ca hai layout de chay duoc o ca hai truong hop.
CANDIDATES = {
    "ai_daily": ["data/ai_gpr_data_daily.csv", "data/AI-GPRs/ai_gpr_data_daily.csv"],
    "ai_monthly": ["data/ai_gpr_data_monthly.csv", "data/AI-GPRs/ai_gpr_data_monthly.csv"],
    "ai_country": ["data/ai_gpr_country_monthly.csv",
                   "data/AI-GPRs/ai_gpr_country_monthly.csv"],
    "ai_bilateral": ["data/ai_gpr_bilateral_monthly.csv",
                     "data/AI-GPRs/ai_gpr_bilateral_monthly.csv"],
    "gpr_daily": ["data/data_gpr_daily_recent.xls",
                  "data/GPR index/data_gpr_daily_recent (1).xls"],
}


def _find(key: str) -> Path:
    for p in CANDIDATES[key]:
        if Path(p).exists():
            return Path(p)
    raise FileNotFoundError(f"{key}: khong thay o {CANDIDATES[key]}")


def _load_gprd(path: Path) -> pd.DataFrame:
    """File .xls GPR goc co CA cot `DAY` (so nguyen yyyymmdd) LAN cot `date`
    (datetime) + cot dictionary var_name/var_label o duoi. Dung cot `date`."""
    raw = pd.read_excel(path)
    out = raw[["date", "GPRD", "GPRD_ACT", "GPRD_THREAT"]].dropna(subset=["date"]).copy()
    out["Date"] = pd.to_datetime(out["date"])
    return out.drop(columns=["date"])


def main() -> int:
    ai = pd.read_csv(_find("ai_daily"), parse_dates=["Date"])
    aim = pd.read_csv(_find("ai_monthly"), parse_dates=["Date"])
    gprd = _load_gprd(_find("gpr_daily"))

    print("=" * 72)
    print("1. GRANULARITY + SO VUNG OIL  (plan §3)")
    print("=" * 72)
    oil = [c for c in ai.columns if c.startswith("GPR_OIL_")]
    print(f"  file daily  : {len(ai)} hang, {ai.Date.min().date()} -> {ai.Date.max().date()}")
    print(f"  cot oil-vung: {len(oil)}  {oil}")
    print("  co cot 'Southeast Asia' rieng?  "
          f"{any('SoutheastAsia' in c or 'SouthEastAsia' in c for c in oil)}")
    for key, label in [("ai_country", "country x 200 x 4 vai"),
                       ("ai_bilateral", "bilateral x 1200 cap")]:
        p = _find(key)
        head = pd.read_csv(p, nrows=1)
        dates = pd.read_csv(p, usecols=[0], parse_dates=[0]).iloc[:, 0]
        step = dates.diff().dt.days.median()
        print(f"  {label:22s}: {len(dates)} hang, {len(head.columns)} cot, "
              f"{dates.min().date()} -> {dates.max().date()}, buoc trung vi = {step:.0f} ngay "
              f"=> {'MONTHLY' if step > 20 else 'DAILY'}")

    print()
    print("=" * 72)
    print("2. PHAN PHOI + ZERO-INFLATION  (plan §4.3)")
    print("=" * 72)
    mg = ai.merge(gprd, on="Date", how="inner").dropna(subset=["GPRD"])
    print(f"  mau chung (giao AI-GPR x GPRD): n={len(mg)}, "
          f"{mg.Date.min().date()} -> {mg.Date.max().date()}")
    print(f"  {'chuoi':16s} {'mean':>8s} {'sd':>8s} {'ac1':>7s} {'skew':>7s} "
          f"{'kurt':>8s} {'q95':>8s} {'q99':>8s} {'%zero':>7s}")
    for name in ["GPR_AI", "GPR_AER", "GPRD", "THREATS_GPR_AI", "ACTS_GPR_AI", "GPR_OIL"]:
        s = mg[name]
        print(f"  {name:16s} {s.mean():8.2f} {s.std():8.2f} {s.autocorr(1):7.3f} "
              f"{s.skew():7.2f} {s.kurtosis():8.1f} {s.quantile(.95):8.1f} "
              f"{s.quantile(.99):8.1f} {100 * (s == 0).mean():6.2f}%")
    print("  --- 8 cot oil-vung, ty le ngay bang 0 (anh huong thiet ke phan vi/trigger) ---")
    for c in oil:
        print(f"  {c:24s} {100 * (mg[c] == 0).mean():6.2f}% ngay bang 0")

    print()
    print("=" * 72)
    print("3. TU TUONG QUAN THEO TAN SUAT  (plan §4.3 'dai hon 0.73 vs 0.62')")
    print("=" * 72)
    wk = mg.set_index("Date").resample("W").mean(numeric_only=True)
    for label, frame in [("daily ", mg.set_index("Date")), ("weekly", wk)]:
        print(f"  {label}: ac1  AI-GPR={frame.GPR_AI.autocorr(1):.3f}  "
              f"GPR_AER={frame.GPR_AER.autocorr(1):.3f}  GPRD={frame.GPRD.autocorr(1):.3f}")
        print(f"  {label}: sd   AI-GPR={frame.GPR_AI.std():.2f}  "
              f"GPR_AER={frame.GPR_AER.std():.2f}  GPRD={frame.GPRD.std():.2f}")

    print()
    print("=" * 72)
    print("4. TUONG QUAN AI-GPR vs KEYWORD  (plan §3 'chi 0.69 -> sai so do')")
    print("=" * 72)
    print(f"  daily   corr(GPR_AI, GPR_AER) = {mg.GPR_AI.corr(mg.GPR_AER):.3f}")
    print(f"  daily   corr(GPR_AI, GPRD)    = {mg.GPR_AI.corr(mg.GPRD):.3f}")
    print(f"  weekly  corr(GPR_AI, GPR_AER) = {wk.GPR_AI.corr(wk.GPR_AER):.3f}")
    print(f"  weekly  corr(GPR_AI, GPRD)    = {wk.GPR_AI.corr(wk.GPRD):.3f}")
    sub = aim[aim.Date >= "1985-01-01"]
    print(f"  monthly corr(GPR_AI, GPR_AER) 1985+ = {sub.GPR_AI.corr(sub.GPR_AER):.3f}")
    print(f"  monthly corr(GPR_AI, GPR_AER) full  = {aim.GPR_AI.corr(aim.GPR_AER):.3f}")

    print()
    print("=" * 72)
    print("5. VAI TRO VIETNAM THEO GIAI DOAN  (plan §4.6 'gan nhu luon spillover')")
    print("=" * 72)
    cty = pd.read_csv(_find("ai_country"), parse_dates=["Date"])
    roles = [f"Vietnam_{r}" for r in ("initiator", "respondent", "spillover")]
    for lo, hi, label in [("1960-01-01", "2026-12-31", "toan mau 1960-2026"),
                          ("1960-01-01", "1989-12-31", "1960-1989"),
                          ("2015-01-01", "2026-12-31", "2015-2026 (cua so du an)")]:
        s = cty[(cty.Date >= lo) & (cty.Date <= hi)]
        tot = s[roles].sum()
        share = {r.split("_")[1]: round(float(100 * tot[r] / tot.sum()), 1) for r in roles}
        dom = (s[roles].idxmax(axis=1).str.split("_").str[1]
               .value_counts(normalize=True) * 100).round(1).to_dict()
        print(f"  {label:26s} n={len(s):4d}  %bien do={share}")
        print(f"  {'':26s}          %so thang ap dao={dom}")

    print()
    print("Xong. Moi so tren la doc tu file that trong data/, khong hard-code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
