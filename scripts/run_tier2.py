"""run_tier2.py — chay TANG 2 (G2a) end-to-end offline, sinh deliverable.

🔬 Research runner (docs/05 G2a, gate theo docs/09 §2.5). KHONG service hoa.
Doc GPR daily tu file + macro tu FRED (cache), uoc luong Local Projection tang 2, xuat:
  - docs/reports/G2a_<shock_type>_<data_version>.md   (KHONG bao gio ghi de)
  - docs/reports/figs/irf_<macro>_<shock>_<shock_type>_<version_tag>.png
  - docs/reports/data/tier2_irf_<shock_type>_<data_version>.csv

Chay:
    python scripts/run_tier2.py                        # innovation (mac dinh hop le), cache
    python scripts/run_tier2.py --shock-method zscore  # LEVEL doi chung, INELIGIBLE
    python scripts/run_tier2.py --refresh --horizon 20

Quy tac gate (sua theo review 08 §4.6): may KHONG tu phan GO/NO-GO — report co muc
Human review; run level tu danh dau INELIGIBLE (CLAUDE.md #9).
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


def _log1p(s):
    """log1p GPR de select_ar_order doc dung LEVEL (dataset.log1p_gpr)."""
    from gpr_engine.econometrics.dataset import log1p_gpr
    return log1p_gpr(s)

# Macro dua vao G2a: du 4 kenh (dxy da noi dai major<->broad, phu 1990+).
MACRO = list(CORE_MACRO)

MACRO_LABEL = {
    "oil": "Δln Oil (Brent)",
    "dxy": "Δln DXY (USD broad)",
    "vix": "VIX (level)",
    "us10y": "ΔUS10Y (yield %)",
}

# Loai shock -> co du dieu kien ket luan gate khong (CLAUDE.md #9: shock = innovation).
# Level-based van chay duoc (doi chung/lich su) nhung report tu danh dau KHONG ket luan.
GATE_ELIGIBLE_SHOCK_TYPES = {"innovation"}


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


def gate_checklist(irf: pd.DataFrame, shock: str, shock_type: str) -> tuple[str, list[str]]:
    """Cong G2a — 6 tieu chi (docs/09 §2.5, thay gate 'dung dau literature' cu).

    BO tieu chi ep dau ky vong (review 08 §4.6 — confirmation bias: trade war co the
    lam dau GIAM do cau yeu; ep mot dau la sai). May chi cham cac tieu chi co hoc:
      (1) pipeline dung        — precondition, ghi nhan tu metadata
      (2) IRF on dinh qua spec — bang robustness sub-sample trong report
      (3) CI bao day du        — luon co trong bang IRF
      (5) ket qua null van luu — moi kenh deu ghi, ke ca khong y nghia
    Tieu chi (4) 'dau & do lon CO giai thich kinh te' va (6) 'channel-specific >
    generic khi phu hop' la cua NGUOI REVIEW — may khong tu phan GO/NO-GO.

    Verdict toi da tu may: 'PENDING HUMAN REVIEW'. Neu shock la level (khong phai
    innovation) -> 'INELIGIBLE': khong duoc dung ket luan gate (CLAUDE.md #9).
    """
    notes = []
    for M in MACRO:
        sub = irf[(irf["macro_var"] == M) & (irf["shock"] == shock)]
        sig = sub[sub["pvalue"] < 0.10]
        if not len(sig):
            notes.append(f"- **{MACRO_LABEL.get(M, M)}**: không horizon nào p<0.10 "
                         f"— kết quả null, VẪN LƯU (tiêu chí 5).")
            continue
        peak = sig.loc[sig["beta"].abs().idxmax()]
        notes.append(
            f"- **{MACRO_LABEL.get(M, M)}**: {len(sig)}/{len(sub)} horizon p<0.10; "
            f"đỉnh |γ| tại h={int(peak['horizon'])} (γ={peak['beta']:+.4f}, "
            f"p={peak['pvalue']:.3f}). Dấu và độ lớn CẦN GIẢI THÍCH KINH TẾ "
            f"(tiêu chí 4 — người review; KHÔNG ép trùng kỳ vọng literature).")
    if shock_type not in GATE_ELIGIBLE_SHOCK_TYPES:
        verdict = "INELIGIBLE — shock là LEVEL, không phải innovation (CLAUDE.md #9); " \
                  "kết quả chỉ dùng đối chứng, KHÔNG kết luận gate"
    else:
        verdict = "PENDING HUMAN REVIEW — máy đã chấm tiêu chí 1/2/3/5; " \
                  "người review quyết tiêu chí 4/6 rồi ghi GO/NO-GO + lý do vào report này"
    return verdict, notes


def irf_table_md(irf: pd.DataFrame, shock: str, macro_std: dict, shock_std: dict,
                 horizons=(0, 1, 5, 10, 20, 30)) -> str:
    """Bang γ tai vai horizon chon loc, moi macro mot dong-block.

    β_std = γ * std(shock) / std(macro): so do lech chuan macro phan ung tren
    +1σ shock, dung cho ca innovation chua standardize va LEVEL z-score.
    """
    lines = ["| Macro | h | γ (beta) | β_std (σ/σ) | SE | p-value | 90% CI |",
             "|---|---|---|---|---|---|---|"]
    s_shock = shock_std.get(shock, 1.0)
    for M in MACRO:
        sd = macro_std.get(M, 1.0)
        for h in horizons:
            row = irf[(irf["macro_var"] == M) & (irf["shock"] == shock)
                      & (irf["horizon"] == h)]
            if not len(row):
                continue
            r = row.iloc[0]
            star = "**" if r["pvalue"] < 0.10 else ""
            bstd = r["beta"] * s_shock / sd if sd else float("nan")
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
        shock_sd = sub["GPRD"].std() or 1.0
        irf = estimate_tier2(sub, macro_vars=["vix"], shocks=["GPRD"],
                             horizons=range(0, max(hs) + 1), macro_lags=macro_lags)
        cells = []
        for h in hs:
            r = irf[irf["horizon"] == h]
            if not len(r):
                cells.append("—"); continue
            rr = r.iloc[0]
            mark = "*" if rr["pvalue"] < 0.10 else ""
            cells.append(f"{rr['beta'] * shock_sd / sd:+.3f}{mark}")
        lines.append(f"| {name} | {len(sub)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(irf: pd.DataFrame, panel: pd.DataFrame, meta: dict) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    shock_primary = DEFAULT_SHOCKS[0]  # GPRD
    shock_type = meta["shock_type"]
    verdict, notes = gate_checklist(irf, shock_primary, shock_type)
    macro_std = {M: float(panel[M].std()) for M in MACRO if M in panel.columns}
    shock_std = {s: float(panel[s].std()) for s in DEFAULT_SHOCKS if s in panel.columns}

    parts = []
    parts.append(f"# G2a — Global Macro Impact (Tầng 2 cascade) — shock: {shock_type}\n")
    parts.append("> 🔬 Research deliverable. Local Projection (Jordà 2005), "
                 "docs/07_formulas_reference_v2.md §3. Sinh tự động bởi `scripts/run_tier2.py`.\n")
    if shock_type not in GATE_ELIGIBLE_SHOCK_TYPES:
        parts.append("> ⚠️ **Shock trong run này là LEVEL (transform: "
                     f"{meta['shock_method']}), không phải innovation.** Theo "
                     "CLAUDE.md #9 / review 08 §4.4, hệ số của level KHÔNG đọc được "
                     "là 'tác động của cú sốc' — level autocorrelated cao nên "
                     "'coincident' gần như là kết quả mặc định. Run này chỉ dùng "
                     "làm ĐỐI CHỨNG với run innovation (G2.0).\n")
    parts.append("## Metadata\n")
    parts.append(f"- **shock_type**: `{shock_type}` (transform: `{meta['shock_method']}`)")
    parts.append(f"- **data_version** (sha256 GPR daily): `{meta['data_version']}`")
    if meta.get("ar_orders"):
        orders_str = ", ".join(f"{k}={v}" for k, v in sorted(meta["ar_orders"].items()))
        parts.append(f"- **AR order (PERSISTENT, BIC/dev-window, pre-registered)**: "
                     f"{orders_str} — spec khóa ở `config/hypothesis_registry.yaml`")
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
    parts.append("Gate 6 tiêu chí (docs/09 §2.5 — ĐÃ BỎ tiêu chí 'đúng dấu "
                 "literature', review 08 §4.6): (1) pipeline đúng · (2) IRF ổn định "
                 "qua spec · (3) CI đầy đủ · (4) dấu/độ lớn CÓ giải thích kinh tế "
                 "(người review, không ép trùng kỳ vọng) · (5) null vẫn lưu · "
                 "(6) channel-specific > generic khi phù hợp. Shock chính "
                 f"`{shock_primary}`:\n")
    parts.extend(notes)
    parts.append("")
    parts.append("### Human review (điền tay sau khi đọc kết quả)\n")
    parts.append("- Tiêu chí 4 — giải thích kinh tế cho từng kênh có ý nghĩa: _chưa điền_")
    parts.append("- Tiêu chí 6 — so channel-specific (chờ S-GPR): _chưa áp dụng_")
    parts.append("- **Kết luận người review (GO/NO-GO + lý do + ngày + người):** _chưa điền_\n")

    parts.append(f"## Bảng IRF (γ) — shock `{shock_primary}`\n")
    parts.append("γ = impulse response trên **1 đơn vị shock theo thang gốc**. "
                 "**β_std** = γ×std(shock)/std(macro) → 'số σ macro phản ứng trên 1σ "
                 "shock', so sánh được giữa các kênh (β_std≈0 cho DXY/oil là thật, "
                 "không phải lỗi). **In đậm** = p<0.10.\n")
    parts.append(irf_table_md(irf, shock_primary, macro_std, shock_std))
    parts.append("")

    parts.append("## Đồ thị IRF\n")
    for M in MACRO:
        parts.append(f"### {MACRO_LABEL.get(M, M)}\n")
        parts.append(
            f"![IRF {M}](figs/irf_{M}_{shock_primary}_{shock_type}_{meta['version_tag']}.png)\n")

    parts.append("## KĐ3 — Threat vs Act (β_std theo nhiều horizon)\n")
    parts.append("β_std = γ×std(shock)/std(macro) cho GPRD_THREAT vs GPRD_ACT — act có **mạnh & "
                 "trễ hơn** threat không? Câu hỏi global thuần túy. `*` = p<0.10.\n")
    parts.append("| Macro | shock | h=0 | h=1 | h=5 | h=10 | h=20 |")
    parts.append("|---|---|---|---|---|---|---|")
    ta_horizons = [0, 1, 5, 10, 20]
    for M in MACRO:
        sd = macro_std.get(M, 1.0) or 1.0
        for sh in ("GPRD_THREAT", "GPRD_ACT"):
            sh_sd = shock_std.get(sh, 1.0)
            cells = []
            for h in ta_horizons:
                r = irf[(irf["macro_var"] == M) & (irf["shock"] == sh)
                        & (irf["horizon"] == h)]
                if not len(r):
                    cells.append("—"); continue
                rr = r.iloc[0]
                mark = "*" if rr["pvalue"] < 0.10 else ""
                cells.append(f"{rr['beta'] * sh_sd / sd:+.3f}{mark}")
            parts.append(f"| {MACRO_LABEL.get(M, M)} | {sh.replace('GPRD_', '')} | "
                         + " | ".join(cells) + " |")
    parts.append("")

    parts.append("## Robustness — γ(VIX) qua sub-sample (tiêu chí 2: ổn định qua spec)\n")
    parts.append("β_std VIX theo GPRD trên các giai đoạn. Dấu/độ lớn ổn định qua "
                 "sub-sample → không phải artifact của 1 giai đoạn. Diễn giải dấu "
                 "là việc của người review (tiêu chí 4). `*` = p<0.10.\n")
    parts.append(vix_robustness_md(panel, meta["macro_lags"]))
    parts.append("")

    parts.append("## Ghi chú biến đổi & nhận diện (đọc kỹ)\n")
    parts.append(f"- **Transform shock**: `{meta['shock_method']}`. Contract: "
                 "LEVEL=log1p(GPR), INNOVATION=LEVEL−E[LEVEL|quá khứ]; JUMP tính "
                 "rolling trên raw để giữ thông tin đuôi. zscore/log1p trực tiếp chỉ "
                 "là LEVEL đối chứng.")
    parts.append("- **Information time + phiên thật**: GPR ngày D chỉ dùng từ D+1; "
                 "tin cuối tuần gộp vào phiên kế tiếp. Panel chỉ giữ ngày cả bốn macro "
                 "có quan sát, không forward-fill return/difference qua holiday.")
    parts.append("- **DXY nối dài**: DTWEXM (major, 1973→2019) nối DTWEXBGS (broad, "
                 "2006→) ở cấp return Δln (overlap 2006–2019 corr=0.926). Nhờ vậy có "
                 "đủ 4 kênh macro 1990+ thay vì chỉ 2006+ (broad-only).\n")

    parts.append("## Giới hạn & bước sau\n")
    parts.append("- Chưa orthogonalize giữa các shock (GPRD chứa cả threat+act); "
                 "transmission decomposition đầy đủ chờ tầng 3 (G2b).")
    parts.append("- Chưa tách theo `channel` (energy/trade) — cần S-GPR (G5). "
                 "Khi có, chạy lại theo channel (tiêu chí 6 của gate).")
    parts.append("- Diễn giải kết quả (leading/coincident, cơ chế kinh tế của dấu) "
                 "thuộc mục Human review phía trên — KHÔNG hard-code vào script.\n")

    out = REPORTS / f"G2a_{shock_type}_{meta.get('version_tag', meta['data_version'])}.md"
    if out.exists():
        raise FileExistsError(
            f"{out} đã tồn tại — không ghi đè report cũ (docs/10 F1). "
            "Đổi data_version hoặc xóa file cũ một cách CÓ CHỦ ĐÍCH rồi chạy lại.")
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# shock_method (transform) -> shock_type (ban chat cua bien). zscore/log1p van la
# LEVEL — chi doi thang do. "innovation" chi co khi G2.0 (shocks.py) cung cap.
SHOCK_METHOD_TO_TYPE = {"zscore": "level", "log1p": "level", "innovation": "innovation"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpr-path", default=DEFAULT_GPR_DAILY)
    ap.add_argument("--start", default="1990-01-02")
    ap.add_argument("--end", default=None)
    ap.add_argument("--horizon", type=int, default=30, help="max horizon (ngày)")
    ap.add_argument("--macro-lags", type=int, default=5,
                    help="số lag ρ của chính M (VIX rất dai, cần ≥5)")
    ap.add_argument("--shock-method", default="innovation",
                    choices=list(SHOCK_METHOD_TO_TYPE),
                    help="mac dinh innovation; zscore/log1p chi la LEVEL doi chung")
    ap.add_argument("--refresh", action="store_true", help="keo lai FRED (bo cache)")
    args = ap.parse_args()

    shock_type = SHOCK_METHOD_TO_TYPE[args.shock_method]
    # innovation (G2.0) nay da san sang: transform_gpr_shocks(method="innovation")
    # dung econometrics.shocks.innovation (AR-p rolling, no leakage). docs/10 D2/D3.

    print("[1/4] Xây panel tầng 2 (GPR file + FRED macro)...")
    panel = build_tier2_panel(
        gpr_path=args.gpr_path, start=args.start, end=args.end,
        refresh=args.refresh, shock_method=args.shock_method)
    print(f"      panel: {panel.shape[0]} ngày, {panel.index.min().date()} "
          f"→ {panel.index.max().date()}, cột: {list(panel.columns)}")

    print("[2/4] Ước lượng Local Projection tầng 2...")
    horizons = range(0, args.horizon + 1)
    irf = estimate_tier2(
        panel, macro_vars=MACRO, horizons=horizons, macro_lags=args.macro_lags)

    data_version = _data_version(args.gpr_path)
    # Innovation: spec order (AR) là bậc tự do -> phải vào version, nếu không report
    # order=5 và order=8 cùng data_version (chỉ hash file GPR) = versioning sai.
    ar_orders = None
    if args.shock_method == "innovation":
        from gpr_engine.econometrics.data_files import load_gpr_daily
        from gpr_engine.econometrics.shocks import DEFAULT_MAX_ORDER, select_ar_order
        _gpr = load_gpr_daily(args.gpr_path)
        ar_orders = {c: select_ar_order(_log1p(_gpr[c]), max_order=DEFAULT_MAX_ORDER)
                     for c in DEFAULT_SHOCKS if c in _gpr.columns}
        order_tag = "ar" + "-".join(str(ar_orders[c]) for c in sorted(ar_orders))
        version_tag = f"{data_version}_{order_tag}"
    else:
        version_tag = data_version

    DATADIR.mkdir(parents=True, exist_ok=True)
    irf_csv = DATADIR / f"tier2_irf_{shock_type}_{version_tag}.csv"
    irf.to_csv(irf_csv, index=False)
    print(f"      IRF rows: {len(irf)} → {irf_csv}")

    print("[3/4] Vẽ IRF...")
    FIGS.mkdir(parents=True, exist_ok=True)
    for M in MACRO:
        out = FIGS / f"irf_{M}_{DEFAULT_SHOCKS[0]}_{shock_type}_{version_tag}.png"
        plot_irf(irf, M, DEFAULT_SHOCKS[0], out)
    print(f"      {len(MACRO)} đồ thị → {FIGS}")

    print("[4/4] Viết report...")
    meta = {
        "shock_type": shock_type,
        "shock_method": args.shock_method,
        "data_version": data_version,
        "version_tag": version_tag,
        "ar_orders": ar_orders,
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
    print(f"\nDONE. Xem {report}")


if __name__ == "__main__":
    main()
