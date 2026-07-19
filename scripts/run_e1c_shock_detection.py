"""run_e1c_shock_detection.py — E1c: rank thước đo shock bằng AUC, sự kiện NGOẠI SINH. 🔬

docs/13 §2 — thay E1b. Vấn đề E1b (docs/13 §1): định nghĩa episode (GPRD>q97.5)
NỘI SINH với chính GPRD → ranking phần lớn do cấu tạo, không do dữ liệu. E1c sửa
hai lỗi:
  §1.1 sự kiện ngoại sinh (gold set dựng tay, KHÔNG tra GPRD) thay episode nội sinh.
  §1.2 AUC (Mann-Whitney) thay ngưỡng 2σ — AUC bất biến với biến đổi đơn điệu nên
       miễn nhiễm zero-inflation của JUMP và skew của LEVEL (2σ không so được).

AUC_m = P(m tại ngày sự kiện > m tại ngày không sự kiện). 0.5 = ngẫu nhiên.

Phép thử tự bác bỏ (docs/13 §2.5): chạy SONG SONG endo (GPRD>q97.5, đối chứng) +
exo (gold set). Nếu LEVEL thắng tuyệt đối ở endo mà không ở exo → xác nhận E1b đo
tính đơn điệu, bản exo là bản dùng.

Ràng buộc (docs/13 §2.6): KHÔNG chạm holdout, KHÔNG hồi quy outcome, report versioned,
Guard P1 (mọi số từ stats). Thước đo: INNOVATION, JUMP, LEVEL+JUMP, LEVEL (§2.4).

Chạy:  .venv/bin/python scripts/run_e1c_shock_detection.py
  - Có data/gold_events.csv  -> chạy cả exo + endo.
  - Không có                 -> chỉ endo (đối chứng) + cảnh báo gold set là blocker.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import DEFAULT_GPR_DAILY, load_gpr_daily  # noqa: E402
from gpr_engine.econometrics.dataset import log1p_gpr  # noqa: E402
from gpr_engine.econometrics.shocks import (  # noqa: E402
    jump,
    level_plus_jump,
    persistent_ar,
    select_ar_order,
)

REPORTS = Path("docs/reports")
GOLD = Path("data/gold_events.csv")
START = "1990-01-01"
ROLL = 250
EVENT_BUFFER = 10        # ±10 phiên quanh sự kiện bị loại khỏi nhóm "không sự kiện"
EVENT_WINDOW = 1         # ngày sự kiện ± 1 phiên tính là "sự kiện"
B_BOOT = 2000            # bootstrap CI (phân tầng theo năm)
SEED = 42

SUBSAMPLES = {
    "full": (None, None),
    "pre-2008": (None, "2007-12-31"),
    "2008-2015": ("2008-01-01", "2015-12-31"),
    "post-2015": ("2016-01-01", None),
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _data_version(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# AUC — thuần, test được không cần mạng
# ---------------------------------------------------------------------------
def event_and_control_masks(index: pd.DatetimeIndex, events: pd.DatetimeIndex,
                            window: int = EVENT_WINDOW, buffer: int = EVENT_BUFFER
                            ) -> tuple[np.ndarray, np.ndarray]:
    """Mask (event, control) trên index. event = ±window quanh sự kiện; control =
    ngoài ±buffer quanh MỌI sự kiện (vùng đệm chống nhiễm)."""
    idx = pd.DatetimeIndex(index)
    ev_days = pd.DatetimeIndex([])
    near_days = pd.DatetimeIndex([])
    for e in pd.DatetimeIndex(events):
        ev_days = ev_days.union(pd.date_range(e - pd.Timedelta(days=window),
                                              e + pd.Timedelta(days=window)))
        near_days = near_days.union(pd.date_range(e - pd.Timedelta(days=buffer),
                                                  e + pd.Timedelta(days=buffer)))
    event_mask = idx.isin(ev_days)
    control_mask = ~idx.isin(near_days)
    return event_mask, control_mask


def auc(measure: pd.Series, events: pd.DatetimeIndex,
        window: int = EVENT_WINDOW, buffer: int = EVENT_BUFFER) -> tuple[float, int, int]:
    """AUC Mann-Whitney: P(m@event > m@control). Trả (auc, n_event, n_control).

    AUC bất biến với biến đổi đơn điệu -> so được giữa JUMP (zero-inflated) và
    LEVEL (skew). NaN nếu quá ít quan sát.
    """
    from scipy.stats import mannwhitneyu

    m = measure.dropna()
    ev_mask, ctrl_mask = event_and_control_masks(m.index, events, window, buffer)
    a, b = m[ev_mask].to_numpy(), m[ctrl_mask].to_numpy()
    if len(a) < 3 or len(b) < 3:
        return float("nan"), len(a), len(b)
    U, _ = mannwhitneyu(a, b, alternative="greater")
    return float(U / (len(a) * len(b))), len(a), len(b)


def auc_ci(measure: pd.Series, events: pd.DatetimeIndex, b: int = B_BOOT,
           seed: int = SEED) -> tuple[float, float]:
    """CI 95% cho AUC bằng bootstrap phân tầng theo năm (docs/13 §2.3)."""
    m = measure.dropna()
    rng = np.random.default_rng(seed)
    years = m.index.year
    uniq_years = np.unique(years)
    boots = []
    for _ in range(b):
        # rút lại các năm (phân tầng): giữ cấu trúc trong năm
        pick = rng.choice(uniq_years, size=len(uniq_years), replace=True)
        idx = np.concatenate([np.where(years == y)[0] for y in pick])
        ms = m.iloc[idx]
        val, na, nb = auc(ms, events)
        if not np.isnan(val):
            boots.append(val)
    if not boots:
        return float("nan"), float("nan")
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


# ---------------------------------------------------------------------------
# Sự kiện
# ---------------------------------------------------------------------------
def endo_events(gprd: pd.Series) -> pd.DatetimeIndex:
    """Đối chứng: episode = GPRD > q97.5 rolling, dedup >10 ngày (như E1b)."""
    thr = gprd.rolling(ROLL).quantile(0.975).shift(1)
    big = gprd[gprd > thr].dropna()
    ev, last = [], None
    for d in big.index:
        if last is None or (d - last).days > 10:
            ev.append(d)
        last = d
    return pd.DatetimeIndex(ev)


def load_gold_events() -> pd.DatetimeIndex | None:
    """Gold set ngoại sinh (data/gold_events.csv). None nếu chưa có (blocker)."""
    if not GOLD.exists():
        return None
    df = pd.read_csv(GOLD, parse_dates=["event_date"])
    return pd.DatetimeIndex(df["event_date"].dropna().unique())


# ---------------------------------------------------------------------------
def build_measures(gprd: pd.Series) -> dict[str, pd.Series]:
    level = log1p_gpr(gprd)
    p = select_ar_order(level)
    innov = (level - persistent_ar(level, order=p, min_train=ROLL)).rename("INNOVATION")
    jmp = jump(gprd, window=ROLL, q=0.95).rename("JUMP")
    common = innov.dropna().index.intersection(jmp.dropna().index)
    return {
        "INNOVATION": innov.reindex(common),
        "JUMP": jmp.reindex(common),
        "LEVEL+JUMP": level_plus_jump(level.reindex(common), jmp.reindex(common)),
        "LEVEL": level.reindex(common).rename("LEVEL"),
    }, p


def compute(measures: dict[str, pd.Series], events: pd.DatetimeIndex,
            with_ci: bool = True) -> dict:
    """Bảng AUC theo thước đo × sub-sample (+CI cho full)."""
    table: dict[str, dict] = {}
    for name, m in measures.items():
        table[name] = {}
        for sub, (lo, hi) in SUBSAMPLES.items():
            ev = events[(events >= (lo or events.min())) &
                        (events <= (hi or events.max()))]
            a, ne, nc = auc(m.loc[lo:hi], ev)
            table[name][sub] = {"auc": round(a, 3) if not np.isnan(a) else None,
                                "n_event": ne, "n_control": nc}
        if with_ci:
            lo95, hi95 = auc_ci(m, events)
            table[name]["ci_full"] = [round(lo95, 3), round(hi95, 3)]
    return table


def rank(table: dict) -> list[str]:
    return sorted(table, key=lambda k: (table[k]["full"]["auc"] or 0), reverse=True)


def main() -> None:
    gprd = load_gpr_daily(DEFAULT_GPR_DAILY)["GPRD"].loc[START:]
    measures, p = build_measures(gprd)

    ev_endo = endo_events(gprd)
    ev_exo = load_gold_events()

    endo_tbl = compute(measures, ev_endo)
    exo_tbl = compute(measures, ev_exo) if ev_exo is not None else None

    dv = _data_version(DEFAULT_GPR_DAILY)
    stats = {
        "ar_order": p,
        "n_endo_events": len(ev_endo),
        "n_exo_events": len(ev_exo) if ev_exo is not None else 0,
        "endo_rank": " > ".join(rank(endo_tbl)),
        "endo_winner": rank(endo_tbl)[0],
        "exo_available": ev_exo is not None,
    }
    if exo_tbl is not None:
        stats["exo_rank"] = " > ".join(rank(exo_tbl))
        stats["exo_winner"] = rank(exo_tbl)[0]

    parts = build_report(stats, endo_tbl, exo_tbl, dv, _git_commit(),
                         dt.datetime.now().isoformat(timespec="seconds"))
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E1c_shock_detection_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


def build_report(stats: dict, endo: dict, exo: dict | None,
                 dv: str, commit: str, now: str) -> list[str]:
    def tbl(table: dict, label: str) -> list[str]:
        lines = [f"### AUC — {label}\n",
                 "| Thước đo | " + " | ".join(SUBSAMPLES) + " | CI 95% (full) |",
                 "|---|" + "---|" * (len(SUBSAMPLES) + 1)]
        for name in rank(table):
            cells = " | ".join(str(table[name][s]["auc"]) for s in SUBSAMPLES)
            ci = table[name].get("ci_full", ["–", "–"])
            lines.append(f"| {name} | {cells} | [{ci[0]}, {ci[1]}] |")
        return lines

    parts = [
        "# E1c — Rank thước đo shock bằng AUC (sự kiện ngoại sinh)\n",
        "> 🔬 Research diagnostic (docs/13 §2, registry KĐ-E1c). THAY E1b: sửa lỗi "
        "episode nội sinh (§1.1) + ngưỡng 2σ không so được (§1.2). AUC bất biến biến "
        "đổi đơn điệu. KHÔNG chạm holdout, KHÔNG hồi quy outcome. Sinh bởi "
        "`scripts/run_e1c_shock_detection.py`.\n",
        "## Metadata\n",
        f"- **data_version**: `{dv}` · **git**: `{commit}` · **generated_at**: {now}",
        f"- **AR order (pre-registered)**: p={stats['ar_order']} · **B bootstrap**: {B_BOOT} · seed={SEED}",
        f"- **sự kiện endo** (GPRD>q97.5, đối chứng): {stats['n_endo_events']} · "
        f"**exo (gold set)**: {stats['n_exo_events']}\n",
    ]
    if not stats["exo_available"]:
        parts.append(
            "> 🛑 **CHƯA CÓ `data/gold_events.csv`** — chỉ chạy được bản ENDO (đối "
            "chứng). Bản EXO (bản DÙNG để chốt ô chính) chặn bởi gold set: cần 2 người "
            "dựng tay, KHÔNG tra GPRD (docs/13 §2.2, cổng G-Gold). primary_cell.shock "
            "KHÔNG được chốt từ bản endo.\n")
    parts += ["## Kết quả\n", *tbl(endo, "ENDO (GPRD>q97.5 — ĐỐI CHỨNG, không dùng chốt)")]
    if exo is not None:
        parts += ["", *tbl(exo, "EXO (gold set ngoại sinh — BẢN DÙNG)")]
        parts += [
            "", "## Phép thử tự bác bỏ (docs/13 §2.5)\n",
            f"- endo rank: {stats['endo_rank']}",
            f"- exo rank: {stats['exo_rank']}",
            ("- Nếu LEVEL/LEVEL+JUMP thắng tuyệt đối ở endo mà KHÔNG ở exo → xác nhận "
             "E1b đo tính đơn điệu theo GPRD, không đo sức phát hiện. Bản exo là bản dùng."),
        ]
    else:
        parts += [
            "", "## Phép thử tự bác bỏ (docs/13 §2.5)\n",
            f"- endo rank (đối chứng): **{stats['endo_rank']}**.",
            "- CHƯA chạy được bản exo → chưa kết luận. Dựng gold set trước.",
        ]
    parts += [
        "", "## Ghi chú AUC vs hit-rate E1b\n",
        "AUC bất biến biến đổi đơn điệu nên chấm INNOVATION công bằng hơn hit-rate "
        "2σ của E1b (E1b méo vì JUMP zero-inflated, LEVEL skew — docs/13 §1.2). "
        "So AUC endo với hit-rate E1b để thấy mức độ méo của E1b.\n",
        "## Hệ quả ô chính SCA-01\n",
        "Chỉ chốt `primary_cell.shock` từ bản EXO khi: một thước đo thắng rõ, ổn định "
        "qua sub-sample, CI không chồng lấn (docs/13 §3). Nếu không → SHOCK MỞ (§3.1): "
        "báo cáo cả 4 mức, Holm trên 4×H.\n",
    ]
    return parts


if __name__ == "__main__":
    main()
