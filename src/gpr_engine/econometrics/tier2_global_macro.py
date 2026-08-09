"""tier2_global_macro.py — TANG 2 cascade: GLOBAL MACRO RESPONSE (G2a). 🔬 research

Xem docs/06 §2.3, docs/07 §3.

"1 cu soc dia chinh tri day dau / do / risk-off toan cau bao nhieu."
Day la deliverable DOC LAP ("Global Macro Impact") — generic, khong can VN.

Cong thuc (Local Projection Jorda, moi bien vi mo M, moi horizon h):
    M_{t+h} = a + Σ_j γ_{M,j} · shock_{j,t} + Σ_k ρ · M_{t-k} + η
Uoc luong tung (macro_var, shock) rieng bang run_local_projection (HAC SE).

Ket qua = IRF panel: (macro_var, shock, horizon) -> γ + dai tin cay.
Theo channel (khi co S-GPR): chay rieng shock kenh energy vs trade -> γ khac nhau.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from .local_projection import (
    DEFAULT_SUPT_SEED,
    DEFAULT_SUPT_SIMS,
    run_local_projection,
)

DEFAULT_MACRO = ["oil", "dxy", "vix", "us10y"]
DEFAULT_SHOCKS = ["GPRD", "GPRD_ACT", "GPRD_THREAT"]

BASE_COLS = ["macro_var", "shock", "horizon", "beta", "se", "tstat",
             "pvalue", "ci_low", "ci_high", "nobs", "converged"]
SUPT_COLS = ["ci_low_supt", "ci_high_supt", "supt_c"]


def estimate_tier2(
    df: pd.DataFrame,
    macro_vars: Iterable[str] = DEFAULT_MACRO,
    shocks: Iterable[str] = DEFAULT_SHOCKS,
    shock_groups: Iterable[Sequence[str]] | None = None,
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 31),
    macro_lags: int = 1,
    inference: str = "hac",
    lags: int = 4,
    simultaneous: bool = False,
    method: str = "ols",
    tau: float = 0.5,
    ci: float = 0.90,
    n_sim: int = DEFAULT_SUPT_SIMS,
    seed: int = DEFAULT_SUPT_SEED,
) -> pd.DataFrame:
    """Uoc luong tang 2 cho moi (macro_var, shock).

    df : da align + transform (dataset.transform_global_macro cho macro; log1p_gpr cho shock).
    macro_lags : so lag cua chinh bien vi mo dua vao controls (rho trong cong thuc).
        CHI dung khi inference="hac" — xem canh bao ben duoi.

    Tham so suy dien (docs/14 M8/M9, pre-register o SCA-01.lp_inference)
    ---------------------------------------------------------------------
    Truyen thang xuong `run_local_projection`; MAC DINH giu nguyen ban cu
    (hac / OLS / khong sup-t) nen moi report da sinh khong doi. Bang γ cua
    Phase 1a phai goi voi inference="lag_augmented", simultaneous=True va lap
    method="quantile" theo tau — day la spec da khoa trong registry, khong phai
    lua chon cua runner.

    ⚠️ inference="lag_augmented" ep `macro_lags=0`. Lag augmentation TU them lag
    cua y (=M) va cua shock; giu them `macro_lags` se tao cot lag TRUNG KHIT voi
    cot ma run_local_projection sinh ra -> X'X suy bien, pinv chia doi he so
    giua hai cot giong het nhau va SE mat y nghia. Dieu chinh so lag bang `lags`,
    khong bang `macro_lags`.

    shock_groups — NHIEU regressor trong CUNG mot hoi quy (P1.4)
    ------------------------------------------------------------
    `shocks` chay MOI thuoc do mot hoi quy rieng, va chi bao cao he so cua dung
    thuoc do do. Spec CHINH cua docs/17_master_plan.md §4.1 (spec kep) can dieu
    khac: ANTICIPATED va SURPRISE phai vao CUNG mot hoi quy va CA HAI he so deu
    duoc bao cao. Truoc P1.4 dieu do khong lam duoc — regressor thu hai chi co
    the nhet vao `controls` va he so cua no bi VUT.

        estimate_tier2(panel, shock_groups=[["GPR_ANTICIPATED", "GPR_SURPRISE"]])

    Moi nhom -> MOT hoi quy; moi thanh vien nhom -> mot hang ket qua, phan biet
    bang cot `spec` (= "A+B"). He so cua control/lag augmentation KHONG duoc tra
    ve: chung la nuisance, doc nhu γ la sai.

    Hai cot CHI co o nhanh nay: `sd_regressor` va `beta_standardized` (= β×sd).
    Bat buoc vi trong mot hoi quy nhieu regressor, cac regressor co phuong sai
    khac han nhau — Var(ANTICIPATED)/Var(SURPRISE) ~0.1 tren chuoi sai phan, va
    E2 do duoc 48.9% o DAO CHIEU ket luan khi doc he so tho thay vi chuan hoa.
    Bao cao so tho o day roi so sanh chung la lap lai dung tai nan thang do ma
    registry da ghi cho LEVEL+JUMP.

    Dung duoc DONG THOI voi `shocks` (hai nhanh gop vao cung mot bang ket qua).

    Returns
    -------
    DataFrame long: [macro_var, shock, horizon, beta, se, tstat, pvalue,
                     ci_low, ci_high, nobs] (+ ci_low_supt/ci_high_supt/supt_c
    khi simultaneous=True; + spec/sd_regressor/beta_standardized khi dung
    `shock_groups`). beta = γ (impulse response).
    """
    macro_vars = list(macro_vars)
    shocks = list(shocks)
    groups = [list(g) for g in (shock_groups or [])]
    controls = list(controls)
    horizons = list(horizons)

    if not shocks and not groups:
        raise ValueError("Phai co it nhat mot trong `shocks` / `shock_groups`.")
    for g in groups:
        if len(g) < 2:
            raise ValueError(
                f"shock_groups={g!r}: mot NHOM phai co >=2 regressor (muc dich la "
                "dua chung vao CUNG mot hoi quy). Mot regressor thi dung `shocks`.")
        if len(set(g)) != len(g):
            raise ValueError(f"shock_groups={g!r}: trung ten regressor -> cot trung "
                             "khit, X'X suy bien, SE vo nghia.")

    if inference == "lag_augmented" and macro_lags:
        raise ValueError(
            f"inference='lag_augmented' voi macro_lags={macro_lags}: lag cua M se bi "
            "them HAI LAN (mot lan o day, mot lan trong run_local_projection) -> cot "
            "trung khit, X'X suy bien, SE vo nghia. Dat macro_lags=0 va dieu chinh "
            "do sau lag bang tham so `lags`.")

    missing = [c for c in [*macro_vars, *shocks, *controls] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    frames = []
    for M in macro_vars:
        # Them lag cua chinh M vao controls (autoregressive term ρ)
        work = df.copy()
        lag_cols = []
        for k in range(1, macro_lags + 1):
            col = f"__{M}_lag{k}"
            work[col] = work[M].shift(k)
            lag_cols.append(col)

        for shock in shocks:
            irf = run_local_projection(
                work, y=M, shock=shock,
                controls=[*controls, *lag_cols],
                horizons=horizons,
                inference=inference, lags=lags, simultaneous=simultaneous,
                method=method, tau=tau, ci=ci, n_sim=n_sim, seed=seed,
            )
            irf = irf.reset_index()  # horizon la cot
            irf.insert(0, "shock", shock)
            irf.insert(0, "macro_var", M)
            frames.append(irf)

        for group in groups:
            missing_g = [c for c in group if c not in work.columns]
            if missing_g:
                raise KeyError(f"shock_groups: cot khong co trong df: {missing_g}")
            head, rest = group[0], list(group[1:])
            irf = run_local_projection(
                work, y=M, shock=head,
                controls=[*rest, *controls, *lag_cols],
                horizons=horizons,
                inference=inference, lags=lags, simultaneous=simultaneous,
                method=method, tau=tau, ci=ci, n_sim=n_sim, seed=seed,
                return_all=True,
            )
            # Chi giu he so cua CAC REGRESSOR TRONG NHOM. Cot lag augmentation
            # va control la nuisance — doc chung nhu β/θ la sai (CLAUDE.md, ghi
            # chu `role="lag_augmentation"` cua tier3).
            irf = irf[irf["term"].isin(group)].copy()
            irf.insert(0, "spec", "+".join(group))
            irf = irf.rename(columns={"term": "shock"})
            irf.insert(0, "macro_var", M)
            # β CHUAN HOA — bat buoc khi trong mot hoi quy co nhieu regressor
            # khac phuong sai (docs/17_master_plan.md §4.1: Var(ANT)/Var(SUR)~0.1,
            # E2 do 48.9% o dao chieu ket luan neu doc he so tho).
            sd = {c: float(work[c].std()) for c in group}
            irf["sd_regressor"] = irf["shock"].map(sd)
            irf["beta_standardized"] = irf["beta"] * irf["sd_regressor"]
            frames.append(irf)

    out = pd.concat(frames, ignore_index=True)
    base = BASE_COLS if not groups else ["spec", *BASE_COLS,
                                         "sd_regressor", "beta_standardized"]
    cols = [c for c in base if c in out.columns]
    return out[cols + [c for c in SUPT_COLS if c in out.columns]]


def global_macro_impact_index(irf: pd.DataFrame, shock: str = "GPRD") -> pd.DataFrame:
    """Tom tat IRF thanh chi so 'Global Macro Impact' cho 1 shock:
    voi moi macro_var lay γ tai h=0 (tac dong tuc thoi) — dung de xuat sang gpr_indices.
    """
    sub = irf[(irf["shock"] == shock) & (irf["horizon"] == 0)]
    return sub[["macro_var", "beta", "ci_low", "ci_high"]].reset_index(drop=True)
