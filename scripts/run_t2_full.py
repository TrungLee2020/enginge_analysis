"""run_t2_full.py — PHASE 1a: bang γ tang 2 day du (track THANG). 🔬 research

docs/14 §2 muc 1a. Deliverable: bang γ dau tien noi mot dieu ve THE GIOI thay vi
ve chinh pipeline. Chay offline (file GPR + FRED cache), khong can PostgreSQL.

SPEC — moi dong duoi day la mot quyet dinh DA KY, khong phai lua chon cua runner:
  - TRUC SHOCK {LEVEL, INNOVATION, LEVEL+JUMP}: g0 §7.1 = A
    (DEC-2026-08-02-shock-axis). Bao cao ca ba, KHONG chon. Cong eligibility o
    `econometrics.shock_axis` — LEVEL/LEVEL+JUMP chi doc duoc voi lag_augmented.
  - SUY DIEN lag_augmented + HC1 + dai sup-t: SCA-01.lp_inference (registry).
  - HO KIEM DINH = nhom outcome pre-register: docs/14 §6.6 = B
    (DEC-2026-08-02-holm-family). Holm trong ho, tai focal horizons da khoa.
  - FOCAL HORIZONS {1,2,6} thang: SCA-01.primary_cell.focal_horizons (khoa may).
  - BATTERY a/b CUNG MAU + control DONG THUOC DO voi shock: docs/14 §2 1a.

CHAY:
    python scripts/run_t2_full.py                 # day du (~vai phut)
    python scripts/run_t2_full.py --no-quantile   # bo nhanh phan vi (nhanh hon)
    python scripts/run_t2_full.py --refresh       # keo lai FRED

Guard P1 (docs/12 §5.4): MOI so trong narrative lay tu dict `stats`. Them so vao
report = them truong vao `stats` roi tham chieu. Khong go tay.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import (  # noqa: E402
    DEFAULT_GPR_DAILY,
    DEFAULT_GPR_MONTHLY,
    MONTHLY_JUMP_MIN_PERIODS,
    MONTHLY_JUMP_WINDOW,
    align_monthly_gpr_to_information_time,
    benchmark_vintage,
    build_monthly_panel,
    build_monthly_shock_axis,
    freight_vintage,
    load_benchmark_monthly,
    real_macro_vintage,
)
from gpr_engine.econometrics.multiplicity import (  # noqa: E402
    PREREGISTERED_OUTCOME_FAMILIES,
    holm_by_family,
)
from gpr_engine.econometrics.shock_axis import (  # noqa: E402
    SHOCK_MEASURES,
    gate_shock_eligibility,
    shock_column,
)
from gpr_engine.econometrics.tier2_global_macro import estimate_tier2  # noqa: E402

REPORTS = Path("docs/reports")
DATADIR = REPORTS / "data"

# --- spec khoa (khong sua o day; sua o registry/g0 roi doi cho khop) -----------
INFERENCE = "lag_augmented"      # SCA-01.lp_inference.method
LAGS = 6                         # p+1 voi p=5 (AR order khoa cho GPRD)
HORIZONS = range(0, 25)          # h=0..24 thang (docs/14 §2 1a)
FOCAL_HORIZONS = (1, 2, 6)       # SCA-01.primary_cell.focal_horizons
TAUS = (0.10, 0.25, 0.50, 0.75, 0.90)
ALPHA = 0.10                     # muc y nghia dung xuyen suot repo (CI 90%)
CI = 0.90
SEED = 0

CHANNELS = {"pooled": "GPR", "act": "GPR_ACT", "threat": "GPR_THREAT"}
BATTERY_CONTROLS = ("epu_us", "epu_global")

OUTCOME_LABEL = {
    "oil": "Δln Oil (Brent)", "dxy": "Δln DXY", "vix": "VIX (level)",
    "us10y": "ΔUS10Y (%)", "ip": "IP (100·Δln)", "cpi": "CPI (Δln)",
    "infl_exp": "Kỳ vọng lạm phát (Δ)", "freight": "Cước biển (Δln PPI)",
}
FAMILY_LABEL = {"asset_price": "Giá tài sản", "real_macro": "Vĩ mô thực",
                "physical_channel": "Kênh vật lý"}
MEASURE_LABEL = {"LEVEL": "LEVEL", "INNOVATION": "INNOVATION",
                 "LEVEL_PLUS_JUMP": "LEVEL+JUMP"}


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "UNKNOWN"


def _data_version(*paths: str) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:12]


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
def build_panel(start: str, end: str | None, refresh: bool) -> pd.DataFrame:
    """Panel thang: truc shock x 3 kenh + 8 outcome + battery DONG THUOC DO.

    Battery khong dung `battery=True` cua build_monthly_panel: cai do tra EPU o
    LEVEL thoi. Rang buoc docs/14 §2 1a muc 2 doi control CUNG THUOC DO voi
    shock — so LEVEL-control voi INNOVATION-shock se thoi phong phan "rieng cua
    GPR". Nen dung day dung `build_monthly_shock_axis` cho ca EPU, roi moi
    thuoc do dung control cua chinh no.

    Mot MAU DUY NHAT (complete-case toan bo) de moi o so sanh duoc: ban a vs b,
    va ba thuoc do voi nhau. Chi phi: xem `sample_cost` trong report.
    """
    raw = load_benchmark_monthly(start, end, refresh=refresh, wui_path=None)
    axis = pd.concat(
        [build_monthly_shock_axis(raw[c].dropna(), prefix=c) for c in raw.columns],
        axis=1)
    # EPU thang M cung chi biet sau khi thang M ket thuc — align GIONG GPR, neu
    # khong thi control nhin truoc shock mot thang.
    axis = align_monthly_gpr_to_information_time(axis)
    return build_monthly_panel(
        start=start, end=end, refresh=refresh, shock_axis=True, components=True,
        real_macro=True, freight=True, battery=False, extra_monthly=axis)


def outcomes_present(panel: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Ho outcome pre-register, loc theo cot thuc su co trong panel."""
    return {fam: tuple(o for o in members if o in panel.columns)
            for fam, members in PREREGISTERED_OUTCOME_FAMILIES.items()}


# ---------------------------------------------------------------------------
# Uoc luong
# ---------------------------------------------------------------------------
def estimate_gamma(panel: pd.DataFrame, families: dict) -> pd.DataFrame:
    """Bang γ: measure x channel x outcome x battery x horizon, OLS + sup-t."""
    rows = []
    for measure in SHOCK_MEASURES:
        for chan, prefix in CHANNELS.items():
            shock = shock_column(prefix, measure)
            if shock not in panel.columns:
                continue
            for battery in ("a", "b"):
                controls = ([f"{c}_{measure}" for c in BATTERY_CONTROLS]
                            if battery == "b" else [])
                for fam, outs in families.items():
                    for out in outs:
                        irf = estimate_tier2(
                            panel, macro_vars=[out], shocks=[shock],
                            controls=controls, horizons=HORIZONS,
                            macro_lags=0,               # lag_augmented tu them
                            inference=INFERENCE, lags=LAGS, simultaneous=True,
                            ci=CI, seed=SEED)
                        irf = irf.rename(columns={"macro_var": "outcome"})
                        irf["measure"] = measure
                        irf["channel"] = chan
                        irf["family"] = fam
                        irf["battery"] = battery
                        # ĐÓNG GÓP CHUẨN HÓA — bắt buộc, không phải tiện ích.
                        # docs/16 §2.2 điều kiện 1 + E2: hệ số THÔ của hai thước
                        # đo/hai thành phần nằm trên regressor khác phương sai
                        # nên KHÔNG so được. In γ thô cạnh nhau là tái lập đúng
                        # ngộ nhận mà E2 đã bác (48.9% ô đảo chiều).
                        irf["beta_std"] = irf["beta"] * float(panel[shock].std())
                        rows.append(irf)
    out = pd.concat(rows, ignore_index=True)
    return out[["measure", "channel", "outcome", "family", "battery", "horizon",
                "beta", "beta_std", "se", "tstat", "pvalue", "ci_low", "ci_high",
                "ci_low_supt", "ci_high_supt", "supt_c", "nobs", "converged"]]


def estimate_quantiles(panel: pd.DataFrame, families: dict,
                       channel: str = "pooled") -> pd.DataFrame:
    """Hoi quy phan vi tai TAUS. sup-t KHONG ap dung (can bootstrap, chua lam).

    Chi chay kenh `pooled`: luoi day du (3 kenh x 5 tau) khong them thong tin
    cho cau hoi cua Phase 1a ("phan phoi dich chuyen hay day duoi") ma nhan 3
    lan chi phi. Pham vi nay GHI RA day, khong am tham thu hep.
    """
    prefix = CHANNELS[channel]
    rows = []
    for measure in SHOCK_MEASURES:
        shock = shock_column(prefix, measure)
        for battery in ("a", "b"):
            controls = ([f"{c}_{measure}" for c in BATTERY_CONTROLS]
                        if battery == "b" else [])
            for tau in TAUS:
                for fam, outs in families.items():
                    for out in outs:
                        irf = estimate_tier2(
                            panel, macro_vars=[out], shocks=[shock],
                            controls=controls, horizons=HORIZONS, macro_lags=0,
                            inference=INFERENCE, lags=LAGS, simultaneous=False,
                            method="quantile", tau=tau, ci=CI)
                        irf = irf.rename(columns={"macro_var": "outcome"})
                        irf["measure"] = measure
                        irf["channel"] = channel
                        irf["family"] = fam
                        irf["battery"] = battery
                        irf["tau"] = tau
                        rows.append(irf)
    out = pd.concat(rows, ignore_index=True)
    return out[["measure", "channel", "outcome", "family", "battery", "tau",
                "horizon", "beta", "se", "pvalue", "ci_low", "ci_high", "nobs",
                "converged"]]


def apply_holm(gamma: pd.DataFrame, families: dict) -> pd.DataFrame:
    """Holm TRONG HO outcome, tai tung (measure, channel, battery, horizon focal).

    Mot kiem dinh = mot (outcome, shock) tai mot horizon focal. KHONG quet ca 25
    horizon vao day: chieu horizon da do dai sup-t xu ly (docs/14 §1.3), phat
    lai la mat het power.
    """
    focal = gamma[gamma["horizon"].isin(FOCAL_HORIZONS)].copy()
    parts = []
    keys = ["measure", "channel", "battery", "horizon"]
    for _, grp in focal.groupby(keys, sort=False):
        parts.append(holm_by_family(grp, families, outcome_col="outcome",
                                    pvalue_col="pvalue", alpha=ALPHA))
    out = pd.concat(parts, ignore_index=True)
    # holm_by_family ghi de cot `family` — gia tri trung khop, giu mot ban.
    return out


# ---------------------------------------------------------------------------
# Thong ke cho narrative (Guard P1: report CHI duoc doc tu day)
# ---------------------------------------------------------------------------
def compute_stats(panel: pd.DataFrame, gamma: pd.DataFrame, holm: pd.DataFrame,
                  quant: pd.DataFrame | None, families: dict,
                  elapsed: float) -> dict:
    surv = holm[holm["reject"]]
    surv_b = surv[surv["battery"] == "b"]
    stats = {
        "n_obs": int(panel.shape[0]),
        "n_outcomes": sum(len(v) for v in families.values()),
        "n_measures": len(SHOCK_MEASURES),
        "n_channels": len(CHANNELS),
        "n_horizons": len(list(HORIZONS)),
        "max_horizon": max(HORIZONS),
        "n_gamma_rows": int(len(gamma)),
        "n_focal_tests": int(len(holm)),
        "n_survive_holm": int(len(surv)),
        "n_survive_holm_battery": int(len(surv_b)),
        "n_raw_sig": int((holm["pvalue"] < ALPHA).sum()),
        "alpha": ALPHA,
        "lags": LAGS,
        "jump_window": MONTHLY_JUMP_WINDOW,
        "jump_min_periods": MONTHLY_JUMP_MIN_PERIODS,
        "elapsed_sec": round(elapsed, 1),
        "supt_c_min": round(float(gamma["supt_c"].min()), 3),
        "supt_c_max": round(float(gamma["supt_c"].max()), 3),
        "n_quantile_rows": int(len(quant)) if quant is not None else 0,
        "n_taus": len(TAUS),
        # QuantReg (IRLS) khong hoi tu thi statsmodels WARN roi tra he so vong
        # lap cuoi — so van chay thang vao report. Dem ra day de nguoi doc biet
        # bao nhieu o khong dang tin, thay vi de warning bay len stderr roi mat.
        "n_quantile_not_converged": (0 if quant is None
                                     else int((~quant["converged"]).sum())),
        "n_gamma_not_converged": int((~gamma["converged"]).sum()),
    }
    # Ket qua manh nhat (theo p-value) trong so cac o SONG SOT battery + Holm.
    if len(surv_b):
        best = surv_b.loc[surv_b["pvalue"].idxmin()]
        stats.update({
            "top_outcome": best["outcome"], "top_measure": best["measure"],
            "top_channel": best["channel"], "top_horizon": int(best["horizon"]),
            "top_beta": round(float(best["beta"]), 4),
            "top_pvalue": round(float(best["pvalue"]), 4),
            "top_pvalue_adj": round(float(best["pvalue_adj"]), 4),
            "top_family": best["family"],
        })
    # Ty le sup-t cat 0: bao nhieu (measure,channel,outcome) co IRF ra khoi dai
    # dong thoi o it nhat 1 horizon — do la doc IRF DUNG cach (khong pointwise).
    g = gamma[gamma["battery"] == "b"]
    excl = (g["ci_low_supt"] > 0) | (g["ci_high_supt"] < 0)
    cells = g.groupby(["measure", "channel", "outcome"]).size()
    hit = g[excl].groupby(["measure", "channel", "outcome"]).size()
    stats["n_cells"] = int(len(cells))
    stats["n_cells_supt_excl_zero"] = int(len(hit))
    # Dong thuan qua truc SHOCK: o nao ma CA BA thuoc do cung song sot Holm.
    if len(surv_b):
        by_cell = surv_b.groupby(["channel", "outcome", "horizon"])["measure"].nunique()
        stats["n_cells_all_three_measures"] = int((by_cell == len(SHOCK_MEASURES)).sum())
    else:
        stats["n_cells_all_three_measures"] = 0
    return stats


def family_sizes(families: dict) -> dict[str, int]:
    return {k: len(v) for k, v in families.items()}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def gamma_table_md(holm: pd.DataFrame, battery: str, measure: str) -> str:
    """Bang focal-horizon cho mot (measure, battery): outcome x horizon."""
    sub = holm[(holm["battery"] == battery) & (holm["measure"] == measure)
               & (holm["channel"] == "pooled")]
    lines = ["| Họ | Outcome | h | γ | SE | p | p_Holm | sống sót |",
             "|---|---|---|---|---|---|---|---|"]
    for fam in PREREGISTERED_OUTCOME_FAMILIES:
        rows = sub[sub["family"] == fam].sort_values(["outcome", "horizon"])
        for _, r in rows.iterrows():
            mark = "**✓**" if r["reject"] else "—"
            lines.append(
                f"| {FAMILY_LABEL[fam]} | {OUTCOME_LABEL.get(r['outcome'], r['outcome'])} "
                f"| {int(r['horizon'])} | {r['beta']:+.4f} | {r['se']:.4f} "
                f"| {r['pvalue']:.3f} | {r['pvalue_adj']:.3f} | {mark} |")
    return "\n".join(lines)


def axis_summary_md(holm: pd.DataFrame) -> str:
    """So o song sot Holm theo (thuoc do x ho) — doc truc SHOCK trong mot bang."""
    sub = holm[holm["battery"] == "b"]
    fams = list(PREREGISTERED_OUTCOME_FAMILIES)
    lines = ["| Thước đo | " + " | ".join(FAMILY_LABEL[f] for f in fams) + " | Tổng |",
             "|---|" + "---|" * (len(fams) + 1)]
    for m in SHOCK_MEASURES:
        cells, tot = [], 0
        for f in fams:
            n = int(sub[(sub["measure"] == m) & (sub["family"] == f)]["reject"].sum())
            cells.append(str(n))
            tot += n
        lines.append(f"| {MEASURE_LABEL[m]} | " + " | ".join(cells) + f" | {tot} |")
    return "\n".join(lines)


def quantile_table_md(quant: pd.DataFrame, measure: str) -> str:
    """γ theo τ tai focal horizons, ban battery b, kenh pooled."""
    sub = quant[(quant["measure"] == measure) & (quant["battery"] == "b")
                & (quant["horizon"].isin(FOCAL_HORIZONS))]
    lines = ["| Outcome | h | " + " | ".join(f"τ={t:.2f}" for t in TAUS) + " |",
             "|---|---|" + "---|" * len(TAUS)]
    for fam, outs in PREREGISTERED_OUTCOME_FAMILIES.items():
        del fam
        for out in outs:
            for h in FOCAL_HORIZONS:
                cells = []
                for t in TAUS:
                    r = sub[(sub["outcome"] == out) & (sub["horizon"] == h)
                            & (sub["tau"] == t)]
                    if not len(r):
                        cells.append("—")
                        continue
                    rr = r.iloc[0]
                    if not rr["converged"]:
                        cells.append("‡")     # IRLS khong hoi tu -> KHONG in so
                        continue
                    star = "*" if rr["pvalue"] < ALPHA else ""
                    cells.append(f"{rr['beta']:+.3f}{star}")
                if any(c != "—" for c in cells):
                    lines.append(f"| {OUTCOME_LABEL.get(out, out)} | {h} | "
                                 + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_report(stats: dict, holm: pd.DataFrame, gamma: pd.DataFrame,
                 quant: pd.DataFrame | None, families: dict, meta: dict) -> list[str]:
    """Narrative. Guard P1: MOI so o day den tu `stats`/`meta`/bang — khong go tay."""
    p: list[str] = []
    p.append("# T2-full — Bảng γ tầng 2, track THÁNG (Phase 1a)\n")
    p.append("> 🔬 Research deliverable. Local Projection lag-augmented (MO-PM 2021) "
             "+ HC1 + dải sup-t (MO-PM 2019). Sinh tự động bởi `scripts/run_t2_full.py`.\n")
    p.append("**Claim tối đa: `transmission decomposition` / `predictive`. "
             "KHÔNG phải `causal`** — reduced-form LP, chưa có structural ID "
             "(claims matrix `docs/07v2` §6.4). Track tháng **chưa có holdout** "
             "(`g0` §2: rỗng theo cấu tạo) → trần claim "
             "`predictive, chưa xác nhận holdout`.\n")

    p.append("## Metadata\n")
    p.append(f"- **data_version**: `{meta['data_version']}`")
    p.append(f"- **git commit**: `{meta['git_commit']}`")
    p.append(f"- **generated_at**: {meta['generated_at']}")
    p.append(f"- **panel**: {meta['panel_start']} → {meta['panel_end']} "
             f"({stats['n_obs']} tháng, complete-case một mẫu duy nhất)")
    p.append(f"- **suy diễn**: `{INFERENCE}` + HC1, lags={stats['lags']}, "
             f"dải sup-t (seed={SEED}), CI={CI}")
    p.append(f"- **lưới**: {stats['n_measures']} thước đo × {stats['n_channels']} kênh "
             f"× {stats['n_outcomes']} outcome × 2 bản battery × "
             f"h=0..{stats['max_horizon']} → {stats['n_gamma_rows']} hàng γ")
    p.append(f"- **vintage**: real_macro=`{meta['real_macro_vintage']}` · "
             f"freight=`{meta['freight_vintage']}` · benchmark=`{meta['benchmark_vintage']}`")
    p.append(f"- **thời gian chạy**: {stats['elapsed_sec']} giây\n")

    p.append("## Quyết định đã ký chi phối run này\n")
    p.append("| Quyết định | Nội dung | Hệ quả trong run |")
    p.append("|---|---|---|")
    p.append("| `DEC-2026-08-02-shock-axis` (`g0` §7.1=A) | SHOCK là **trục báo cáo**, "
             "báo cáo cả ba, không chọn | 3 bảng γ song song; `primary_cell.shock` "
             "vẫn UNRESOLVED |")
    p.append("| — điều kiện kèm | LEVEL/LEVEL+JUMP chỉ eligible với `lag_augmented` | "
             f"run này dùng `{INFERENCE}` → cả ba thước đo eligible |")
    p.append("| `DEC-2026-08-02-holm-family` (docs/14 §6.6=B) | Họ = nhóm outcome "
             "pre-register | Holm trong họ, cỡ "
             + " / ".join(str(v) for v in family_sizes(families).values()) + " |")
    p.append("")

    p.append("## Cổng eligibility (máy)\n")
    p.append("| Thước đo | Eligible | Lý do |")
    p.append("|---|---|---|")
    for m in SHOCK_MEASURES:
        e = gate_shock_eligibility(m, INFERENCE)
        p.append(f"| {MEASURE_LABEL[m]} | {'✅' if e.eligible else '❌'} | {e.reason} |")
    p.append("")

    p.append("## Kết quả — số ô sống sót Holm (bản b: có battery EPU)\n")
    p.append(f"Một ô = một (outcome, horizon focal) tại h∈{list(FOCAL_HORIZONS)}, "
             f"kênh pooled+act+threat gộp lại; α={stats['alpha']}. "
             f"Tổng {stats['n_focal_tests']} kiểm định focal, "
             f"{stats['n_raw_sig']} có p thô < {stats['alpha']}, "
             f"**{stats['n_survive_holm']}** sống sót Holm trong họ "
             f"(bản b: {stats['n_survive_holm_battery']}).\n")
    p.append(axis_summary_md(holm))
    p.append("")
    p.append(f"**Đồng thuận qua trục SHOCK:** {stats['n_cells_all_three_measures']} ô "
             "(kênh, outcome, horizon) sống sót Holm ở **cả ba** thước đo. "
             "Đó là con số đáng đọc nhất của trục báo cáo: kết luận bền qua "
             "cách đo shock mạnh hơn hẳn kết luận chỉ đúng ở một thước đo.\n")

    if "top_outcome" in stats:
        p.append(f"**Ô mạnh nhất (bản b):** {OUTCOME_LABEL.get(stats['top_outcome'], stats['top_outcome'])} "
                 f"× {MEASURE_LABEL[stats['top_measure']]} × kênh {stats['top_channel']} "
                 f"tại h={stats['top_horizon']}: γ={stats['top_beta']:+.4f}, "
                 f"p={stats['top_pvalue']:.4f}, p_Holm={stats['top_pvalue_adj']:.4f} "
                 f"(họ `{stats['top_family']}`).\n")
    else:
        p.append("**Không ô nào sống sót Holm ở bản b.** Kết quả null — VẪN LƯU "
                 "và vẫn là kết quả (`SCA-01.commitment`: báo cáo toàn bộ bất kể "
                 "kết quả).\n")

    p.append(f"**Dải sup-t:** hằng số c ∈ [{stats['supt_c_min']}, {stats['supt_c_max']}] "
             f"trên {stats['n_horizons']} horizon — so với z pointwise. "
             f"{stats['n_cells_supt_excl_zero']}/{stats['n_cells']} ô có IRF ra khỏi "
             "dải **đồng thời** ở ít nhất một horizon. Đọc IRF bằng dải pointwise "
             "trên ngần ấy horizon là đọc sai.\n")

    for m in SHOCK_MEASURES:
        p.append(f"## Bảng γ — {MEASURE_LABEL[m]}, kênh pooled, bản b (có battery)\n")
        p.append(gamma_table_md(holm, "b", m))
        p.append("")

    if quant is not None:
        p.append("## Hồi quy phân vị — phân phối dịch chuyển hay dày đuôi?\n")
        p.append(f"γ theo τ tại focal horizons, bản b, kênh pooled. `*` = p<{stats['alpha']}. "
                 "**Không có dải sup-t** cho nhánh này (hàm ảnh hưởng của QuantReg "
                 "cần ước lượng sparsity — đường đúng là bootstrap, chưa làm): đọc "
                 f"kèm cảnh báo bội trên {stats['n_horizons']} horizon.\n")
        p.append(f"`‡` = IRLS **không hội tụ** → ô để trống, không in số. "
                 f"{stats['n_quantile_not_converged']}/{stats['n_quantile_rows']} "
                 "hàng phân vị rơi vào trường hợp này: statsmodels chỉ WARN rồi trả "
                 "hệ số của vòng lặp cuối, nên nếu không đếm thì số không đáng tin "
                 "vẫn chạy thẳng vào bảng. Hồi quy phân vị ở τ đuôi trên mẫu "
                 f"{stats['n_obs']} tháng là vùng dễ không hội tụ — đây là giới hạn "
                 "của mẫu, không phải lỗi cấu hình.\n")
        for m in SHOCK_MEASURES:
            p.append(f"### {MEASURE_LABEL[m]}\n")
            p.append(quantile_table_md(quant, m))
            p.append("")

    p.append("## Giới hạn — đọc trước khi trích số\n")
    p.append(f"- **Mẫu {stats['n_obs']} tháng** là chi phí thật của thiết kế: "
             f"LEVEL+JUMP cần {stats['jump_window']} tháng cửa sổ "
             f"(min_periods={stats['jump_min_periods']}) cho ngưỡng phân vị, và "
             "EPU global chỉ có từ 1997. Một mẫu duy nhất cho mọi ô là điều kiện "
             "để bản a/b và ba thước đo so được với nhau (docs/14 §2 1a) — "
             "trộn mẫu thì 'hệ số yếu đi khi thêm control' có thể chỉ là đổi mẫu.")
    p.append("- **WUI KHÔNG có trong battery**: publish theo quý, join vào grid "
             "tháng sẽ xóa 2/3 panel trong im lặng, forward-fill thì vi phạm #10. "
             "`data/wui_global.csv` chưa tồn tại. Battery ở đây = EPU US + EPU "
             "Global, **thiếu WUI** — ghi ra chứ không lặng lẽ bỏ (docs/14 §2 1a #3).")
    p.append("- **Freight là PPI khảo sát dính** → đo truyền dẫn chi phí, KHÔNG đo "
             "tắc nghẽn Hormuz/Malacca. Đừng đọc hệ số freight như thước đo điểm nghẽn.")
    p.append("- **IP/CPI revise hồi tố**: bản FRED là vintage mới nhất, không phải "
             "point-in-time. Backtest thật phải qua ALFRED vintage.")
    p.append(f"- **Phân vị chỉ chạy kênh pooled** ({stats['n_taus']} mức τ): lưới đầy "
             "đủ 3 kênh × 5 τ không thêm thông tin cho câu hỏi Phase 1a mà nhân 3 "
             "lần chi phí. Phạm vi ghi ra, không âm thầm thu hẹp.")
    p.append("- **Holm chỉ áp tại focal horizons đã pre-register**, không quét 25 "
             "horizon: chiều horizon đã do dải sup-t xử lý (docs/14 §1.3); phạt lại "
             "là mất hết power.")
    p.append("- Holm **conservative** khi outcome tương quan mạnh — oil/dxy/vix/us10y "
             "chắc chắn có. Đánh đổi đã biết khi ký §6.6, không đổi sang thủ tục "
             "lỏng hơn sau khi thấy p-value.\n")

    p.append("## Human review (điền tay sau khi đọc)\n")
    p.append("- Dấu & độ lớn có giải thích kinh tế cho từng ô sống sót: _chưa điền_")
    p.append("- Ba thước đo có kể cùng một câu chuyện không: _chưa điền_")
    p.append("- **Kết luận (GO/NO-GO + lý do + ngày + người):** _chưa điền_\n")
    return p


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-quantile", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    print("[1/5] Panel tháng (trục shock × 3 kênh + 8 outcome + battery đồng thước đo)...")
    panel = build_panel(args.start, args.end, args.refresh)
    families = outcomes_present(panel)
    print(f"      {panel.shape[0]} tháng, {panel.index.min().date()} → "
          f"{panel.index.max().date()}, {panel.shape[1]} cột")

    print("[2/5] Ước lượng γ (OLS lag-augmented + sup-t)...")
    gamma = estimate_gamma(panel, families)
    print(f"      {len(gamma)} hàng γ")

    print("[3/5] Holm trong họ outcome tại focal horizons...")
    holm = apply_holm(gamma, families)
    print(f"      {len(holm)} kiểm định focal, {int(holm['reject'].sum())} sống sót")

    quant = None
    if not args.no_quantile:
        print("[4/5] Hồi quy phân vị (kênh pooled)...")
        quant = estimate_quantiles(panel, families)
        print(f"      {len(quant)} hàng")
    else:
        print("[4/5] Bỏ qua phân vị (--no-quantile)")

    elapsed = time.time() - t0
    stats = compute_stats(panel, gamma, holm, quant, families, elapsed)
    dv = _data_version(DEFAULT_GPR_MONTHLY, DEFAULT_GPR_DAILY)
    meta = {
        "data_version": dv,
        "git_commit": _git_commit(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "panel_start": panel.index.min().date().isoformat(),
        "panel_end": panel.index.max().date().isoformat(),
        "real_macro_vintage": real_macro_vintage(),
        "freight_vintage": freight_vintage(),
        "benchmark_vintage": benchmark_vintage(),
    }

    print("[5/5] Ghi report + CSV...")
    DATADIR.mkdir(parents=True, exist_ok=True)
    gamma.to_csv(DATADIR / f"t2_full_gamma_{dv}.csv", index=False)
    holm.to_csv(DATADIR / f"t2_full_holm_{dv}.csv", index=False)
    if quant is not None:
        quant.to_csv(DATADIR / f"t2_full_quantile_{dv}.csv", index=False)

    out = REPORTS / f"T2_full_{dv}.md"
    if out.exists():
        raise FileExistsError(
            f"{out} đã tồn tại — không ghi đè report cũ. Xóa CÓ CHỦ ĐÍCH rồi chạy lại.")
    out.write_text("\n".join(build_report(stats, holm, gamma, quant, families, meta)),
                   encoding="utf-8")
    print(f"\nDONE ({stats['elapsed_sec']}s). → {out}")


if __name__ == "__main__":
    main()
