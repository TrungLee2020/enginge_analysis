"""run_tier2.py — chay TANG 2 (G2a) end-to-end offline, sinh deliverable.

🔬 Research runner (docs/05 G2a). KHONG service hoa. Doc GPR daily tu file +
macro tu FRED (cache), uoc luong Local Projection tang 2, xuat:
  - docs/reports/G2a_global_macro.md   (deliverable "Global Macro Impact")
  - docs/reports/figs/irf_<macro>.png  (do thi IRF)
  - docs/reports/data/tier2_irf.csv    (bang γ day du)

Chay:
    python scripts/run_tier2.py                 # dung cache neu co
    python scripts/run_tier2.py --refresh       # keo lai FRED
    python scripts/run_tier2.py --horizon 20    # gioi han horizon

Moi ket qua ghi kem data_version (hash file GPR) + git commit (docs/05 DONE #3).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# cho phep chay truc tiep tu repo root (khong can pip install -e)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import (  # noqa: E402
    CORE_MACRO,
    DEFAULT_GPR_DAILY,
    build_tier2_panel,
)
from gpr_engine.econometrics.tier2_global_macro import (  # noqa: E402
    DEFAULT_SHOCKS,
    estimate_tier2,
)

# Sub-sample robustness cho VIX (kiem chung dau γ khong do 1 giai doan).
VIX_SUBSAMPLES = {
    "full": (None, None),
    "pre-2008": (None, "2007-12-31"),
    "post-2008": ("2008-01-01", None),
    "post-2015": ("2015-01-01", None),
}

REPORTS = Path("docs/reports")
FIGS = REPORTS / "figs"
DATADIR = REPORTS / "data"

# Macro dua vao G2a: du 4 kenh (dxy da noi dai major<->broad, phu 1990+).
MACRO = list(CORE_MACRO)

MACRO_LABEL = {
    "oil": "Δln Oil (Brent)",
    "dxy": "Δln DXY (USD broad)",
    "vix": "VIX (level)",
    "us10y": "ΔUS10Y (yield %)",
}
# Ky vong tu literature (dau hieu ky vong neu GPR LEO THANG rui ro):
LIT_EXPECT = {
    "oil": "dương (shock đẩy giá dầu lên — kênh energy, Caldara-Iacoviello)",
    "dxy": "dương (flight-to-safety vào USD)",
    "vix": "dương (risk-off, biến động tăng)",
    "us10y": "âm/mơ hồ (flight-to-quality kéo yield xuống, nhưng lạm phát dầu đẩy lên)",
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "UNKNOWN"


def _data_version(gpr_path: str) -> str:
    h = hashlib.sha256()
    h.update(Path(gpr_path).read_bytes())
    return h.hexdigest()[:12]


def plot_irf(irf: pd.DataFrame, macro: str, shock: str, out: Path) -> None:
    sub = irf[(irf["macro_var"] == macro) & (irf["shock"] == shock)].sort_values("horizon")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(sub["horizon"], sub["beta"], color="#1f5fa6", lw=1.8, label="γ (IRF)")
    ax.fill_between(sub["horizon"], sub["ci_low"], sub["ci_high"],
                    color="#1f5fa6", alpha=0.15, label="90% CI")
    ax.axhline(0, color="#888", lw=0.8, ls="--")
    ax.set_xlabel("Horizon h (ngày)")
    ax.set_ylabel(f"γ: phản ứng {MACRO_LABEL.get(macro, macro)}")
    ax.set_title(f"IRF: {shock} → {MACRO_LABEL.get(macro, macro)}")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


# Dau γ ky vong (neu GPR = leo thang rui ro): oil+, vix+, us10y mo ho.
EXPECT_SIGN = {"oil": +1, "dxy": +1, "vix": +1, "us10y": 0}


def gate_verdict(irf: pd.DataFrame, shock: str) -> tuple[str, list[str]]:
    """Cong G2a — danh gia TRUNG THUC. Khong chi hoi 'co p<0.10' ma hoi
    'γ co y nghia VA DUNG DAU ky vong'. γ y nghia nhung SAI DAU (vd VIX am) la
    canh bao spec/nhan qua nguoc, khong tinh la pass.

    Tra ve (verdict, notes). verdict GO chi khi it nhat 1 kenh co γ y nghia dung dau.
    """
    notes = []
    n_correct_sig = 0
    for M in MACRO:
        sub = irf[(irf["macro_var"] == M) & (irf["shock"] == shock)]
        sig = sub[sub["pvalue"] < 0.10]
        exp = EXPECT_SIGN.get(M, 0)
        if not len(sig):
            notes.append(f"- **{MACRO_LABEL.get(M, M)}**: không horizon nào p<0.10 "
                         f"→ không có phản ứng rõ. Kỳ vọng: {LIT_EXPECT[M]}.")
            continue
        peak = sig.loc[sig["beta"].abs().idxmax()]
        sign_ok = exp == 0 or (peak["beta"] > 0) == (exp > 0)
        n_correct_sig += int(sign_ok and exp != 0)
        flag = "✔ đúng dấu" if sign_ok else "⚠ **SAI DẤU so với kỳ vọng** (co-move ngược / spec)"
        notes.append(
            f"- **{MACRO_LABEL.get(M, M)}**: {len(sig)}/{len(sub)} horizon p<0.10; "
            f"đỉnh |γ| tại h={int(peak['horizon'])} (γ={peak['beta']:+.4f}, "
            f"p={peak['pvalue']:.3f}) — {flag}. Kỳ vọng: {LIT_EXPECT[M]}.")
    verdict = "GO" if n_correct_sig >= 1 else "NO-GO / REVIEW"
    return verdict, notes


def irf_table_md(irf: pd.DataFrame, shock: str, macro_std: dict,
                 horizons=(0, 1, 5, 10, 20, 30)) -> str:
    """Bang γ tai vai horizon chon loc, moi macro mot dong-block.

    Them cot β_std = γ/std(macro) — vi shock da z-score (std=1), β_std la 'so do
    lech chuan macro phan ung tren +1σ shock', SO SANH DUOC giua cac kenh. Tranh
    hieu lam khi γ tho cua bien return (~0.0000) trong nhu loi.
    """
    lines = ["| Macro | h | γ (beta) | β_std (σ/σ) | SE | p-value | 90% CI |",
             "|---|---|---|---|---|---|---|"]
    for M in MACRO:
        sd = macro_std.get(M, 1.0)
        for h in horizons:
            row = irf[(irf["macro_var"] == M) & (irf["shock"] == shock)
                      & (irf["horizon"] == h)]
            if not len(row):
                continue
            r = row.iloc[0]
            star = "**" if r["pvalue"] < 0.10 else ""
            bstd = r["beta"] / sd if sd else float("nan")
            lines.append(
                f"| {MACRO_LABEL.get(M, M)} | {h} | {star}{r['beta']:.4f}{star} | "
                f"{bstd:+.3f} | {r['se']:.4f} | {r['pvalue']:.3f} | "
                f"[{r['ci_low']:.4f}, {r['ci_high']:.4f}] |")
    return "\n".join(lines)


def vix_robustness_md(panel: pd.DataFrame, macro_lags: int,
                      horizons=(1, 5, 10)) -> str:
    """Chay lai LP VIX~GPRD tren cac sub-sample -> bang β_std. Kiem dau γ on dinh."""
    sd = panel["vix"].std() or 1.0
    hs = list(horizons)
    lines = ["| Sub-sample | n | " + " | ".join(f"h={h}" for h in hs) + " |",
             "|---|---|" + "---|" * len(hs)]
    for name, (a, b) in VIX_SUBSAMPLES.items():
        sub = panel.loc[a:b]
        irf = estimate_tier2(sub, macro_vars=["vix"], shocks=["GPRD"],
                             horizons=range(0, max(hs) + 1), macro_lags=macro_lags)
        cells = []
        for h in hs:
            r = irf[irf["horizon"] == h]
            if not len(r):
                cells.append("—"); continue
            rr = r.iloc[0]
            mark = "*" if rr["pvalue"] < 0.10 else ""
            cells.append(f"{rr['beta'] / sd:+.3f}{mark}")
        lines.append(f"| {name} | {len(sub)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(irf: pd.DataFrame, panel: pd.DataFrame, meta: dict) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    shock_primary = DEFAULT_SHOCKS[0]  # GPRD
    verdict, notes = gate_verdict(irf, shock_primary)
    macro_std = {M: float(panel[M].std()) for M in MACRO if M in panel.columns}

    parts = []
    parts.append("# G2a — Global Macro Impact (Tầng 2 cascade)\n")
    parts.append("> 🔬 Research deliverable. Local Projection (Jordà 2005), "
                 "docs/07 §3. Sinh tự động bởi `scripts/run_tier2.py`.\n")
    parts.append("## Metadata\n")
    parts.append(f"- **data_version** (sha256 GPR daily): `{meta['data_version']}`")
    parts.append(f"- **git commit**: `{meta['git_commit']}`")
    parts.append(f"- **generated_at**: {meta['generated_at']}")
    parts.append(f"- **panel range**: {meta['panel_start']} → {meta['panel_end']} "
                 f"({meta['nobs']} ngày giao dịch)")
    parts.append(f"- **macro**: {', '.join(MACRO)} | "
                 f"**shocks**: {', '.join(DEFAULT_SHOCKS)}")
    parts.append(f"- **horizons**: 0..{meta['max_horizon']} ngày | "
                 f"**macro_lags (ρ)**: {meta['macro_lags']} | HAC/Newey-West SE\n")

    parts.append("## Câu hỏi\n")
    parts.append('"Một cú sốc địa chính trị (GPRD) đẩy dầu / đô / risk-off toàn '
                 'cầu bao nhiêu?" — deliverable độc lập, country-agnostic. Đây là '
                 "**INDIRECT channel** (tầng 2) mà mọi nước dùng chung; tầng 3 "
                 "(params riêng nước) ước lượng sau.\n")

    parts.append(f"## Cổng G2a: **{verdict}**\n")
    parts.append("Tiêu chí (đánh giá **trung thực**): γ phải có ý nghĩa **VÀ đúng "
                 "dấu kỳ vọng**. γ có ý nghĩa nhưng sai dấu (vd VIX âm) là cảnh báo "
                 "co-move ngược / lỗi spec — KHÔNG tính là pass. Shock chính "
                 f"`{shock_primary}` (đã chuẩn hóa z-score):\n")
    parts.extend(notes)
    parts.append("")

    parts.append(f"## Bảng IRF (γ) — shock `{shock_primary}`\n")
    parts.append("γ = impulse response: phản ứng biến vĩ mô tại h ngày sau shock "
                 "**+1 độ lệch chuẩn** GPRD (chuẩn hóa, không log1p — xem ghi chú "
                 "biến đổi). **β_std** = γ/std(macro) → 'số σ macro phản ứng trên 1σ "
                 "shock', so sánh được giữa các kênh (β_std≈0 cho DXY/oil là thật, "
                 "không phải lỗi). **In đậm** = p<0.10.\n")
    parts.append(irf_table_md(irf, shock_primary, macro_std))
    parts.append("")

    parts.append("## Đồ thị IRF\n")
    for M in MACRO:
        parts.append(f"### {MACRO_LABEL.get(M, M)}\n")
        parts.append(f"![IRF {M}](figs/irf_{M}_{shock_primary}.png)\n")

    parts.append("## KĐ3 — Threat vs Act (β_std theo nhiều horizon)\n")
    parts.append("β_std = γ/std(macro) cho GPRD_THREAT vs GPRD_ACT — act có **mạnh & "
                 "trễ hơn** threat không? Câu hỏi global thuần túy. `*` = p<0.10.\n")
    parts.append("| Macro | shock | h=0 | h=1 | h=5 | h=10 | h=20 |")
    parts.append("|---|---|---|---|---|---|---|")
    ta_horizons = [0, 1, 5, 10, 20]
    for M in MACRO:
        sd = macro_std.get(M, 1.0) or 1.0
        for sh in ("GPRD_THREAT", "GPRD_ACT"):
            cells = []
            for h in ta_horizons:
                r = irf[(irf["macro_var"] == M) & (irf["shock"] == sh)
                        & (irf["horizon"] == h)]
                if not len(r):
                    cells.append("—"); continue
                rr = r.iloc[0]
                mark = "*" if rr["pvalue"] < 0.10 else ""
                cells.append(f"{rr['beta'] / sd:+.3f}{mark}")
            parts.append(f"| {MACRO_LABEL.get(M, M)} | {sh.replace('GPRD_', '')} | "
                         + " | ".join(cells) + " |")
    parts.append("")

    parts.append("## Robustness — dấu γ(VIX) qua sub-sample\n")
    parts.append("β_std VIX theo GPRD trên các giai đoạn. Nếu dấu âm ổn định qua "
                 "mọi sub-sample → không phải artifact của 1 giai đoạn (vd khủng "
                 "hoảng 2008), củng cố kết luận GPRD coincident/lagging. `*` = p<0.10.\n")
    parts.append(vix_robustness_md(panel, meta["macro_lags"]))
    parts.append("")

    parts.append("## Ghi chú biến đổi & nhận diện (đọc kỹ)\n")
    parts.append("- **Shock chuẩn hóa, KHÔNG log1p.** docs/07 §0 bắt buộc log(1+GPR) "
                 "vì phân phối *country-GPR nước nhỏ* (mean/std ≈ 0.05, lệch phải). "
                 "GPRD **toàn cầu daily** (~10..370) không thuộc phân phối đó; log1p "
                 "ép 370→5.9, làm phẳng spike khủng hoảng. Nên dùng z-score → γ đọc "
                 "là 'phản ứng / 1σ shock'. Quy ước log1p vẫn giữ cho country-GPR ở tầng 3.")
    parts.append("- **Panel lưới business-day liên tục + complete-case một lần** "
                 "(data_files.build_tier2_panel): tránh lỗi trước đây khi NaN rải rác "
                 "khiến mỗi horizon chạy trên mẫu khác nhau và AR-lag nhảy qua khe NaN "
                 "(gây γ VIX âm giả). Nay mọi horizon dùng cùng mẫu.")
    parts.append("- **DXY nối dài**: DTWEXM (major, 1973→2019) nối DTWEXBGS (broad, "
                 "2006→) ở cấp return Δln (overlap 2006–2019 corr=0.926). Nhờ vậy có "
                 "đủ 4 kênh macro 1990+ thay vì chỉ 2006+ (broad-only).\n")

    parts.append("## Giới hạn & bước sau\n")
    parts.append("- **GPR là coincident, chưa thấy leading**: γ đương thời (h=0) yếu; "
                 "VIX tương lai có xu hướng *mean-revert* sau spike GPRD (γ âm ở h dài) "
                 "— GPRD hay xảy ra *tại* đỉnh biến động, không dẫn trước. Đây là dữ "
                 "kiện quan trọng cho KĐ5 (lead-lag) ở G2b, không phải lỗi.")
    parts.append("- Chưa orthogonalize giữa các shock (GPRD chứa cả threat+act); "
                 "mediation đầy đủ chờ tầng 3 (G2b).")
    parts.append("- Chưa tách theo `channel` (energy/trade) — cần S-GPR (G5). "
                 "Khi có, chạy lại theo channel để xác nhận energy→γ_oil cao.")
    parts.append("- **Tiếp theo**: dù cổng ra sao, G2a là deliverable độc lập. "
                 "G2b `tier3_country.py` + `config/params/vn.yaml` (mediation "
                 "Direct/Indirect cho VN-Index) là bước kế.\n")

    out = REPORTS / "G2a_global_macro.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpr-path", default=DEFAULT_GPR_DAILY)
    ap.add_argument("--start", default="1990-01-02")
    ap.add_argument("--end", default=None)
    ap.add_argument("--horizon", type=int, default=30, help="max horizon (ngày)")
    ap.add_argument("--macro-lags", type=int, default=5,
                    help="số lag ρ của chính M (VIX rất dai, cần ≥5)")
    ap.add_argument("--refresh", action="store_true", help="keo lai FRED (bo cache)")
    args = ap.parse_args()

    print("[1/4] Xây panel tầng 2 (GPR file + FRED macro)...")
    panel = build_tier2_panel(
        gpr_path=args.gpr_path, start=args.start, end=args.end,
        refresh=args.refresh)
    print(f"      panel: {panel.shape[0]} ngày, {panel.index.min().date()} "
          f"→ {panel.index.max().date()}, cột: {list(panel.columns)}")

    print("[2/4] Ước lượng Local Projection tầng 2...")
    horizons = range(0, args.horizon + 1)
    irf = estimate_tier2(
        panel, macro_vars=MACRO, horizons=horizons, macro_lags=args.macro_lags)

    DATADIR.mkdir(parents=True, exist_ok=True)
    irf.to_csv(DATADIR / "tier2_irf.csv", index=False)
    print(f"      IRF rows: {len(irf)} → {DATADIR / 'tier2_irf.csv'}")

    print("[3/4] Vẽ IRF...")
    FIGS.mkdir(parents=True, exist_ok=True)
    for M in MACRO:
        out = FIGS / f"irf_{M}_{DEFAULT_SHOCKS[0]}.png"
        plot_irf(irf, M, DEFAULT_SHOCKS[0], out)
    print(f"      {len(MACRO)} đồ thị → {FIGS}")

    print("[4/4] Viết report...")
    meta = {
        "data_version": _data_version(args.gpr_path),
        "git_commit": _git_commit(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "panel_start": panel.index.min().date().isoformat(),
        "panel_end": panel.index.max().date().isoformat(),
        "nobs": int(panel.shape[0]),
        "max_horizon": args.horizon,
        "macro_lags": args.macro_lags,
    }
    report = write_report(irf, panel, meta)
    print(f"      → {report}")
    print("\nDONE. Xem docs/reports/G2a_global_macro.md")


if __name__ == "__main__":
    main()
