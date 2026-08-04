"""s_gpr.py — S-GPR: chi so tu phat ngon so cap (chan B). CONG THUC, khong LLM.

Spec: docs/00 §2.5. Dau vao la BANG DIEM tu scoring.statement_scorer (LLM da do
xong o tang truoc); tu day tro di chi con so hoc — dung phan cong docs/15 §0.

    S-GPR_{a->b, t}  = Σ_i w(role_i) · max(v_i, 0) · specificity_i   (leo thang)
    S-CONC_{a->b, t} = Σ_i w(role_i) · max(-v_i, 0)                  (hoa giai)
    S-GPR_global_t   = Σ_pairs trade_weight_pair · S-GPR_pair,t

Ba quy tac cua spec, code phai giu dung:
  1. KHONG tron hai chieu thanh mot so (net) — leo thang va hoa giai tac dong
     bat doi xung len thi truong, giu rieng de he so tu do.
  2. `w(role)` chi la KHOI TAO bang thu bac (CLAUDE.md #7) — gia tri cuoi phai
     uoc luong tu event study (speaker fixed-effects). Vi the DEFAULT_ROLE_
     WEIGHTS_INIT co hau to _INIT va moi ham nhan `role_weights` de thay the;
     role la thi raise chu khong gan trong so ngam.
  3. Chuan hoa theo so phat ngon cua nguon trong ky — moi nguon co nhip dang
     khac nhau (Truth Social vai chuc post/ngay vs MOFA 1 hop bao/ngay), khong
     chuan hoa thi nguon dang nhieu chi phoi chi so bang so luong.

Cong thuc hoa giai CO Y khong nhan specificity (theo spec §2.5 nguyen van) —
neu sau nay muon doi xung hoa, do la thay doi spec o docs/00 truoc.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

# KHOI TAO theo thu bac (docs/00 §2.5) — KHONG phai trong so cuoi (#7).
# central_bank_governor 0.8 danh cho kenh tai chinh.
DEFAULT_ROLE_WEIGHTS_INIT: dict[str, float] = {
    "head_of_state": 1.0,
    "minister": 0.6,
    "spokesperson": 0.4,
    "central_bank_governor": 0.8,
}

REQUIRED_SCORE_COLS = ["published_at", "source", "actor_country",
                       "target_country", "v", "specificity", "speaker_role"]


def pair_key(actor: str, target: str) -> str:
    """'USA>CHN' — co huong (a->b khac b->a, thang do leo thang theo chieu noi)."""
    return f"{actor}>{target}"


def _role_weights_series(roles: pd.Series,
                         role_weights: Mapping[str, float] | None) -> pd.Series:
    weights = dict(DEFAULT_ROLE_WEIGHTS_INIT if role_weights is None
                   else role_weights)
    unknown = sorted(set(roles.dropna()) - set(weights))
    if unknown:
        raise KeyError(
            f"speaker_role chua co trong w(role): {unknown}. Them vao role_weights "
            "mot cach tuong minh — gan trong so ngam la vi pham CLAUDE.md #7 "
            "(w(role) phai kiem soat duoc, gia tri cuoi tu event study).")
    return roles.map(weights)


def statement_contributions(
    scores: pd.DataFrame,
    role_weights: Mapping[str, float] | None = None,
    normalize_by_source: bool = True,
) -> pd.DataFrame:
    """Dong gop tung phat ngon vao 2 chieu chi so (buoc trung gian, audit duoc).

    Tra ve scores + [pair, date, w_role, esc, conc, n_source_day]:
        esc  = w(role)·max(v,0)·specificity / n_source_day
        conc = w(role)·max(-v,0)            / n_source_day
    n_source_day = so phat ngon CUNG NGUON cung ngay (chuan hoa nhip dang;
    normalize_by_source=False thi = 1). Hang thieu actor/target bi LOAI va dem
    o attrs["n_dropped_no_pair"] — pair khong xac dinh thi khong vao chi so cap.
    """
    missing = [c for c in REQUIRED_SCORE_COLS if c not in scores.columns]
    if missing:
        raise KeyError(f"Bang diem thieu cot: {missing}. Can {REQUIRED_SCORE_COLS}")

    df = scores.copy()
    has_pair = df["actor_country"].notna() & df["target_country"].notna()
    n_dropped = int((~has_pair).sum())
    df = df[has_pair].copy()

    df["pair"] = [pair_key(a, b) for a, b in
                  zip(df["actor_country"], df["target_country"])]
    df["date"] = pd.to_datetime(df["published_at"]).dt.normalize()
    df["w_role"] = _role_weights_series(df["speaker_role"], role_weights)

    v = df["v"].astype(float)
    esc_raw = df["w_role"] * np.maximum(v, 0.0) * df["specificity"].astype(float)
    conc_raw = df["w_role"] * np.maximum(-v, 0.0)

    if normalize_by_source:
        n_src = df.groupby(["source", "date"])["v"].transform("size")
    else:
        n_src = pd.Series(1.0, index=df.index)
    df["n_source_day"] = n_src
    df["esc"] = esc_raw / n_src
    df["conc"] = conc_raw / n_src

    df.attrs["n_dropped_no_pair"] = n_dropped
    return df


def s_gpr_pair(
    scores: pd.DataFrame,
    window: int = 7,
    role_weights: Mapping[str, float] | None = None,
    normalize_by_source: bool = True,
    full_range: bool = True,
) -> pd.DataFrame:
    """Chi so cap co huong theo NGAY: rolling sum `window` ngay cua dong gop.

    Returns: DataFrame long [date, pair, s_gpr, s_conc]. Ngay khong co phat
    ngon = 0 (chi so CUONG DO dang flow: im lang nghia la khong ai leo thang,
    khac voi NaN "khong quan sat"). full_range=True trai du moi ngay lich giua
    min-max de rolling window co nghia; window tinh theo NGAY LICH (7 = "7d"
    trong Measurement Card docs/11 §2.2).
    """
    if window < 1:
        raise ValueError(f"window >= 1, nhan {window}")
    contrib = statement_contributions(scores, role_weights, normalize_by_source)
    if contrib.empty:
        return pd.DataFrame(columns=["date", "pair", "s_gpr", "s_conc"])

    daily = (contrib.groupby(["pair", "date"])[["esc", "conc"]].sum()
             .rename(columns={"esc": "s_gpr", "conc": "s_conc"}))

    frames = []
    for pair, grp in daily.groupby(level="pair"):
        g = grp.droplevel("pair").sort_index()
        if full_range:
            idx = pd.date_range(g.index.min(), g.index.max(), freq="D")
            g = g.reindex(idx, fill_value=0.0)
        g = g.rolling(window, min_periods=1).sum()
        g.index.name = "date"
        g = g.reset_index()
        g.insert(1, "pair", pair)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    out.attrs["n_dropped_no_pair"] = contrib.attrs["n_dropped_no_pair"]
    out.attrs["window_days"] = window
    return out


def s_gpr_global(
    pair_index: pd.DataFrame,
    trade_weights: Mapping[str, float],
) -> pd.DataFrame:
    """S-GPR_global_t = Σ_pairs trade_weight_pair · S-GPR_pair,t (ca 2 chieu).

    `trade_weights` BAT BUOC do caller cung cap va phai phu MOI pair co mat —
    thieu pair nao raise. Khong co trong so mac dinh: trade weight la du lieu
    (tra tu thuong mai song phuong), khong phai hang so code (#7 cung tinh than).
    """
    pairs = set(pair_index["pair"].unique())
    missing = sorted(pairs - set(trade_weights))
    if missing:
        raise KeyError(
            f"trade_weights thieu pair: {missing}. Bo pair khoi chi so global phai "
            "la quyet dinh tuong minh (weight=0), khong phai do quen.")
    w = pair_index["pair"].map(trade_weights)
    tmp = pair_index.assign(_wg=pair_index["s_gpr"] * w,
                            _wc=pair_index["s_conc"] * w)
    out = (tmp.groupby("date")[["_wg", "_wc"]].sum()
           .rename(columns={"_wg": "s_gpr_global", "_wc": "s_conc_global"}))
    return out


def expanding_percentile(s: pd.Series, min_periods: int = 60) -> pd.Series:
    """Phan vi cua gia tri tai t so voi LICH SU toi t — khong nhin tuong lai.

    Dung cho Measurement Card ("phan vi 94 ke tu 2015", docs/11 §2.2) va lam
    input percentile cho Escalation Ladder. Percentile tai t chi dung du lieu
    toi t nen khong bao gio doi khi co them du lieu sau — cung tinh than
    available_at (CLAUDE.md #11): con so phat ra hom nay phai bat bien ve sau.

    Dinh nghia STRICT: % lich su NHO HON han gia tri hom nay. Voi chuoi
    zero-inflated (JUMP/S-GPR: da so ngay = 0, thinh thoang spike — dung dac
    tinh ma registry KĐ-E1c ghi nhan), dinh nghia "<=" se cho ngay im ang
    percentile ~100 (moi gia tri deu <= 0) va trigger nguong ">95" no moi ngay.
    Strict "<" cho ngay im ang percentile 0, spike moi len cao — dung nghia
    "vuot X% lich su" cua trigger.
    """
    def _pct(x: np.ndarray) -> float:
        return float((x[:-1] < x[-1]).mean() * 100.0) if len(x) > 1 else 0.0

    return s.expanding(min_periods=min_periods).apply(_pct, raw=True)
