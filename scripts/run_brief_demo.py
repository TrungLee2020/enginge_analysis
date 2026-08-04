"""run_brief_demo.py — Model Brief THAT tren du lieu THAT (docs/14 §8). 🏭 demo

Muc dich: chung minh CA CHUOI tang 4 chay duoc end-to-end tren du lieu that, chu
khong chi tren fixture. Day la thu ma unit test khong the thay: loi tich hop chi
lo ra khi bang γ that gap analogue that gap guard that.

Chuoi:
    GPRD daily that -> shock measures -> descriptor
      -> trigger: JUMP vuot nguong phan vi (chan A, docs/15 §3 "trigger tam")
      -> analogue k-NN tren outcome vi mo THAT (panel thang)
      -> o bang γ that (doc tu docs/reports/data/t2_full_holm_*.csv)
      -> composer + Guard P1 -> Model Brief
      -> ghi vao track record de cham CRPS ve sau

⚠️ DAY LA DEMO, KHONG PHAI SAN PHAM. Cu the:
  - trigger dung JUMP chan A vi chan B chua co collector (docs/15 §3);
  - o γ lay tu bang da chay, KHONG uoc luong lai — brief phai doc tu artifact
    versioned, khong tu tinh lai roi ra so khac bang γ da cong bo;
  - `predictive` cua brief la tran claim, khong phai xac nhan holdout (g0 §2).

Chay:  python scripts/run_brief_demo.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.analogue import (  # noqa: E402
    batch_analogues,
    build_descriptor,
)
from gpr_engine.econometrics.data_files import (  # noqa: E402
    build_monthly_panel,
    load_gpr_daily,
)
from gpr_engine.econometrics.shocks import build_shocks  # noqa: E402
from gpr_engine.reporting.composer import (  # noqa: E402
    GammaCell,
    compose_model_brief,
)
from gpr_engine.scoring.track_record import (  # noqa: E402
    Forecast,
    TrackRecord,
    unconditional_baseline,
)

REPORTS = Path("docs/reports")
GAMMA_GLOB = "data/t2_full_holm_*.csv"
TRACK_PATH = REPORTS / "data" / "track_record.jsonl"

TRIGGER_PCTILE = 95.0        # JUMP vuot phan vi nay -> ban bat thuong
ANALOGUE_HORIZONS = (1, 2, 6)
TAUS = (0.10, 0.25, 0.50, 0.75, 0.90)


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "UNKNOWN"


def load_gamma_cells(panel: pd.DataFrame,
                     outcome_filter: set[str] | None = None
                     ) -> tuple[list[GammaCell], str]:
    """Doc o γ ĐÃ SỐNG SÓT tu artifact versioned. KHONG uoc luong lai.

    Brief phai trich tu bang γ da cong bo — tinh lai o day se cho so khac bang
    γ (seed sup-t, mau, spec) va hai van ban cua cung san pham noi hai dieu.

    Dong gop CHUAN HOA (`beta_std`) la BAT BUOC (docs/16 §2.2 dieu kien 1). Bang
    γ cu chua co cot do; khi thieu thi tinh tai cho tu sd cua chinh cot shock
    trong panel — CUNG mot cong thuc runner dung, khong phai xap xi khac.
    """
    files = sorted((REPORTS).glob(GAMMA_GLOB))
    if not files:
        raise FileNotFoundError(
            f"Không thấy {GAMMA_GLOB} trong {REPORTS}. Chạy "
            "`python scripts/run_t2_full.py` trước — brief đọc từ bảng γ đã "
            "công bố, không tự ước lượng lại.")
    path = files[-1]
    df = pd.read_csv(path)
    sub = df[(df["reject"]) & (df["battery"] == "b")]
    if outcome_filter:
        sub = sub[sub["outcome"].isin(outcome_filter)]

    prefix = {"pooled": "GPR", "act": "GPR_ACT", "threat": "GPR_THREAT"}
    cells = []
    for _, r in sub.iterrows():
        if "beta_std" in sub.columns and pd.notna(r.get("beta_std")):
            std = float(r["beta_std"])
        else:
            col = f"{prefix[r['channel']]}_{r['measure']}"
            std = float(r["beta"]) * float(panel[col].std())
        cells.append(GammaCell(
            outcome=f"{r['outcome']} ({r['measure']}·{r['channel']})",
            horizon=int(r["horizon"]), beta=float(r["beta"]),
            pvalue=float(r["pvalue"]), standardized=std,
            survived_holm=True, survived_battery=True))
    return cells, path.name


def find_trigger(jump: pd.Series, pctile: float) -> tuple[pd.Timestamp, float, float]:
    """Ngay JUMP gan nhat vuot nguong phan vi (expanding, khong lookahead)."""
    from gpr_engine.indices.s_gpr import expanding_percentile

    pct = expanding_percentile(jump.dropna(), min_periods=250)
    hits = pct[pct > pctile]
    if hits.empty:
        raise RuntimeError(f"Không ngày nào JUMP vượt phân vị {pctile}.")
    when = hits.index[-1]
    return when, float(jump.loc[when]), float(pct.loc[when])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    print("[1/6] GPRD daily + shock measures...")
    gpr = load_gpr_daily()
    measures = build_shocks(gpr[["GPRD", "GPRD_ACT", "GPRD_THREAT"]])
    when, jump_val, jump_pct = find_trigger(measures["GPRD_JUMP"], TRIGGER_PCTILE)
    print(f"      trigger: {when.date()} · JUMP={jump_val:.2f} (phân vị {jump_pct:.1f})")

    print("[2/6] Panel tháng (outcome vĩ mô thật)...")
    panel = build_monthly_panel(refresh=args.refresh, shock_axis=True,
                                components=True, real_macro=True, freight=True)

    print("[3/6] Descriptor + analogue trên dữ liệu thật...")
    monthly_shocks = pd.DataFrame({
        "LEVEL": panel["GPR_LEVEL"], "INNOVATION": panel["GPR_INNOVATION"],
        "JUMP": (panel["GPR_LEVEL_PLUS_JUMP"] - panel["GPR_LEVEL"]).clip(lower=0),
        "ACT": panel["GPR_ACT_LEVEL"], "THREAT": panel["GPR_THREAT_LEVEL"],
    })
    desc = build_descriptor(monthly_shocks, macro=panel[["vix", "dxy", "oil"]])
    # as_of = tháng gần nhất có descriptor đầy đủ (không dùng tháng tương lai).
    as_of = desc.dropna().index[-1]
    outcomes = panel[["ip", "cpi", "infl_exp", "vix"]]
    ana, skipped = batch_analogues(desc, outcomes, as_of, ANALOGUE_HORIZONS)
    print(f"      as_of={as_of.date()} · {len(ana)} ô có tiền lệ, "
          f"{len(skipped)} ô im lặng (n<5)")

    print("[4/6] Ô bảng γ (đọc từ artifact versioned)...")
    cells, gamma_file = load_gamma_cells(panel)
    print(f"      {len(cells)} ô sống sót từ {gamma_file}")

    print("[5/6] Compose brief (Guard P1 chặn ở cửa ra)...")
    trigger = {"label": "bản bất thường · sốc đuôi chân A",
               "reason": f"JUMP={jump_val:.2f} vượt phân vị {jump_pct:.1f} "
                         f"ngày {when.date()}"}
    meta = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "data_version": gamma_file.split("_")[-1].replace(".csv", ""),
            "git_commit": _git_commit(), "n_obs": int(len(panel)),
            "sample_caveat": "track tháng chưa có holdout"}
    payload = {"jump": jump_val, "jump_pctile": jump_pct,
               "n_analogue": len(ana), "n_skipped": len(skipped)}
    brief = compose_model_brief(trigger, cells, ana, payload, meta, skipped=skipped)

    print("[6/6] Ghi brief + đăng ký dự báo vào track record...")
    tr = TrackRecord.load(TRACK_PATH)
    n_new = 0
    for a in ana:
        fid = f"{as_of.date()}_{a.outcome_name}_h{a.horizon}"
        if fid in {f.forecast_id for f in tr._items.values()}:
            continue
        hist = outcomes[a.outcome_name].loc[:as_of]
        try:
            baseline = unconditional_baseline(hist, TAUS, as_of=as_of)
        except ValueError:
            continue
        # Phân phối có điều kiện = phân vị của chính các tiền lệ (analogue),
        # KHÔNG phải γ: γ cho phản ứng trung bình, analogue cho phân phối.
        vals = sorted(nb.outcome for nb in a.neighbours)
        q = {f"{t:.2f}": float(pd.Series(vals).quantile(t)) for t in TAUS}
        tr.record(Forecast(
            forecast_id=fid, issued_at=as_of,
            target_date=as_of + pd.DateOffset(months=a.horizon),
            outcome_name=a.outcome_name, quantiles=q, baseline_quantiles=baseline,
            model_version="analogue-v1", data_version=meta["data_version"]))
        n_new += 1
    tr.save(TRACK_PATH)

    out = REPORTS / f"BRIEF_demo_{as_of.date()}_{meta['data_version']}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè.")
    out.write_text(brief, encoding="utf-8")
    print(f"      {n_new} dự báo mới vào track record ({TRACK_PATH})")
    print(f"\nDONE → {out}")
    print(f"Track record: {len(tr)} dự báo, {len(tr.pending)} chờ kết cục.")


if __name__ == "__main__":
    main()
