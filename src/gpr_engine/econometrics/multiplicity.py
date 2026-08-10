"""multiplicity.py — hieu chinh KIEM DINH BOI giua cac OUTCOME (docs/14 M10).

Pham vi HEP MOT CACH CO Y. Boi cua bang γ chia ba chieu (docs/14 §1.3):

    horizon (h=0..24, ×25)  -> XU LY XONG boi dai sup-t (local_projection,
                               simultaneous=True). KHONG hieu chinh lai o day —
                               phat hai lan cung mot chieu la mat het power.
    outcome (8 bien, ×8)    -> CHINH LA VIEC CUA FILE NAY.
    thuoc do shock (×3)     -> KHONG phai boi neu SHOCK la TRUC BAO CAO (ba bang
                               rieng, ba cau hoi rieng) thay vi ba lan thu cung
                               mot gia thuyet. Quyet dinh o `g0` §7.1 — chua ky.

Vi sao Holm chu khong phai SPA/StepM: SPA (Hansen) va StepM (Romano-Wolf) sinh ra
de so nhieu CHIEN LUOC/mo hinh voi mot benchmark, va can bootstrap tren ma tran
loi de bat phu thuoc. O day so kiem dinh nho (3-8) va cai can la mot thu tuc
FWER khong gia dinh gi ve phu thuoc. Holm dung duoc voi phu thuoc BAT KY, khong
tham so, khong tu che. Conservative khi cac outcome tuong quan manh (oil/dxy/vix
/us10y chac chan co) — day la DANH DOI da biet, phai ghi vao report chu khong
sua bang cach doi sang thu tuc long hon sau khi thay p-value.

⚠️ `family` KHONG CO MAC DINH. "Ho kiem dinh la gi" la quyet dinh governance dang
cho ky (`docs/14` §6.6: A = moi outcome mot ho · B = nhom outcome da pre-register
{asset_price, real_macro, physical} · C = ca bang γ). Chon ho SAU khi nhin
p-value la dung cai HARKing ma registry sinh ra de chan, nen ham bat caller khai
bao tuong minh va ghi lai `family` trong ket qua de report truy duoc.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Nhom outcome da pre-register o SCA-01.report_axis_outcome (config/hypothesis_
# registry.yaml). Day la lua chon B cua docs/14 §6.6 — DE SAN cho caller dung
# NEU quyet dinh duoc ky, KHONG phai mac dinh cua ham.
PREREGISTERED_OUTCOME_FAMILIES: dict[str, tuple[str, ...]] = {
    "asset_price": ("oil", "dxy", "vix", "us10y"),
    "real_macro": ("ip", "cpi", "infl_exp"),
    "physical_channel": ("freight",),
}


def holm(pvalues: Sequence[float], alpha: float = 0.10) -> pd.DataFrame:
    """Holm (1979) step-down: kiem soat FWER voi phu thuoc BAT KY.

    Sap p tang dan; bac bo p_(i) khi p_(j) <= alpha/(m-j+1) voi MOI j <= i (dieu
    kien "moi" chinh la buoc step-down — gap p dau tien khong qua nguong thi dung
    han, khong xet tiep).

    p dieu chinh: p_adj_(i) = max_{j<=i} min(1, (m-j+1)·p_(j)) — don dieu hoa de
    so sanh truc tiep voi alpha. NaN duoc GIU nguyen (spec khong hoi tu duoc) va
    KHONG tinh vao m: dem no nhu mot kiem dinh la tu phat vi mot o that bai ky
    thuat.

    Returns: DataFrame [pvalue, rank, threshold, pvalue_adj, reject], giu thu tu
    va index cua input.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha phai trong (0,1), nhan {alpha}")
    p = pd.Series(pvalues, dtype=float)
    if ((p < 0) | (p > 1)).any():
        raise ValueError("pvalues phai trong [0,1] — kiem lai da truyen dung cot chua.")

    valid = p.dropna()
    m = len(valid)
    out = pd.DataFrame({
        "pvalue": p,
        "rank": pd.Series(np.nan, index=p.index, dtype=float),
        "threshold": pd.Series(np.nan, index=p.index, dtype=float),
        "pvalue_adj": pd.Series(np.nan, index=p.index, dtype=float),
        "reject": pd.Series(False, index=p.index, dtype=bool),
    })
    if m == 0:
        return out

    order = valid.sort_values(kind="mergesort").index
    ranks = np.arange(1, m + 1)
    sorted_p = valid.loc[order].to_numpy()

    thresholds = alpha / (m - ranks + 1)
    adj = np.minimum(1.0, (m - ranks + 1) * sorted_p)
    adj = np.maximum.accumulate(adj)            # don dieu hoa (step-down)

    # Step-down: dung o buoc dau tien khong qua nguong.
    passed = sorted_p <= thresholds
    stop = np.argmin(passed) if not passed.all() else m
    reject = np.zeros(m, dtype=bool)
    reject[:stop] = True

    out.loc[order, "rank"] = ranks
    out.loc[order, "threshold"] = thresholds
    out.loc[order, "pvalue_adj"] = adj
    out.loc[order, "reject"] = reject
    return out


def holm_by_family(
    df: pd.DataFrame,
    family: Mapping[str, Sequence[str]],
    outcome_col: str = "macro_var",
    pvalue_col: str = "pvalue",
    alpha: float = 0.10,
    strict: bool = True,
) -> pd.DataFrame:
    """Ap Holm RIENG trong tung ho outcome. `family` = {ten ho: [outcome,...]}.

    Moi hang cua `df` la MOT kiem dinh. Voi bang γ chay kem dai sup-t, mot kiem
    dinh = mot (outcome, shock) tren CA duong IRF — KHONG phai mot (outcome,
    shock, horizon). Loc `df` xuong dung tap kiem dinh do TRUOC khi goi; truyen
    ca 25 horizon vao day la phat chieu horizon lan thu hai (sup-t da phat roi)
    va se xoa sach ket qua.

    strict=True: outcome nao khong nam trong `family` nao -> raise. Bo im lang
    mot outcome khoi hieu chinh la lam nhe FWER ma khong ai thay trong report.

    Returns: `df` + cot [family, rank, threshold, pvalue_adj, reject, family_size].
    """
    if outcome_col not in df.columns or pvalue_col not in df.columns:
        raise KeyError(
            f"Can cot {outcome_col!r} va {pvalue_col!r}. Co: {list(df.columns)}")

    of_outcome: dict[str, str] = {}
    for fam, members in family.items():
        for o in members:
            if o in of_outcome:
                raise ValueError(
                    f"Outcome {o!r} nam trong ca {of_outcome[o]!r} lan {fam!r}. Ho phai "
                    "phan hoach — outcome o hai ho bi phat hai lan.")
            of_outcome[o] = fam

    fam_of_row = df[outcome_col].map(of_outcome)
    unknown = sorted(set(df.loc[fam_of_row.isna(), outcome_col]))
    if unknown:
        msg = (f"Outcome khong thuoc ho nao: {unknown}. Ho da khai: "
               f"{ {k: list(v) for k, v in family.items()} }.")
        if strict:
            raise ValueError(
                msg + " Bo im lang mot outcome khoi hieu chinh = lam nhe FWER ma "
                "report khong ghi. Khai bao no, hoac dat strict=False CO CHU DICH.")

    out = df.copy()
    out["family"] = fam_of_row
    for col in ("rank", "threshold", "pvalue_adj"):
        out[col] = np.nan
    out["reject"] = False
    out["family_size"] = np.nan

    for idx in out.dropna(subset=["family"]).groupby("family").groups.values():
        res = holm(out.loc[idx, pvalue_col], alpha=alpha)
        for col in ("rank", "threshold", "pvalue_adj", "reject"):
            out.loc[idx, col] = res[col].to_numpy()
        out.loc[idx, "family_size"] = int(res["pvalue"].notna().sum())
    return out


# ---------------------------------------------------------------------------
# Kiem dinh muc LUOI: quan sat co nhieu hon nhieu thuan khong?
# ---------------------------------------------------------------------------
# Holm o tren tra loi "o NAO song sot trong ho nay". No KHONG tra loi "toan bo
# luoi co nhieu hon nhieu khong" — va hai cau hoi do cho ket luan nguoc nhau khi
# so kiem dinh lon con co ho thi nho.
#
# Vi du that (T2_full_f2579b30928f): 432 kiem dinh focal, 34 co p tho < 0.10, 15
# "song sot Holm". Nghe nhu 15 phat hien. Nhung duoi NULL TOAN CUC, so bac bo ky
# vong o nguong 0.10 la 43.2 — quan sat 34 nam DUOI muc nhieu thuan sinh ra. Ho
# Holm co 4/3/1 outcome nen nguong nghiem nhat chi la alpha/4; no gan nhu khong
# phat gi so voi quy mo 432 kiem dinh cua luoi.
#
# E[bac bo] = n*alpha dung BAT KE cac kiem dinh tuong quan den dau (ky vong cong
# tinh). Chi PHUONG SAI moi phinh theo tuong quan — nen z duoi day la CAN DUOI
# cua |z| that, dung de doc dau va do lon xap xi, khong dung de bao cao p-value.
@dataclass(frozen=True)
class GridNullCheck:
    """Doi chieu so bac bo tho voi ky vong duoi null toan cuc."""

    n_tests: int
    alpha: float
    observed: int
    expected: float
    z_indep: float          # CAN DUOI cua |z| that (xem ghi chu tren)
    ratio: float            # observed / expected

    @property
    def verdict(self) -> str:
        if self.observed <= self.expected:
            return ("DUOI ky vong null — luoi nhat quan voi KHONG co tac dong o "
                    "dau ca. Khong duoc doc cac o song sot Holm nhu phat hien.")
        if self.z_indep < 1.64:
            return ("TREN ky vong null nhung trong khoang nhieu — chua tach duoc "
                    "khoi null toan cuc.")
        return ("TREN ky vong null ro ret — co tin hieu o muc luoi. Van phai xem "
                "Holm de biet O NAO.")

    def to_markdown(self) -> str:
        """Render doc lap (notebook/script rieng).

        ⚠️ Runner co Guard P1 tren `stats` (vd `scripts/run_t2_full.py`) thi
        KHONG dung ham nay: dua cac truong o tren vao `stats` roi tham chieu,
        khong thi guard mat hieu luc voi dung khoi so nay.
        """
        return (
            f"**Kiem dinh muc luoi (null toan cuc):** {self.n_tests} kiem dinh o "
            f"nguong p<{self.alpha:g}. Ky vong duoi null: **{self.expected:.1f}**. "
            f"Quan sat: **{self.observed}** ({self.ratio:.2f}x, z≳{self.z_indep:+.2f}).\n\n"
            f"> {self.verdict}\n"
        )


def grid_null_check(pvalues: Sequence[float], alpha: float = 0.10) -> GridNullCheck:
    """So so bac bo tho voi n*alpha.

    Goi tren TOAN BO p-value focal cua luoi (moi thuoc do, moi kenh, moi ban
    battery, moi horizon focal) — khong phai tren mot ho.

    >>> import numpy as np
    >>> r = grid_null_check(np.full(432, 0.5), alpha=0.10)   # khong o nao bac bo
    >>> r.observed, round(r.expected, 1)
    (0, 43.2)
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha phai trong (0,1), nhan {alpha}")
    p = pd.Series(pvalues, dtype=float).dropna().to_numpy()   # NaN = spec hong
    n = int(p.size)
    if n == 0:
        raise ValueError("grid_null_check: khong co p-value nao.")
    if ((p < 0) | (p > 1)).any():
        raise ValueError("pvalues phai trong [0,1] — kiem lai da truyen dung cot chua.")
    obs = int((p < alpha).sum())
    exp = n * alpha
    sd = float(np.sqrt(n * alpha * (1 - alpha)))
    return GridNullCheck(
        n_tests=n, alpha=alpha, observed=obs, expected=exp,
        z_indep=(obs - exp) / sd if sd > 0 else 0.0,
        ratio=obs / exp if exp > 0 else float("nan"),
    )
