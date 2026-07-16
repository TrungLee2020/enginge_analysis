"""tier3_country.py — TANG 3 cascade: COUNTRY TRANSMISSION (G2b). 🔬 research

Xem docs/06 (kien truc), docs/07_formulas_reference_v2.md §4-5 (cong thuc chuan).
Sua 2026-07-16 theo review 08 / phan hoi 09 (docs/10 F2):
  [4.2] BA he so — beta (global-direct) + theta (indirect) + lambda (domestic-direct).
        Ban cu chi co theta+lambda (lam roi beta cua spec goc 01 Lop 4b).
  [4.1] Indirect la TICH CHAP: Indirect(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s)·θ_M(h−s).
        KHONG nhan hai he so cung horizon.
  [4.5] Dong gop kenh = Shapley/LMG cua R². Cong thuc θ²Var(M)/Var(r) da XOA
        (bo covariance, tong co the >100% — CLAUDE.md #12).

Phuong trinh tang 3 (docs/07v2 §5.1, Local Projection theo horizon h):
    r^c_{t+h} = α + Σ_j β_j·GPR^{j,innov}    (GLOBAL-DIRECT, khong qua macro)
              + Σ_M θ_M·M_t                  (INDIRECT, qua tang 2)
              + λ·GPR^{c,⊥,innov}            (DOMESTIC-DIRECT)
              + Φ·X^c + ε
Moi shock la INNOVATION (CLAUDE.md #9). Ket qua goi la "transmission
decomposition" (reduced-form/predictive), KHONG "causal mediation" khi chua co
structural ID (claims matrix 07v2 §6.4).

Params doc tu config/params/<country>.yaml. Khong dien he so tay.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from math import factorial

import pandas as pd
import statsmodels.api as sm

from .local_projection import run_local_projection


def orthogonalize(df: pd.DataFrame, target: str, on: Iterable[str]) -> pd.Series:
    """Tach phan rieng nuoc c: hoi quy target len cac regressor global, tra ve phan du.

    GPR^c = f(GPR_global, GPR_US, GPR_CN, Oil) + GPR^{c,⊥}   (docs/07v2 §4.1, FWL).
    Phan du GPR^{c,⊥} la DOMESTIC-DIRECT shock (λ) cua tang 3 — LUU Y: no la phan
    RIENG cua nuoc c, KHONG phai tac dong truc tiep cua global shock (do la β).
    """
    on = list(on)
    missing = [c for c in [target, *on] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co: {missing}")
    data = df[[target, *on]].dropna()
    X = sm.add_constant(data[on], has_constant="add")
    res = sm.OLS(data[target], X).fit()
    resid = pd.Series(res.resid, index=data.index, name=f"{target}_ORTH")
    return resid.reindex(df.index)


def estimate_tier3(
    df: pd.DataFrame,
    market_ret: str,
    macro_channels: Iterable[str],
    direct_shock: str | None = None,
    global_shocks: Iterable[str] = (),
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 61),
) -> pd.DataFrame:
    """Uoc luong tang 3: beta (global-direct) + theta (indirect) + lambda (domestic).

    Moi he so lay tu CUNG mot model LP (HAC SE) qua run_local_projection(return_all=True).

    Parameters
    ----------
    direct_shock : GPR^{c,⊥} innovation. None cho phep — track daily cua nuoc chi co
        country-GPR monthly thi KHONG co direct shock daily (CLAUDE.md #10).
    global_shocks : cac GPR^{j,innov} (beta). Rong duoc (chi do theta/lambda).

    Returns
    -------
    DataFrame long: [horizon, term, role, coef, se, tstat, pvalue, ci_low, ci_high, nobs]
    role ∈ {beta, theta, lambda, control}.
    """
    macro_channels = list(macro_channels)
    global_shocks = list(global_shocks)
    controls = list(controls)
    horizons = list(horizons)

    if not global_shocks and direct_shock is None:
        raise ValueError("Can it nhat mot shock: global_shocks hoac direct_shock.")

    role_of: dict[str, str] = {}
    for g in global_shocks:
        role_of[g] = "beta"
    for m in macro_channels:
        role_of[m] = "theta"
    if direct_shock is not None:
        role_of[direct_shock] = "lambda"
    for c in controls:
        role_of[c] = "control"

    x_cols = list(role_of)                    # thu tu: beta, theta, lambda, control
    need = [market_ret, *x_cols]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    # run_local_projection nhan (shock, controls) — voi return_all=True moi regressor
    # deu duoc tra he so nen phan chia shock/controls chi la hinh thuc goi ham.
    out = run_local_projection(
        df, y=market_ret, shock=x_cols[0], controls=x_cols[1:],
        horizons=horizons, return_all=True,
    )
    out = out.rename(columns={"beta": "coef"})
    out.insert(2, "role", out["term"].map(role_of))
    return out[["horizon", "term", "role", "coef", "se", "tstat", "pvalue",
                "ci_low", "ci_high", "nobs"]]


# ---------------------------------------------------------------------------
# Transmission decomposition — TICH CHAP (review 4.1, docs/07v2 §5.2)
# ---------------------------------------------------------------------------
def convolve_indirect(
    gamma_j: Mapping[str, pd.Series],
    theta: Mapping[str, pd.Series],
    horizons: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Indirect_{j→c}(h) = Σ_M Σ_{s=0..h} γ_{M,j}(s) · θ^c_M(h−s).

    Dien giai: shock day mediator M o buoc s, mediator danh thi truong o buoc h−s.
    Day la chuoi dong thuc — KHONG phai tich hai he so cung horizon (bug v1).

    gamma_j : {channel: IRF tang 2 γ_{M,j}(s), Series index=horizon}.
    theta   : {channel: θ^c_M(h) tang 3, Series index=horizon}.
    horizons: cac h can tinh; mac dinh = giao cua range hai input.
    IRF thieu buoc nao coi nhu 0 o buoc do (fill 0 — ghi ro trong report).

    Returns: DataFrame index=horizon, mot cot moi channel + 'indirect_total'.
    """
    channels = [ch for ch in gamma_j if ch in theta]
    if not channels:
        raise ValueError(
            f"Khong co channel chung: gamma={list(gamma_j)}, theta={list(theta)}")
    if horizons is None:
        h_max = min(max(int(gamma_j[ch].index.max()) for ch in channels),
                    max(int(theta[ch].index.max()) for ch in channels))
        horizons = range(0, h_max + 1)
    horizons = list(horizons)

    rows = {}
    for h in horizons:
        contrib = {}
        for ch in channels:
            g = gamma_j[ch]
            t = theta[ch]
            total = 0.0
            for s in range(0, h + 1):
                total += float(g.get(s, 0.0)) * float(t.get(h - s, 0.0))
            contrib[ch] = total
        contrib["indirect_total"] = sum(contrib.values())
        rows[h] = contrib

    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "horizon"
    return out[[*channels, "indirect_total"]]


def transmission_decomposition(
    gamma: pd.DataFrame,
    tier3_coefs: pd.DataFrame,
    shock: str,
    horizons: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Phan ra tong tac dong cua global shock j len r^c (docs/07v2 §5.2):

        Total^global_j(h)  = beta_j(h) + Indirect_j(h)      (Indirect = tich chap)
        Total^domestic(h)  = lambda(h)

    gamma       : output tang 2 (estimate_tier2) — cot [macro_var, shock, horizon, beta].
    tier3_coefs : output estimate_tier3 — cot [horizon, term, role, coef, ...].
    shock       : ten global shock j (phai co trong gamma["shock"]; neu vang trong
                  tier3 role=beta thi beta(h)=0 — shock khong vao truc tiep).

    CLAIM (07v2 §6.4): day la "transmission decomposition" reduced-form —
    KHONG dien giai causal khi chua co structural identification.
    """
    g_sub = gamma[gamma["shock"] == shock]
    if g_sub.empty:
        raise ValueError(f"gamma khong co shock {shock!r}: {gamma['shock'].unique()}")
    gamma_j = {ch: grp.set_index("horizon")["beta"].sort_index()
               for ch, grp in g_sub.groupby("macro_var")}

    theta_df = tier3_coefs[tier3_coefs["role"] == "theta"]
    theta = {ch: grp.set_index("horizon")["coef"].sort_index()
             for ch, grp in theta_df.groupby("term")}

    beta_s = (tier3_coefs[(tier3_coefs["role"] == "beta")
                          & (tier3_coefs["term"] == shock)]
              .set_index("horizon")["coef"].sort_index())
    lam_s = (tier3_coefs[tier3_coefs["role"] == "lambda"]
             .set_index("horizon")["coef"].sort_index())

    ind = convolve_indirect(gamma_j, theta, horizons=horizons)
    out = ind.rename(columns={c: f"indirect_{c}" for c in ind.columns
                              if c != "indirect_total"})
    out = out.rename(columns={"indirect_total": "indirect"})
    out["beta_global_direct"] = [float(beta_s.get(h, 0.0)) for h in out.index]
    out["total_global"] = out["beta_global_direct"] + out["indirect"]
    out["domestic"] = [float(lam_s.get(h, float("nan"))) for h in out.index]
    return out


# ---------------------------------------------------------------------------
# Dong gop kenh — Shapley/LMG cua R² (review 4.5, docs/07v2 §5.3)
# ---------------------------------------------------------------------------
def shapley_r2(
    df: pd.DataFrame,
    y: str,
    channels: Iterable[str],
    controls: Iterable[str] = (),
) -> dict:
    """Shapley/LMG decomposition cua R²: chia deu dong gop cua moi channel qua
    moi thu tu dua bien vao — xu ly duoc covariance giua cac kenh (thu khien
    cong thuc θ²Var(M)/Var(r) cu sai, tong co the >100%).

        Share_k = Σ_{S ⊆ K\\{k}} |S|!(|K|−|S|−1)!/|K|! · [R²(S∪{k}) − R²(S)]

    controls (neu co) LUON nam trong model — shares phan ra phan R² TREN baseline
    controls-only: Σ shares = R²(full) − R²(controls). Khong controls: Σ = R²(full).

    Do phuc tap 2^K — K kenh macro ≤ 6 la tuc thoi. K > 15 -> raise (dung sampling).

    Returns: {"shares": {channel: share}, "r2_full": float, "r2_baseline": float}
    """
    channels = list(channels)
    controls = list(controls)
    if not channels:
        raise ValueError("channels rong.")
    if len(channels) > 15:
        raise ValueError(f"K={len(channels)} qua lon cho Shapley exact (2^K subset).")
    missing = [c for c in [y, *channels, *controls] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co: {missing}")

    data = df[[y, *channels, *controls]].dropna()

    def r2(subset: tuple[str, ...]) -> float:
        cols = [*controls, *subset]
        if not cols:
            return 0.0
        X = sm.add_constant(data[list(cols)], has_constant="add")
        return float(sm.OLS(data[y], X).fit().rsquared)

    cache = {(): r2(())}
    K = len(channels)
    for r in range(1, K + 1):
        for S in combinations(channels, r):
            cache[tuple(sorted(S))] = r2(S)

    shares = {}
    for k in channels:
        others = [c for c in channels if c != k]
        total = 0.0
        for r in range(0, len(others) + 1):
            w = factorial(r) * factorial(K - r - 1) / factorial(K)
            for S in combinations(others, r):
                key = tuple(sorted(S))
                key_k = tuple(sorted([*S, k]))
                total += w * (cache[key_k] - cache[key])
        shares[k] = total

    return {
        "shares": shares,
        "r2_full": cache[tuple(sorted(channels))],
        "r2_baseline": cache[()],
    }
