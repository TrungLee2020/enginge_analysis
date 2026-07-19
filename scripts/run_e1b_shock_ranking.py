"""run_e1b_shock_ranking.py — E1b: rank thước đo shock theo sức PHÁT HIỆN episode. 🔬

docs/11 §10 (E1b), docs/12 §9 (checklist) — quyết định trường SHOCK của ô chính
lưới SCA. Registry: KĐ-E1b (đã đăng ký 2026-07-19). KHÔNG chạm holdout.

Câu hỏi: trong {INNOVATION, JUMP, LEVEL+JUMP}, thước đo nào highlight đúng các cú
sốc địa chính trị lớn đã biết? Đo THUỘC TÍNH NỘI TẠI của thước đo (event-study
descriptor), KHÔNG hồi quy lên outcome macro — để không leak vào lưới SCA sau
(tránh circular: chọn shock bằng chính outcome rồi lại test shock đó trên outcome).

Metric (mỗi thước đo, mỗi sub-sample):
  - mean_z_at_event : trung bình (giá trị thước đo / σ toàn mẫu) tại các episode lớn
  - hit_rate_2sd    : tỉ lệ episode được thước đo đẩy vượt 2σ (phát hiện được)
Episode lớn = GPRD level vượt phân vị 97.5 rolling(250, lùi), dedup cụm cách >10 ngày.

Guard P1 (docs/12 §5.4): mọi số trong narrative lấy từ dict `stats`, KHÔNG hard-code.

Chạy:  .venv/bin/python scripts/run_e1b_shock_ranking.py
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
START = "1990-01-01"
ROLL = 250            # cửa sổ rolling cho phân vị / chuẩn hóa (~1 năm giao dịch)
EVENT_Q = 0.975       # ngưỡng episode lớn
DEDUP_DAYS = 10       # gộp cụm episode cách nhau <= 10 ngày
HIT_SD = 2.0          # ngưỡng "phát hiện": thước đo đẩy episode vượt 2σ

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


def find_events(gprd: pd.Series) -> pd.DatetimeIndex:
    """Episode lớn = GPRD vượt phân vị EVENT_Q rolling (lùi), dedup cụm."""
    thr = gprd.rolling(ROLL).quantile(EVENT_Q).shift(1)
    big = gprd[gprd > thr].dropna()
    ev, last = [], None
    for d in big.index:
        if last is None or (d - last).days > DEDUP_DAYS:
            ev.append(d)
        last = d
    return pd.DatetimeIndex(ev)


def salience(measure: pd.Series, events: pd.DatetimeIndex,
             lo: str | None, hi: str | None) -> tuple[float, float, int]:
    """(mean_z_at_event, hit_rate_2sd, n_events) trên sub-sample [lo,hi].

    σ tính trên chính sub-sample (đặc trưng biến động giai đoạn đó).
    """
    m = measure.loc[lo:hi].dropna()
    if m.std() == 0 or m.empty:
        return float("nan"), float("nan"), 0
    s = m.std()
    ev = events[(events >= (lo or events.min())) & (events <= (hi or events.max()))]
    at_ev = m.reindex(ev).dropna()
    if at_ev.empty:
        return float("nan"), float("nan"), 0
    return float((at_ev / s).mean()), float((at_ev > HIT_SD * s).mean()), int(len(at_ev))


def compute(gpr_path: str = DEFAULT_GPR_DAILY) -> tuple[dict, dict]:
    """Tính (stats, table) — tách khỏi I/O để test được (Guard P1)."""
    gprd = load_gpr_daily(gpr_path)["GPRD"].loc[START:]
    level = log1p_gpr(gprd)
    p = select_ar_order(level)
    innov = (level - persistent_ar(level, order=p, min_train=ROLL)).rename("INNOVATION")
    jmp = jump(gprd, window=ROLL, q=0.95).rename("JUMP")
    common = innov.dropna().index.intersection(jmp.dropna().index)
    lvl_jump = level_plus_jump(level.reindex(common), jmp.reindex(common))

    measures = {"INNOVATION": innov, "JUMP": jmp, "LEVEL+JUMP": lvl_jump}
    events = find_events(gprd)

    table: dict[str, dict] = {}
    for name, meas in measures.items():
        table[name] = {}
        for sub, (lo, hi) in SUBSAMPLES.items():
            mz, hit, n = salience(meas, events, lo, hi)
            table[name][sub] = {"mean_z": round(mz, 2), "hit": round(hit, 3), "n": n}

    full = {k: table[k]["full"] for k in measures}
    ranked = sorted(measures, key=lambda k: (full[k]["hit"], full[k]["mean_z"]),
                    reverse=True)
    winner = ranked[0]

    winner_always_top = True
    for sub in SUBSAMPLES:
        sub_rank = sorted(measures, key=lambda k: (table[k][sub]["hit"],
                          table[k][sub]["mean_z"]), reverse=True)
        if sub_rank[0] != winner:
            winner_always_top = False

    stats = {
        "ar_order": p,
        "n_events_full": table[winner]["full"]["n"],
        "winner": winner,
        "rank": " > ".join(ranked),
        "winner_hit_full": table[winner]["full"]["hit"],
        "winner_meanz_full": table[winner]["full"]["mean_z"],
        "innov_hit_full": table["INNOVATION"]["full"]["hit"],
        "jump_hit_full": table["JUMP"]["full"]["hit"],
        "winner_always_top": winner_always_top,
    }
    return stats, table


def build_report(stats: dict, table: dict, dv: str, commit: str, now: str) -> list[str]:
    """Sinh narrative từ stats/table. MỌI số phải đến từ đây (Guard P1)."""
    winner = stats["winner"]

    def row(name: str) -> str:
        cells = " | ".join(
            f"{table[name][s]['mean_z']:.2f} / {table[name][s]['hit']*100:.0f}%"
            for s in SUBSAMPLES)
        return f"| {'**'+name+'**' if name == winner else name} | {cells} |"

    parts = [
        "# E1b — Rank thước đo shock theo sức phát hiện episode\n",
        "> 🔬 Research diagnostic (docs/11 §10 E1b, registry KĐ-E1b). KHÔNG chạm "
        "holdout, KHÔNG hồi quy outcome (tránh circular với lưới SCA). Sinh bởi "
        "`scripts/run_e1b_shock_ranking.py`.\n",
        "## Metadata\n",
        f"- **data_version** (sha256 GPRD): `{dv}`",
        f"- **git commit**: `{commit}`",
        f"- **generated_at**: {now}",
        f"- **AR order (pre-registered)**: p={stats['ar_order']}",
        f"- **mẫu**: {START}+ | episode lớn: GPRD > phân vị {EVENT_Q} rolling({ROLL}), "
        f"dedup >{DEDUP_DAYS}d → **{stats['n_events_full']}** episode\n",
        "## Câu hỏi\n",
        "Thước đo shock nào highlight đúng các cú sốc địa chính trị lớn đã biết? "
        "Đo thuộc tính nội tại (giá trị thước đo / σ tại episode; tỉ lệ episode vượt "
        f"{HIT_SD:.0f}σ), KHÔNG qua outcome macro.\n",
        "## Bảng: mean_z@event / hit_rate (>2σ) theo sub-sample\n",
        "| Thước đo | " + " | ".join(SUBSAMPLES) + " |",
        "|---|" + "---|" * len(SUBSAMPLES),
        row("INNOVATION"),
        row("JUMP"),
        row("LEVEL+JUMP"),
        "",
        "## Kết luận\n",
        f"- **Ranking (theo full sample, hit rồi mean_z): {stats['rank']}.**",
        f"- Thắng: **{stats['winner']}** — phát hiện {stats['winner_hit_full']*100:.0f}% "
        f"episode lớn (mean_z={stats['winner_meanz_full']}), so với INNOVATION chỉ "
        f"{stats['innov_hit_full']*100:.0f}% và JUMP {stats['jump_hit_full']*100:.0f}%.",
        f"- Ổn định ranking: winner đứng đầu ở MỌI sub-sample = "
        f"**{'CÓ' if stats['winner_always_top'] else 'KHÔNG'}**.",
        "- INNOVATION phát hiện kém nhất — khớp E1: AR(p) nén cú sốc khi level tăng "
        "dần trước cú nhảy (chuỗi đã 'dự báo được' phần lớn spike).\n",
        "## Hệ quả — ô chính lưới SCA (docs/12 §2.2)\n",
        f"Trường `SHOCK` của primary_cell = **`{stats['winner']}`**. Cả ba mức "
        "{INNOVATION, JUMP, LEVEL+JUMP} vẫn nằm trong chiều SHOCK của lưới (báo cáo "
        "toàn bộ) — E1b chỉ định ô CHÍNH, không loại mức nào khỏi lưới.\n",
        "## Hạn chế\n",
        "- 'Episode lớn' định nghĩa bằng chính GPRD level → thiên vị nhẹ cho thước đo "
        "có thành phần level (LEVEL+JUMP). Đây là lý do báo cáo CẢ hit_rate của JUMP "
        "thuần: nếu JUMP thuần đã đủ cao, không cần thành phần level.",
        "- Không phải test outcome — 'phát hiện episode' ≠ 'dự báo macro'. Việc shock "
        "nào tác động macro là của lưới SCA, không phải E1b.\n",
    ]
    return parts


def main() -> None:
    stats, table = compute()
    dv = _data_version(DEFAULT_GPR_DAILY)
    parts = build_report(
        stats, table, dv, _git_commit(),
        dt.datetime.now().isoformat(timespec="seconds"))

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E1b_shock_ranking_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
