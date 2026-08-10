"""PATCH 2 — sua `build_panel` trong scripts/run_t2_full.py + them chan doan mau.

VAN DE (do tren repo o commit a55b1ea):
    panel thuc te bat dau 2007-02 du `--start` mac dinh la 1990-01-01.
    Nguyen nhan: `FRED_BENCHMARK["epu_global"] = GEPUCURRENT` bat dau 1997, roi
    di qua `build_monthly_shock_axis` -> INNOVATION burn-in `min_train=60` +
    cua so rolling cua JUMP -> khoang 2007. Complete-case toan cuc keo ca panel
    theo. Mat 1990-2007: Chien tranh Vung Vinh, 11/9, Iraq — tuc phan lon SU
    KIEN DUOI, dung thu ma gia thuyet phi tuyen can do.

    Mot bien KIEM SOAT robustness dang tieu 17 nam du lieu cua bien CHINH.

VI SAO CACH SUA NAY HOP LE (tra loi truc tiep docstring hien tai):
    Docstring hien tai lap luan: control phai CUNG THUOC DO voi shock, neu khong
    thi so LEVEL-control voi INNOVATION-shock se thoi phong phan rieng cua GPR.
    Lo ngai do dung, nhung cach vá dat hon can thiet.

    INNOVATION(EPU) = LEVEL(EPU) - AR-fit(cac lag cua LEVEL(EPU)) — tuc la mot
    to hop TUYEN TINH cua {LEVEL(EPU), lag cua no}. Nen dua EPU vao dang
    LEVEL + p lag thi khong gian control CHUA TRON khong gian ma INNOVATION(EPU)
    chiem: no hap thu it nhat bang, thuong la nhieu hon. Va no khong ton warm-up.

    Ngoai le trung thuc: JUMP = max(0, z - q95) la PHI TUYEN, khong nam trong
    span cua level+lag. Nen voi thuoc do LEVEL+JUMP, che do "level_lags" hap thu
    it hon che do "same_measure". Do la danh doi da biet, phai ghi vao report —
    khong duoc lang im. Vi vay giu ca hai che do va bat khai bao tuong minh.
"""
from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# THEM: hang so canh BATTERY_CONTROLS (dong ~76)
# ---------------------------------------------------------------------------
BATTERY_CONTROLS = ("epu_us", "epu_global")

# So lag cua control khi BATTERY_MODE="level_lags". Dat bang LAGS cua LP de
# control va shock cung do sau lag — khong phai tham so tu do de do.
BATTERY_CONTROL_LAGS = 6

# "same_measure": control di qua build_monthly_shock_axis, cung thuoc do voi
#                 shock. Hap thu ca JUMP phi tuyen. TON warm-up -> mau 2007+.
# "level_lags":   control vao dang LEVEL + lag. Span >= INNOVATION (xem docstring).
#                 KHONG ton warm-up -> mau dai. Hap thu it hon o thuoc do JUMP.
BATTERY_MODE = "level_lags"


# ---------------------------------------------------------------------------
# THEM: chan doan mau — chay TRUOC khi uoc luong
# ---------------------------------------------------------------------------
def sample_binding_report(panel: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Cot nao rang buoc dau mau. In TRUOC moi run, khong phai debug tool.

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
    actual = panel.dropna(how="any").index.min()
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


# ---------------------------------------------------------------------------
# THAY THE: build_panel (dong ~107)
# ---------------------------------------------------------------------------
def build_panel(start: str, end: str | None, refresh: bool,
                battery_mode: str = BATTERY_MODE) -> pd.DataFrame:
    """Panel thang: truc shock x 3 kenh + 8 outcome + battery.

    `battery_mode` — xem hang so o tren. Mac dinh "level_lags" vi che do
    "same_measure" lam mat 1990-2007 (GEPUCURRENT 1997 + burn-in shock-axis),
    tuc mat phan lon su kien duoi. Danh doi cua "level_lags" o thuoc do JUMP
    phai duoc ghi vao report.

    Mot MAU DUY NHAT (complete-case toan bo) de moi o so sanh duoc. Chi phi bay
    gio DO DUOC va IN RA: `sample_cost()`.
    """
    from gpr_engine.econometrics.data_files import (
        build_monthly_panel, load_benchmark_monthly)
    from gpr_engine.econometrics.dataset import align_monthly_gpr_to_information_time
    from gpr_engine.econometrics.shock_axis import build_monthly_shock_axis

    if battery_mode not in ("same_measure", "level_lags"):
        raise ValueError(f"battery_mode la: {battery_mode!r}")

    raw = load_benchmark_monthly(start, end, refresh=refresh, wui_path=None)

    if battery_mode == "same_measure":
        extra = pd.concat(
            [build_monthly_shock_axis(raw[c].dropna(), prefix=c)
             for c in raw.columns], axis=1)
    else:
        # LEVEL (cung phep bien doi log1p ma transform_benchmark dung) + p lag.
        from gpr_engine.econometrics.data_files import transform_benchmark
        lvl = transform_benchmark(raw)
        cols = [lvl.rename(columns={c: f"{c}_LEVEL" for c in lvl.columns})]
        for k in range(1, BATTERY_CONTROL_LAGS + 1):
            cols.append(lvl.shift(k).rename(
                columns={c: f"{c}_LEVEL_L{k}" for c in lvl.columns}))
        extra = pd.concat(cols, axis=1)

    # EPU thang M cung chi biet sau khi thang M ket thuc — align GIONG GPR, neu
    # khong thi control nhin truoc shock mot thang.
    extra = align_monthly_gpr_to_information_time(extra)
    return build_monthly_panel(
        start=start, end=end, refresh=refresh, shock_axis=True, components=True,
        real_macro=True, freight=True, battery=False, extra_monthly=extra)


# ---------------------------------------------------------------------------
# THAY THE: cach dung ten cot control trong estimate_gamma (dong ~149 va ~190)
# ---------------------------------------------------------------------------
def battery_control_names(measure: str, battery: str,
                          battery_mode: str = BATTERY_MODE) -> list[str]:
    """Ten cot control cho ban battery. Thay hai cho hard-code hien tai."""
    if battery != "b":
        return []
    if battery_mode == "same_measure":
        return [f"{c}_{measure}" for c in BATTERY_CONTROLS]
    return ([f"{c}_LEVEL" for c in BATTERY_CONTROLS]
            + [f"{c}_LEVEL_L{k}" for c in BATTERY_CONTROLS
               for k in range(1, BATTERY_CONTROL_LAGS + 1)])
