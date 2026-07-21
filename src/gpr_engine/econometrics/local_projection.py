"""Local Projection (Jorda 2005) — utility DUNG CHUNG cho tang 2 va tang 3.

Xem docs/07_formulas_reference_v2.md §3 (tang 2) va §5.1 (tang 3), docs/06 §2.5.

Vai tro: KHONG con la "model chinh" — la ham nen uoc luong impulse response cho
mot phuong trinh LP bat ky. Tang 2 (tier2_global_macro) va tang 3 (tier3_country)
deu goi ham nay.

Cong thuc uoc luong tai moi horizon h:
    y_{t+h} = alpha_h + beta_h * shock_t + Phi_h * controls_t + eps_{t+h}
IRF = { beta_h : h in horizons }.

HAI CHE DO SUY DIEN (docs/14 M8, pre-register o SCA-01.lp_inference)
---------------------------------------------------------------------------
inference="hac" (MAC DINH, giu tuong thich ban cu)
    Newey-West vi horizon chong lan tao autocorrelation residual. Day la cach
    "sach giao khoa" nhung coverage TOI khi regressor dai dang — chinh la truong
    hop cua ta (GPR level autocorrelated cao).

inference="lag_augmented" (Montiel Olea & Plagborg-Moller 2021)
    Them lag cua CA y LAN shock lam control (lag augmentation), roi dung sai so
    chuan Eicker-Huber-White (HC1), KHONG HAC. Ket qua cua ho: t-stat tiem can
    chuan tac DEU tren mien dai dang (ke ca nghiem don vi), o moi h.

    Vi sao BO duoc HAC du residual VAN tu tuong quan: cai vao phuong sai tiem can
    khong phai residual ma la SCORE. Sau khi partial-out cac lag cua chinh shock,
    phan con lai cua regressor la INNOVATION, nen score la martingale difference
    -> EHW nhat quan, va HAC chi lam hong mau huu han.

    ⚠️ DIEU KIEN THEN CHOT: phai co lag CUA SHOCK trong controls, khong chi lag
    cua y. Neu thieu, regressor chua duoc partial-out thanh innovation va lap
    luan tren SUP DO. Ham nay TU them ca hai — dung tu che bang cach chi truyen
    lag cua y qua `controls`.

    ⚠️ TUONG TAC VOI docs/14 §6.4 (shock = LEVEL hay INNOVATION): lag augmentation
    la CAI LAM CHO shock=LEVEL tro nen bien minh duoc — no partial-out phan da du
    bao duoc cua level ngay trong hoi quy. Khong co no thi LEVEL vao hoi quy dung
    la loi #9. Co no thi he so doc duoc la phan ung voi phan BAT NGO cua level.
    Day la ly le ky thuat cho lua chon A o g0 §7.1.

DAI SUP-T (Montiel Olea & Plagborg-Moller 2019) — simultaneous=True
---------------------------------------------------------------------------
Dai pointwise 90% KHONG bao phu ca duong IRF voi xac suat 90%: nhin 25 horizon
thi ky vong ~2.5 diem nam ngoai NGAY CA KHI mo hinh dung. Doc "IRF vuot 0 o h=7"
tu dai pointwise la doc sai. Dai sup-t nhan SE voi hang so c sao cho TOAN duong
nam trong dai voi xac suat danh nghia.

    c = phan vi (1-alpha) cua  max_h |Z_h|,  Z ~ N(0, Omega)
    Omega = ma tran TUONG QUAN cua cac beta_h qua horizon

Omega uoc luong bang HAM ANH HUONG (influence function), khong bootstrap:
    beta_h - beta = sum_t psi_{h,t},   psi_{h,t} = [(X'X)^{-1} X_t]_j * e_{h,t}
    Cov(beta_h, beta_k) = sum_{t chung} psi_{h,t} * psi_{k,t}
Duong cheo cua ma tran nay CHINH LA HC0 (HC1 sau hieu chinh n/(n-k)) — nen SE
pointwise va dai sup-t den tu CUNG MOT nguon, khong the ton tai hai bo so lech
nhau trong cung mot report. `test_supt_diagonal_matches_hc1` khoa dieu do.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm

DEFAULT_SUPT_SIMS = 10_000
DEFAULT_SUPT_SEED = 0

VALID_INFERENCE = ("hac", "lag_augmented")
VALID_METHOD = ("ols", "quantile")


def _influence(X: np.ndarray, resid: np.ndarray, j: int) -> np.ndarray:
    """psi_t = [(X'X)^{-1} X_t]_j * e_t — dong gop cua quan sat t vao beta_j.

    sum_t psi_t = beta_j_hat - beta_j; sum_t psi_t^2 = phuong sai HC0. Tra ve
    da hieu chinh HC1 (nhan n/(n-k)) de khop cov_type="HC1" cua statsmodels.
    """
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    a = X @ xtx_inv[:, j]                      # (n,)
    psi = a * resid
    return psi * np.sqrt(n / (n - k))          # HC1


def _supt_critical_value(
    cov: np.ndarray, ci: float, n_sim: int, seed: int,
) -> tuple[float, np.ndarray]:
    """Hang so c cua dai sup-t + ma tran tuong quan Omega (MO-PM 2019).

    Mo phong max_h |Z_h| voi Z ~ N(0, Omega). Deterministic theo `seed` — bat
    buoc, vi day la con so di vao report (nguyen tac #4 versioning).
    """
    sd = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    ok = sd > 0
    if ok.sum() < 2:                            # 1 horizon -> sup-t = pointwise
        from scipy.stats import norm
        return float(norm.ppf(0.5 + ci / 2.0)), np.eye(len(sd))

    omega = np.eye(len(sd))
    sub = np.outer(sd[ok], sd[ok])
    omega[np.ix_(ok, ok)] = cov[np.ix_(ok, ok)] / sub
    omega = (omega + omega.T) / 2.0             # doi xung hoa sai so lam tron
    # Chieu ve nua xac dinh duong: sai so uoc luong co the tao tri rieng am nho.
    vals, vecs = np.linalg.eigh(omega)
    omega_psd = vecs @ np.diag(np.clip(vals, 1e-10, None)) @ vecs.T

    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(np.zeros(len(sd)), omega_psd, size=n_sim,
                                    method="eigh")
    c = float(np.quantile(np.max(np.abs(draws[:, ok]), axis=1), ci))
    return c, omega


def _add_lags(work: pd.DataFrame, cols: Iterable[str], lags: int) -> list[str]:
    """Them cot lag 1..lags cho `cols` vao `work` (in-place). Tra ten cot moi."""
    made = []
    for col in cols:
        for k in range(1, lags + 1):
            name = f"__la_{col}_l{k}"
            work[name] = work[col].shift(k)
            made.append(name)
    return made


def run_local_projection(
    df: pd.DataFrame,
    y: str,
    shock: str,
    controls: Iterable[str] = (),
    horizons: Iterable[int] = range(0, 61),
    hac_maxlags: int | None = None,
    ci: float = 0.90,
    return_all: bool = False,
    inference: str = "hac",
    lags: int = 4,
    simultaneous: bool = False,
    method: str = "ols",
    tau: float = 0.5,
    n_sim: int = DEFAULT_SUPT_SIMS,
    seed: int = DEFAULT_SUPT_SEED,
) -> pd.DataFrame:
    """Uoc luong LP: hoi quy y_{t+h} len shock_t (+ controls_t) cho tung h.

    Parameters
    ----------
    df : DataFrame da align theo thoi gian (mot hang = mot ky). Dung thu tu hang
        lam truc thoi gian; khong yeu cau index dac biet.
    y : ten cot bien phu thuoc (return / bien vi mo tang 2).
    shock : ten cot bien shock.
    controls : danh sach cot kiem soat X (VIX, DXY, lag return...).
    horizons : cac h can uoc luong (0 = dong thoi).
    hac_maxlags : lag cho Newey-West khi inference="hac". Mac dinh = max(horizons).
    ci : muc tin cay (0.90 -> z ~ 1.645 cho dai pointwise).
    return_all : False (mac dinh) -> chi he so cua `shock`, wide theo horizon
        (giu tuong thich tang 2). True -> he so cua MOI regressor, long format.
    inference : "hac" (mac dinh, ban cu) | "lag_augmented" (MO-PM 2021: tu them
        lag cua y VA shock, dung HC1 thay HAC). Xem docstring module.
    lags : so lag cho lag augmentation. Nen dat p+1 voi p la bac AR cua chuoi.
        Chi co tac dung khi inference="lag_augmented".
    simultaneous : True -> them cot `ci_low_supt`/`ci_high_supt` (dai sup-t
        MO-PM 2019) va `supt_c` (hang so). CHI ho tro method="ols".
    method : "ols" | "quantile" (hoi quy phan vi tai `tau`).
    tau : phan vi cho method="quantile" (0<tau<1).
    n_sim, seed : mo phong sup-t. `seed` co dinh de con so tai lap duoc.

    Returns
    -------
    return_all=False: DataFrame index=horizon, cot beta/se/tstat/pvalue/
        ci_low/ci_high/nobs (+ ci_low_supt/ci_high_supt/supt_c neu simultaneous).
    return_all=True : DataFrame long [horizon, term, beta, se, ...].

    Notes
    -----
    Dai sup-t cho `method="quantile"` CHUA lam: ham anh huong cua hoi quy phan vi
    can uoc luong mat do (sparsity) tai tau, kem on dinh o duoi. Duong dung la
    bootstrap — se lam bang `arch` o M10, khong tu che o day. Goi
    simultaneous=True voi quantile -> NotImplementedError, khong tra dai sai.
    """
    from scipy.stats import norm

    if inference not in VALID_INFERENCE:
        raise ValueError(f"inference phai thuoc {VALID_INFERENCE}, nhan {inference!r}")
    if method not in VALID_METHOD:
        raise ValueError(f"method phai thuoc {VALID_METHOD}, nhan {method!r}")
    if method == "quantile" and not (0.0 < tau < 1.0):
        raise ValueError(f"tau phai trong (0,1), nhan {tau}")
    if simultaneous and method != "ols":
        raise NotImplementedError(
            "Dai sup-t chua ho tro hoi quy phan vi: ham anh huong cua QuantReg can "
            "uoc luong sparsity tai tau, kem on dinh o duoi. Duong dung la bootstrap "
            "(M10, dung `arch`). Chay simultaneous=False roi bao cao dai pointwise "
            "KEM canh bao boi, dung tra dai sup-t sai.")

    controls = list(controls)
    horizons = list(horizons)

    missing = [c for c in [y, shock, *controls] if c not in df.columns]
    if missing:
        raise KeyError(f"Cot khong co trong df: {missing}. Co: {list(df.columns)}")

    base = df.reset_index(drop=True)
    x_cols = [shock, *controls]

    if inference == "lag_augmented":
        if lags < 1:
            raise ValueError(
                "lag_augmented can lags >= 1 — chinh lag augmentation la thu lam cho "
                "suy dien EHW hop le (MO-PM 2021). lags=0 la LP tran + HC1, KHONG "
                "phai lag-augmented.")
        base = base.copy()
        # Lag cua CA y LAN shock. Thieu lag cua shock thi regressor chua thanh
        # innovation va co so bo HAC sup do (xem docstring module).
        x_cols = [*x_cols, *_add_lags(base, [y, shock], lags)]

    if hac_maxlags is None:
        hac_maxlags = max(horizons) if horizons else 0

    z = norm.ppf(0.5 + ci / 2.0)
    j_shock = 1 + x_cols.index(shock)           # +1 vi cot const dung dau

    rows: dict[int, dict] = {}
    long_rows: list[dict] = []
    psis: dict[int, pd.Series] = {}

    for h in horizons:
        y_h = base[y].shift(-h)
        data = pd.concat([y_h.rename("__y__"), base[x_cols]], axis=1).dropna()
        if len(data) <= len(x_cols) + 1:
            rows[h] = dict(beta=np.nan, se=np.nan, tstat=np.nan, pvalue=np.nan,
                           ci_low=np.nan, ci_high=np.nan, nobs=len(data))
            continue

        Xc = sm.add_constant(data[x_cols], has_constant="add")

        if method == "quantile":
            res = sm.QuantReg(data["__y__"], Xc).fit(q=tau)
        elif inference == "lag_augmented":
            # EHW/HC1 — KHONG HAC. Xem docstring module.
            res = sm.OLS(data["__y__"], Xc).fit(cov_type="HC1")
        else:
            res = sm.OLS(data["__y__"], Xc).fit(
                cov_type="HAC", cov_kwds={"maxlags": max(hac_maxlags, h)})

        beta = res.params[shock]
        se = res.bse[shock]
        rows[h] = dict(
            beta=beta, se=se,
            tstat=res.tvalues[shock], pvalue=res.pvalues[shock],
            ci_low=beta - z * se, ci_high=beta + z * se,
            nobs=int(res.nobs),
        )
        if simultaneous:
            psis[h] = pd.Series(
                _influence(np.asarray(Xc, dtype=float),
                           np.asarray(res.resid, dtype=float), j_shock),
                index=data.index)
        if return_all:
            for term in x_cols:
                b, s = res.params[term], res.bse[term]
                long_rows.append(dict(
                    horizon=h, term=term, beta=b, se=s,
                    tstat=res.tvalues[term], pvalue=res.pvalues[term],
                    ci_low=b - z * s, ci_high=b + z * s, nobs=int(res.nobs),
                ))

    if return_all:
        return pd.DataFrame(long_rows, columns=[
            "horizon", "term", "beta", "se", "tstat", "pvalue",
            "ci_low", "ci_high", "nobs"])

    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "horizon"
    cols = ["beta", "se", "tstat", "pvalue", "ci_low", "ci_high", "nobs"]

    if simultaneous:
        hs = [h for h in horizons if h in psis]
        cov = np.full((len(hs), len(hs)), np.nan)
        for a, ha in enumerate(hs):
            for b, hb in enumerate(hs):
                pa, pb = psis[ha].align(psis[hb], join="inner")
                cov[a, b] = float((pa * pb).sum())
        c, _ = _supt_critical_value(cov, ci, n_sim, seed)
        out["supt_c"] = c
        out["ci_low_supt"] = out["beta"] - c * out["se"]
        out["ci_high_supt"] = out["beta"] + c * out["se"]
        cols += ["ci_low_supt", "ci_high_supt", "supt_c"]

    return out[cols]
