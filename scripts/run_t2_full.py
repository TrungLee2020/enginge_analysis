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
  - BATTERY a/b CUNG MAU. Dang control = `level_lags`:
    DEC-2026-08-09-battery-control-form (sua cach thuc hien cua docs/14 §2 1a
    muc 2; "same_measure" giu lam robustness). Ly do + so do duoc o docstring
    `BATTERY_MODE`; danh doi GHI VAO report moi run.

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
    transform_benchmark,
)
from gpr_engine.econometrics.multiplicity import (  # noqa: E402
    PREREGISTERED_OUTCOME_FAMILIES,
    grid_null_check,
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

# Ban battery:
#   a = khong control
#   b = EPU (bat dinh chinh sach)
#   c = EPU + CU SOC chinh sach tien te (policy_shock.mp_surprise)
#
# Vi sao them ban c thay vi nhet vao ban b: ban b la cai da chay va da bao cao;
# doi dinh nghia cua no lam moi so cu khong so duoc nua. Ban c la CHIEU MOI.
#
# Vi sao can: γ do "cu soc GPR -> vi mo toan cau", ma tin Fed day DUNG nhung bien
# do (lai suat, DXY, VIX, dau). Thang nao co ca hai ma khong tach thi γ hut luon
# phan cua Fed. EPU kiem soat BAT DINH chinh sach, KHONG kiem soat CU SOC chinh
# sach — hai thu khac nhau.
# ⚠️ Chi phi mau: mp_surprise bat dau 2003-01 (ngay cong bo statement som nhat
# lay duoc), nen ban c keo CA panel ve 2003+. Mot mau duy nhat la dieu kien de
# a/b/c so duoc — xem muc "Chi phi mau" trong report.
BATTERY_VERSIONS = ("a", "b", "c")
POLICY_SHOCK_COL = "mp_surprise"

# So lag cua control khi BATTERY_MODE="level_lags". Dat bang LAGS cua LP de
# control va shock cung do sau lag — khong phai tham so tu do de do.
BATTERY_CONTROL_LAGS = LAGS

# Dang dua battery EPU vao ban b:
#   "same_measure": control di qua build_monthly_shock_axis, CUNG thuoc do voi
#                   shock (docs/14 §2 1a). Hap thu ca JUMP phi tuyen. TON warm-up
#                   -> mau 2007+.
#   "level_lags":   control vao dang LEVEL + p lag. KHONG ton warm-up -> mau dai.
#
# Mac dinh la "level_lags". Ly do — DO tren du lieu that (2026-08-09, ca hai che
# do chay tren cung `--start=1990-01-01`), khong phai suy doan:
#   same_measure -> 231 thang, bat dau 2007-02, cot rang buoc
#                   `epu_global_LEVEL_PLUS_JUMP`  (= dung mau cua T2_full_f2579b30928f)
#   level_lags   -> 315 thang, bat dau 2000-02, cot rang buoc
#                   `GPR_THREAT_LEVEL_PLUS_JUMP`
#   => +84 thang (7 nam). Duong di cua cai cu: GEPUCURRENT bat dau 1997 ->
#   build_monthly_shock_axis (INNOVATION min_train=60 + cua so JUMP) -> 2007;
#   complete-case toan cuc keo CA panel theo. Mot bien KIEM SOAT robustness tieu
#   7 nam du lieu cua bien CHINH.
#
# Diem quan trong sau khi doi (do duoc, khong doan): cot rang buoc CHUYEN sang
#   JUMP cua CHINH truc shock. Nghia la phan 1990-2000 con mat KHONG phai loi cua
#   control nua — do la chi phi NOI TAI cua thuoc do LEVEL+JUMP (cua so rolling
#   tren GPR). Bo epu_global khoi battery cung KHONG lay lai duoc. Cai gia con lai
#   thuoc ve truc shock, khong thuoc ve battery.
#   So thang mat THAT do bang `sample_cost()` va in vao report moi run.
#
# Vi sao "level_lags" van tra loi duoc lo ngai dong-thuoc-do cua docs/14 §2 1a:
#   INNOVATION(EPU) = LEVEL(EPU) − AR-fit(lag cua LEVEL(EPU)) — mot to hop TUYEN
#   TINH cua {LEVEL(EPU), lag cua no}. Nen {LEVEL + p lag} CHUA TRON khong gian
#   ma INNOVATION(EPU) chiem: hap thu it nhat bang, thuong nhieu hon.
# Ngoai le trung thuc: JUMP = max(0, z − q95) la PHI TUYEN, KHONG nam trong span
#   cua level+lag. O thuoc do LEVEL+JUMP, "level_lags" hap thu IT HON
#   "same_measure". Danh doi da biet -> ghi thang vao report (`render_sample_
#   section`), khong lang im.
BATTERY_MODE = "level_lags"

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


def _spec_version() -> str:
    """Bam SPEC cua run. Ten artifact = data_version + spec_version.

    Vi sao can: `_data_version` chi bam FILE DU LIEU. Doi spec ma du lieu khong
    doi (vd them ban battery c) thi tro ra DUNG mot ten -> `FileExistsError` o
    report, nhung CSV thi da bi ghi de TRUOC do. Da xay ra that 2026-08-09: CSV
    cua T2_full_3e1bd83a02b8 bi ghi de bang ket qua cua spec khac, con file .md
    van mo ta spec cu — hai thu mau thuan nhau ma khong co canh bao nao.
    Doi bat ky dong nao duoi day = ten artifact doi = khong the ghi de nham nua.
    """
    h = hashlib.sha256()
    for part in (INFERENCE, str(LAGS), str(list(HORIZONS)), str(FOCAL_HORIZONS),
                 str(TAUS), str(ALPHA), str(CI), str(SEED), BATTERY_MODE,
                 str(BATTERY_CONTROL_LAGS), str(BATTERY_CONTROLS),
                 str(BATTERY_VERSIONS), str(sorted(CHANNELS))):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:6]


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
def build_policy_shock_monthly(refresh: bool = False) -> pd.DataFrame | None:
    """Cu soc chinh sach tien te theo THANG + lag, cho ban battery c.

    Ngay cong bo lay tu muc luc FOMC that (`ingest/fomc.py`), lai suat tu FRED.
    Can mang; khong lay duoc thi tra None va ban c bi BO — ghi ra, khong lang le
    chay tiep voi mot control rong.
    """
    try:
        from pandas_datareader import data as pdr

        from gpr_engine.econometrics.policy_shock import (
            DEFAULT_YIELD_SERIES,
            event_days,
            policy_surprise,
            to_monthly,
        )
        from gpr_engine.ingest.fomc import list_archive

        rels = [r for r in list_archive(strict=False) if r.doc_type == "statement"]
        for y in range(2000, dt.date.today().year + 1):
            try:
                rels += [r for r in list_archive(years=[y], strict=False)
                         if r.doc_type == "statement"]
            except Exception:                                   # noqa: BLE001, S112
                continue
        ev = event_days({r.published_at for r in rels})
        y = pdr.DataReader(DEFAULT_YIELD_SERIES, "fred", "1999-01-01", None)
        s = policy_surprise(y[DEFAULT_YIELD_SERIES].dropna(), ev)
        m = to_monthly(s)[["mp_surprise"]]
        for k in range(1, BATTERY_CONTROL_LAGS + 1):
            m[f"{POLICY_SHOCK_COL}_L{k}"] = m[POLICY_SHOCK_COL].shift(k)
        print(f"      cú sốc chính sách: {len(ev)} ngày công bố, "
              f"{int((m[POLICY_SHOCK_COL] != 0).sum())} tháng có họp, "
              f"{m.index.min().date()} → {m.index.max().date()}")
        return m
    except Exception as e:                                      # noqa: BLE001
        print(f"      ⚠️ KHÔNG dựng được cú sốc chính sách ({type(e).__name__}: "
              f"{str(e)[:80]}) → bỏ bản battery c")
        return None


def build_panel(start: str, end: str | None, refresh: bool,
                battery_mode: str = BATTERY_MODE,
                dropna: bool = True) -> pd.DataFrame:
    """Panel thang: truc shock x 3 kenh + 8 outcome + battery.

    Battery khong dung `battery=True` cua build_monthly_panel (cai do tra EPU o
    LEVEL, khong lag). Dang control theo `battery_mode` — xem hang so o tren.

    Mot MAU DUY NHAT (complete-case toan bo) de moi o so sanh duoc: ban a vs b,
    va ba thuoc do voi nhau. `dropna=False` tra ban CHUA complete-case, chi de
    chan doan cot nao rang buoc dau mau (`sample_binding_report`) — khong duoc
    dua thang vao uoc luong.
    """
    if battery_mode not in ("same_measure", "level_lags"):
        raise ValueError(
            f"battery_mode la {battery_mode!r}; chi nhan 'same_measure'|'level_lags'.")

    raw = load_benchmark_monthly(start, end, refresh=refresh, wui_path=None)

    if battery_mode == "same_measure":
        extra = pd.concat(
            [build_monthly_shock_axis(raw[c].dropna(), prefix=c)
             for c in raw.columns], axis=1)
    else:
        # LEVEL (cung phep bien doi log1p ma transform_benchmark dung) + p lag.
        lvl = transform_benchmark(raw)
        cols = [lvl.rename(columns={c: f"{c}_LEVEL" for c in lvl.columns})]
        for k in range(1, BATTERY_CONTROL_LAGS + 1):
            cols.append(lvl.shift(k).rename(
                columns={c: f"{c}_LEVEL_L{k}" for c in lvl.columns}))
        extra = pd.concat(cols, axis=1)

    # EPU thang M cung chi biet sau khi thang M ket thuc — align GIONG GPR, neu
    # khong thi control nhin truoc shock mot thang.
    extra = align_monthly_gpr_to_information_time(extra)

    mp = build_policy_shock_monthly(refresh=refresh)
    if mp is not None:
        # KHONG align nhu EPU: cu soc chinh sach cua thang M duoc biet NGAY trong
        # thang M (thi truong phan ung trong ngay cong bo). Day chinh la ly do no
        # la bien kiem soat dung cho outcome cung thang.
        extra = extra.join(mp, how="outer")

    return build_monthly_panel(
        start=start, end=end, refresh=refresh, shock_axis=True, components=True,
        real_macro=True, freight=True, battery=False, extra_monthly=extra,
        dropna=dropna)


def battery_control_names(measure: str, battery: str,
                          battery_mode: str = BATTERY_MODE) -> list[str]:
    """Ten cot control cho ban battery. Mot cho duy nhat sinh ten — hai nhanh
    uoc luong (OLS + phan vi) khong duoc tu ghep chuoi rieng."""
    if battery == "a":
        return []
    if battery not in BATTERY_VERSIONS:
        raise ValueError(f"battery={battery!r} khong thuoc {BATTERY_VERSIONS}")
    if battery_mode == "same_measure":
        cols = [f"{c}_{measure}" for c in BATTERY_CONTROLS]
    else:
        cols = ([f"{c}_LEVEL" for c in BATTERY_CONTROLS]
                + [f"{c}_LEVEL_L{k}" for c in BATTERY_CONTROLS
                   for k in range(1, BATTERY_CONTROL_LAGS + 1)])
    if battery == "c":
        # mp_surprise DA la mot innovation (thay doi trong ngay cong bo), khong
        # bien doi them. Them lag cung do sau voi cac control khac.
        cols += [POLICY_SHOCK_COL] + [
            f"{POLICY_SHOCK_COL}_L{k}" for k in range(1, BATTERY_CONTROL_LAGS + 1)]
    return cols


# ---------------------------------------------------------------------------
# Chan doan mau — chay TRUOC khi uoc luong
# ---------------------------------------------------------------------------
def sample_binding_report(panel: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Cot nao rang buoc dau mau. In TRUOC moi run, khong phai debug tool.

    ⚠️ Goi tren panel CHUA dropna (`build_panel(..., dropna=False)`). Tren panel
    da complete-case thi moi cot cung mot `first_valid` va bang nay vo nghia.

    Complete-case toan cuc nghia la cot bat dau muon nhat quyet dinh mau cua
    TAT CA cac o. Khong in cai nay ra thi mat 17 nam du lieu ma khong ai thay —
    da xay ra that o T2_full_f2579b30928f.
    """
    rows = []
    for c in panel.columns:
        s = panel[c].dropna()
        if s.empty:
            rows.append({"column": c, "first_valid": None, "n_obs": 0})
            continue
        rows.append({"column": c,
                     "first_valid": s.index.min().date().isoformat(),
                     "n_obs": int(s.size)})
    out = pd.DataFrame(rows).sort_values("first_valid", ascending=False,
                                         na_position="first")
    return out.head(top).reset_index(drop=True)


def sample_cost(panel: pd.DataFrame, requested_start: str) -> dict:
    """Bao nhieu thang bi mat so voi `--start`, va vi cot nao."""
    binding = sample_binding_report(panel, top=1)
    complete = panel.dropna(how="any")
    actual = complete.index.min() if len(complete) else pd.NaT
    req = pd.Timestamp(requested_start)
    lost = 0 if pd.isna(actual) else max(
        0, (actual.year - req.year) * 12 + (actual.month - req.month))
    return {
        "requested_start": req.date().isoformat(),
        "actual_start": None if pd.isna(actual) else actual.date().isoformat(),
        "months_lost": lost,
        "binding_column": (binding.iloc[0]["column"] if len(binding) else None),
        "binding_first_valid": (binding.iloc[0]["first_valid"] if len(binding) else None),
    }


def outcomes_present(panel: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Ho outcome pre-register, loc theo cot thuc su co trong panel."""
    return {fam: tuple(o for o in members if o in panel.columns)
            for fam, members in PREREGISTERED_OUTCOME_FAMILIES.items()}


# ---------------------------------------------------------------------------
# Uoc luong
# ---------------------------------------------------------------------------
def available_versions(panel: pd.DataFrame) -> tuple[str, ...]:
    """Ban battery chay duoc tren panel nay. Ban c can cot cu soc chinh sach —
    khong co thi BO ban c, khong im lang chay no voi control rong."""
    return tuple(v for v in BATTERY_VERSIONS
                 if v != "c" or POLICY_SHOCK_COL in panel.columns)


def estimate_gamma(panel: pd.DataFrame, families: dict) -> pd.DataFrame:
    """Bang γ: measure x channel x outcome x battery x horizon, OLS + sup-t."""
    versions = available_versions(panel)
    rows = []
    for measure in SHOCK_MEASURES:
        for chan, prefix in CHANNELS.items():
            shock = shock_column(prefix, measure)
            if shock not in panel.columns:
                continue
            for battery in versions:
                controls = battery_control_names(measure, battery)
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

    Chi chay ban battery a/b, KHONG chay ban c: cau hoi cua ban c ("γ co song
    sot khi kiem soat cu soc chinh sach khong") tra loi bang OLS la du; them mot
    ban nua vao nhanh phan vi nhan 1.5 lan chi phi cham nhat cua run ma khong
    doi cau tra loi. Pham vi ghi ra, khong am tham.
    """
    prefix = CHANNELS[channel]
    rows = []
    for measure in SHOCK_MEASURES:
        shock = shock_column(prefix, measure)
        for battery in ("a", "b"):
            controls = battery_control_names(measure, battery)
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
                  elapsed: float, cost: dict | None = None,
                  battery_mode: str = BATTERY_MODE) -> dict:
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
        # Ban c = EPU + cu soc chinh sach tien te. Con so dang doc nhat cua run
        # nay: bao nhieu o song sot khi da tach phan do Fed gay ra.
        "n_survive_holm_battery_c": int((surv["battery"] == "c").sum()),
        "n_versions": int(holm["battery"].nunique()),
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

    # Doi chieu MUC LUOI: so bac bo tho vs ky vong duoi null toan cuc. Holm tra
    # loi "o nao", cai nay tra loi "luoi co nhieu hon nhieu thuan khong" — hai
    # cau hoi khac nhau, va o T2_full_f2579b30928f chung cho ket luan nguoc
    # nhau (15 "song sot" nhung 34 < 43.2 ky vong).
    chk = grid_null_check(holm["pvalue"], alpha=ALPHA)
    stats.update({
        "grid_n_tests": chk.n_tests,
        "grid_expected": round(chk.expected, 1),
        "grid_observed": chk.observed,
        "grid_ratio": round(chk.ratio, 2),
        "grid_z": round(chk.z_indep, 2),
        "grid_verdict": chk.verdict,          # chuoi, khong phai so
    })

    # Chi phi mau + dang control battery — de report noi ra thay vi de im.
    stats["battery_mode"] = battery_mode
    stats["battery_control_lags"] = (BATTERY_CONTROL_LAGS
                                     if battery_mode == "level_lags" else 0)
    if cost is not None:
        stats.update({
            "sample_requested_start": cost["requested_start"],
            "sample_actual_start": cost["actual_start"],
            "sample_months_lost": cost["months_lost"],
            "sample_binding_column": cost["binding_column"],
            "sample_binding_first_valid": cost["binding_first_valid"],
        })
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


def axis_summary_md(holm: pd.DataFrame, battery: str = "b") -> str:
    """So o song sot Holm theo (thuoc do x ho) — doc truc SHOCK trong mot bang."""
    sub = holm[holm["battery"] == battery]
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


def render_grid_null_section(stats: dict, holm: pd.DataFrame) -> list[str]:
    """Doi chieu muc luoi. DAT TREN bang Holm, khong phai duoi.

    Thu tu quan trong: doc "15 o song sot" truoc roi moi doc "34 < 43.2" thi an
    tuong dau da hinh thanh. Ket luan muc luoi phai den truoc ket luan muc o.

    Guard P1: van xuoi doc tu `stats` (KHONG dung `GridNullCheck.to_markdown`,
    ham do format tu truong cua chinh no nen nam ngoai payload cua runner).
    Bang phu tra ve lam PHAN TU RIENG — guard soi van xuoi, bang la du lieu in
    tu DataFrame; tron chung mot chuoi la guard soi ca bang.
    """
    parts = [
        "## Đối chiếu mức lưới (đọc TRƯỚC bảng Holm)\n",
        f"Toàn lưới có **{stats['grid_n_tests']}** kiểm định focal ở ngưỡng "
        f"p<{stats['alpha']}. Kỳ vọng số bác bỏ **dưới null toàn cục**: "
        f"**{stats['grid_expected']}**. Quan sát: **{stats['grid_observed']}** "
        f"({stats['grid_ratio']}x kỳ vọng, z≳{stats['grid_z']:+.2f}).\n",
        f"> {stats['grid_verdict']}\n",
        "Holm trả lời *ô NÀO sống sót trong họ này*; con số trên trả lời *toàn "
        "lưới có nhiều hơn nhiễu thuần không*. Họ Holm chỉ 4/3/1 outcome nên "
        "ngưỡng nghiêm nhất là α/4 — gần như không phạt gì so với quy mô lưới. "
        "z là **cận dưới** của |z| thật (kỳ vọng cộng tính bất kể tương quan, "
        "chỉ phương sai mới phình) — đọc dấu và độ lớn xấp xỉ, không phải p-value.\n",
    ]
    if "battery" in holm.columns:
        rows = []
        for b, sub in holm.groupby("battery"):
            c = grid_null_check(sub["pvalue"], alpha=stats["alpha"])
            rows.append(f"| {b} | {c.n_tests} | {c.expected:.1f} | {c.observed} "
                        f"| {c.ratio:.2f}x |")
        parts.append("| Bản battery | n | Kỳ vọng null | Quan sát | Tỉ lệ |\n"
                     "|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
        parts.append("Chênh lệch giữa hai bản đọc được ngay ở đây: bản a bác bỏ "
                     "nhiều hơn hẳn bản b ⇒ phần 'riêng của GPR' chính là thứ "
                     "battery hấp thụ.\n")
    return parts


def render_sample_section(stats: dict, binding: pd.DataFrame | None) -> list[str]:
    """Chi phi mau — in ra de lan sau khong mat 10 nam ma khong ai thay."""
    parts = ["## Chi phí mẫu (complete-case toàn cục)\n",
             "\n".join([
                 f"- `--start` yêu cầu: **{stats['sample_requested_start']}**",
                 f"- mẫu thực tế: **{stats['sample_actual_start']}**",
                 f"- **mất {stats['sample_months_lost']} tháng** vì cột "
                 f"`{stats['sample_binding_column']}` (hợp lệ từ "
                 f"{stats['sample_binding_first_valid']})",
                 f"- `battery_mode` = `{stats['battery_mode']}`"
                 + (f", số lag control = {stats['battery_control_lags']}"
                    if stats["battery_control_lags"] else ""),
             ]) + "\n"]
    if binding is not None and len(binding):
        rows = [f"| `{r['column']}` | {r['first_valid']} | {r['n_obs']} |"
                for _, r in binding.iterrows()]
        parts.append("Các cột bắt đầu muộn nhất (trước complete-case):\n")
        parts.append("| Cột | Hợp lệ từ | n |\n|---|---|---|\n"
                     + "\n".join(rows) + "\n")
    if stats["battery_mode"] == "level_lags":
        parts.append(
            "> `level_lags`: control EPU vào dạng LEVEL + lag thay vì cùng thước "
            "đo với shock. Span của {LEVEL, lag} chứa trọn INNOVATION (INNOVATION "
            "là tổ hợp tuyến tính của chính LEVEL và lag của nó) nên hấp thụ "
            "không kém hơn ở hai thước đo LEVEL/INNOVATION. **Đánh đổi**: JUMP là "
            "phi tuyến, KHÔNG nằm trong span đó — ở thước đo LEVEL+JUMP, control "
            "hấp thụ ÍT HƠN chế độ `same_measure`. Đọc kết quả LEVEL+JUMP bản b "
            "với lưu ý này.\n")
    else:
        parts.append(
            "> `same_measure`: control cùng thước đo với shock (docs/14 §2 1a). "
            "Hấp thụ cả JUMP phi tuyến, nhưng tốn warm-up của shock-axis nên "
            "mẫu bị cắt — xem số tháng mất ở trên.\n")
    return parts


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
                 quant: pd.DataFrame | None, families: dict, meta: dict,
                 binding: pd.DataFrame | None = None) -> list[str]:
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

    if "sample_months_lost" in stats:
        p.extend(render_sample_section(stats, binding))

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
    p.append("| `DEC-2026-08-09-battery-control-form` | Dạng control battery = "
             "`level_lags` (LEVEL + lag), sửa cách thực hiện của docs/14 §2 1a "
             "mục 2; `same_measure` giữ làm robustness | run này dùng `"
             + str(stats["battery_mode"]) + "`; lý do + đánh đổi ở mục "
             "*Chi phí mẫu* |")
    p.append("| `DEC-2026-08-09-policy-shock-control` | Bản battery c = b + CÚ SỐC "
             "chính sách tiền tệ (`policy_shock.py`, proxy NGÀY: Δ lãi suất 2 năm "
             "ngày công bố FOMC) + 6 lag; a/b giữ nguyên định nghĩa | chiều MỚI, "
             "không sửa b nên số cũ vẫn so được. Trần claim `measurement`: gọi "
             "\"policy-window surprise (daily proxy)\", KHÔNG gọi \"cú sốc chính "
             "sách\" — chuẩn vàng là cửa sổ 30 phút, bản này dùng cả ngày |")
    p.append("")

    p.append("## Cổng eligibility (máy)\n")
    p.append("| Thước đo | Eligible | Lý do |")
    p.append("|---|---|---|")
    for m in SHOCK_MEASURES:
        e = gate_shock_eligibility(m, INFERENCE)
        p.append(f"| {MEASURE_LABEL[m]} | {'✅' if e.eligible else '❌'} | {e.reason} |")
    p.append("")

    p.extend(render_grid_null_section(stats, holm))

    p.append("## Kết quả — số ô sống sót Holm (bản b: có battery EPU)\n")
    p.append(f"Một ô = một (outcome, horizon focal) tại h∈{list(FOCAL_HORIZONS)}, "
             f"kênh pooled+act+threat gộp lại; α={stats['alpha']}. "
             f"Tổng {stats['n_focal_tests']} kiểm định focal, "
             f"{stats['n_raw_sig']} có p thô < {stats['alpha']}, "
             f"**{stats['n_survive_holm']}** sống sót Holm trong họ "
             f"(bản b: {stats['n_survive_holm_battery']}).\n")
    p.append("**Bản b — control EPU (bất định chính sách):**\n")
    p.append(axis_summary_md(holm, "b"))
    p.append("")
    if stats["n_versions"] > 2:
        p.append("**Bản c — EPU + CÚ SỐC chính sách tiền tệ:** "
                 f"{stats['n_survive_holm_battery_c']} ô sống sót (bản b: "
                 f"{stats['n_survive_holm_battery']}). Đây là con số đáng đọc "
                 "nhất của run: tin Fed đẩy đúng những biến mà γ đo (lãi suất, "
                 "DXY, VIX, dầu), nên ô nào biến mất khi thêm control này là ô "
                 "vốn đang tính công của Fed cho GPR. EPU kiểm soát *bất định* "
                 "chính sách, KHÔNG kiểm soát *cú sốc* chính sách.\n")
        p.append(axis_summary_md(holm, "c"))
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
    print(f"[1/5] Panel tháng (trục shock × 3 kênh + 8 outcome + battery "
          f"`{BATTERY_MODE}`)...")
    # Dung ban CHUA complete-case de do chi phi mau, roi moi dropna. Xay dung
    # mot lan: dropna sau la dung y nghia "mot mau duy nhat" nhu truoc.
    raw_panel = build_panel(args.start, args.end, args.refresh, dropna=False)
    panel = raw_panel.dropna()
    cost = sample_cost(raw_panel, args.start)
    binding = sample_binding_report(raw_panel, top=5)
    families = outcomes_present(panel)
    print(f"      {panel.shape[0]} tháng, {panel.index.min().date()} → "
          f"{panel.index.max().date()}, {panel.shape[1]} cột")
    print(f"      chi phí mẫu: mất {cost['months_lost']} tháng so với "
          f"{cost['requested_start']} — cột ràng buộc `{cost['binding_column']}` "
          f"(hợp lệ từ {cost['binding_first_valid']})")

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
    stats = compute_stats(panel, gamma, holm, quant, families, elapsed, cost=cost)
    dv = f"{_data_version(DEFAULT_GPR_MONTHLY, DEFAULT_GPR_DAILY)}_{_spec_version()}"
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
    # Kiem VA CHAM TRUOC khi ghi bat cu gi. Ban cu kiem report SAU khi da ghi
    # CSV, nen mot lan va cham lam CSV bi ghi de con .md thi giu nguyen — hai
    # thu mau thuan nhau, khong canh bao. Da xay ra that 2026-08-09.
    out = REPORTS / f"T2_full_{dv}.md"
    csvs = {
        "gamma": DATADIR / f"t2_full_gamma_{dv}.csv",
        "holm": DATADIR / f"t2_full_holm_{dv}.csv",
        **({"quantile": DATADIR / f"t2_full_quantile_{dv}.csv"}
           if quant is not None else {}),
    }
    clash = [p for p in [out, *csvs.values()] if p.exists()]
    if clash:
        raise FileExistsError(
            f"Artifact đã tồn tại, KHÔNG ghi đè: {[str(p) for p in clash]}. "
            f"Tên mã hóa data_version + spec_version (`{dv}`) — trùng tên nghĩa "
            "là cùng dữ liệu VÀ cùng spec, tức chạy lại y hệt. Xóa CÓ CHỦ ĐÍCH "
            "rồi chạy lại nếu thật sự muốn.")

    DATADIR.mkdir(parents=True, exist_ok=True)
    gamma.to_csv(csvs["gamma"], index=False)
    holm.to_csv(csvs["holm"], index=False)
    if quant is not None:
        quant.to_csv(csvs["quantile"], index=False)
    out.write_text(
        "\n".join(build_report(stats, holm, gamma, quant, families, meta, binding)),
        encoding="utf-8")
    print(f"\nDONE ({stats['elapsed_sec']}s). → {out}")


if __name__ == "__main__":
    main()
