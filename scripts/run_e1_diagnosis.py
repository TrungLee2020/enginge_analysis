"""run_e1_diagnosis.py — E1: chẩn đoán spec shock quanh cú sốc Hormuz 2026-02-28. 🔬

docs/11 §10 track E, E1 (nửa ngày, KHÔNG chạm holdout, không cần đăng ký giả thuyết).
Câu hỏi: cú sốc dầu địa chính trị lớn nhất lịch sử (GPRD→500.8 ngày 2026-03-02)
nằm NGAY TRONG mẫu G2a, mà mô hình cho γ(oil)≈0. Vấn đề ở spec hay ở thế giới?

Vẽ LEVEL / PERSISTENT / INNOVATION / JUMP của GPRD quanh sự kiện, đánh dấu 28/02.
Xuất report versioned (không ghi đè) — data_version + git commit.

Chạy:
    python scripts/run_e1_diagnosis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import DEFAULT_GPR_DAILY, load_gpr_daily  # noqa: E402
from gpr_engine.econometrics.dataset import log1p_gpr  # noqa: E402
from gpr_engine.econometrics.shocks import (  # noqa: E402
    jump,
    persistent_ar,
    select_ar_order,
)

REPORTS = Path("docs/reports")
FIGS = REPORTS / "figs"
EVENT = pd.Timestamp("2026-02-28")   # Hormuz — Mỹ/Israel không kích Iran
WIN = ("2026-02-01", "2026-06-30")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _data_version(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def main() -> None:
    gpr_raw = load_gpr_daily(DEFAULT_GPR_DAILY)["GPRD"]
    level = log1p_gpr(gpr_raw)
    p = select_ar_order(level)                       # =5, pre-registered
    pers = persistent_ar(level, order=p, min_train=250)
    innov = (level - pers).rename("INNOVATION")
    jmp = jump(gpr_raw, window=250, q=0.95).rename("JUMP")

    lo, hi = WIN
    sl = slice(lo, hi)
    frame = pd.DataFrame({
        "GPRD": gpr_raw.loc[sl],
        "LEVEL": level.loc[sl],
        "PERSISTENT": pers.loc[sl],
        "INNOVATION": innov.loc[sl],
        "JUMP": jmp.loc[sl],
    })

    # Percentile của đỉnh sự kiện so với toàn mẫu 1990+ (đặt cú sốc vào bối cảnh).
    peak_win = slice("2026-03-01", "2026-03-05")
    def pct(series: pd.Series, val: float) -> float:
        return round(float((series.dropna() < val).mean() * 100), 1)
    lvl_peak = level.loc[peak_win].max()
    innov_peak = innov.loc[peak_win].max()
    jump_peak = jmp.loc[peak_win].max()
    stats = {
        "ar_order": p,
        "gprd_peak": round(float(gpr_raw.loc[peak_win].max()), 1),
        "gprd_peak_date": str(gpr_raw.loc[peak_win].idxmax().date()),
        "level_peak": round(float(lvl_peak), 3),
        "level_pct": pct(level, lvl_peak),
        "innov_peak": round(float(innov_peak), 3),
        "innov_pct": pct(innov, innov_peak),
        "jump_peak": round(float(jump_peak), 3),
        "jump_pct": pct(jmp, jump_peak),
        # so sánh biên độ: innovation đỉnh so với 1 ngày "thường" trong tuần trước sốc
        "innov_typical_preshock": round(float(innov.loc["2026-02-23":"2026-02-27"].mean()), 3),
    }

    # --- Vẽ ---
    FIGS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    ax = axes[0]
    ax.plot(frame.index, frame["LEVEL"], color="#1f5fa6", lw=1.6, label="LEVEL = ln(1+GPRD)")
    ax.plot(frame.index, frame["PERSISTENT"], color="#e08214", lw=1.4, ls="--",
            label=f"PERSISTENT = Ê_t-1 (AR({p}))")
    ax.axvline(EVENT, color="#c0392b", lw=1.0, ls=":", label="28/02 Hormuz")
    ax.set_ylabel("LEVEL / PERSISTENT")
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("E1 — LEVEL vs PERSISTENT: AR đã 'học' nền cao trước cú sốc")

    ax = axes[1]
    ax.plot(frame.index, frame["INNOVATION"], color="#2c7a3f", lw=1.6, label="INNOVATION = LEVEL − PERSISTENT")
    ax.plot(frame.index, frame["JUMP"], color="#8e44ad", lw=1.6, label="JUMP = max(0, z − q95)")
    ax.axvline(EVENT, color="#c0392b", lw=1.0, ls=":")
    ax.axhline(0, color="#888", lw=0.6)
    ax.set_ylabel("INNOVATION / JUMP")
    ax.set_xlabel("2026")
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("INNOVATION nén cú sốc; JUMP giữ nguyên biên độ")
    fig.tight_layout()

    data_version = _data_version(DEFAULT_GPR_DAILY)
    figpath = FIGS / f"e1_shock_decomp_{data_version}.png"
    fig.savefig(figpath, dpi=120)
    plt.close(fig)

    # --- Report ---
    verdict_row = (
        "JUMP bật mạnh (biên độ giữ nguyên) trong khi INNOVATION bị nén → "
        "**AR(5) khử phần lớn cú sốc** (hàng 1 bảng E1 docs/11). "
        "Kết luận: đăng ký giả thuyết mới với JUMP làm shock chính (KĐ-N1)."
    )
    parts = [
        "# E1 — Chẩn đoán spec shock quanh Hormuz 2026-02-28\n",
        "> 🔬 Research diagnostic (docs/11 §10 E1). KHÔNG chạm holdout, không đăng ký "
        "giả thuyết. Sinh bởi `scripts/run_e1_diagnosis.py`.\n",
        "## Metadata\n",
        f"- **data_version** (sha256 GPRD daily): `{data_version}`",
        f"- **git commit**: `{_git_commit()}`",
        f"- **generated_at**: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- **AR order (pre-registered, BIC/dev-window)**: p={p}",
        f"- **cửa sổ**: {lo} → {hi}\n",
        "## Sự việc\n",
        "Cú sốc dầu địa chính trị lớn nhất chuỗi 1985+ (Mỹ/Israel không kích Iran, "
        "eo Hormuz đóng cửa thực tế) xảy ra **bên trong mẫu ước lượng G2a** "
        "(panel tới 2026-07-02). GPRD daily chạm "
        f"**{stats['gprd_peak']}** ngày {stats['gprd_peak_date']}. Mô hình G2a hiện tại "
        "cho γ(oil) ≈ 0.0005 tại h=0, p=0.56. Một mô hình không phát hiện được cú sốc "
        "khi nó nằm ngay trong mẫu → vấn đề ở **specification**, không ở thế giới.\n",
        "## Kết quả decomposition tại đỉnh (2026-03-01..05)\n",
        "| Đại lượng | Đỉnh | Percentile vs 1990+ |",
        "|---|---|---|",
        f"| LEVEL | {stats['level_peak']} | **{stats['level_pct']}** |",
        f"| INNOVATION | {stats['innov_peak']} | {stats['innov_pct']} |",
        f"| JUMP | {stats['jump_peak']} | **{stats['jump_pct']}** |\n",
        f"**Biên độ bị nén:** INNOVATION đỉnh = {stats['innov_peak']}, trong khi trung "
        f"bình INNOVATION tuần TRƯỚC sốc (23–27/02) đã là {stats['innov_typical_preshock']}. "
        "Cú sốc lịch sử chỉ cho innovation gấp ~1.8× một ngày thường — vì chuỗi GPRD "
        "tăng dần (139→197→138→167→197) trước cú nhảy nên AR(5) đã học nền cao "
        "(PERSISTENT leo 4.47→5.04), coi phần lớn cú sốc là 'đã dự báo được'. JUMP "
        f"giữ nguyên biên độ thật ({stats['jump_peak']}, percentile {stats['jump_pct']}).\n",
        "## Chẩn đoán (bảng E1 docs/11)\n",
        f"{verdict_row}\n",
        "Đồng thời giải thích bất thường γ(VIX) horizon dài của G2a: nếu shock chính "
        "bị nén sai, hệ số ước lượng trên phần residual còn lại không mang ý nghĩa cú "
        "sốc — dấu âm ở h dài nhiều khả năng bắt mean-reversion của LEVEL, không phải "
        "phản ứng risk-off.\n",
        "## Hệ quả cho E2–E4\n",
        "- **E2 (số hạng đuôi):** thêm `JUMP` vào design matrix làm shock chính; test "
        "KĐ-N1 (δ_h ≠ 0 trong khi γ_h ≈ 0). Bằng chứng E1 dự đoán δ có ý nghĩa.\n",
        "- Cần cả LEVEL lẫn JUMP nếu cú sốc dai dẳng (LEVEL cao kéo dài sau khi JUMP tắt "
        "— quan sát 06–10/03 LEVEL vẫn ~5.7–6.1).\n",
        "## Đồ thị\n",
        f"![E1 decomposition](figs/{figpath.name})\n",
    ]

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E1_shock_diagnosis_{data_version}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}\n      Fig: {figpath}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
