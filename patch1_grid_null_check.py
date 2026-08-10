"""PATCH 1 — them vao cuoi src/gpr_engine/econometrics/multiplicity.py

Khong sua ham nao dang co. Chi them mot ham + hang so.
"""

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
from dataclasses import dataclass


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
        return (
            f"**Kiem dinh muc luoi (null toan cuc):** {self.n_tests} kiem dinh o "
            f"nguong p<{self.alpha:g}. Ky vong duoi null: **{self.expected:.1f}**. "
            f"Quan sat: **{self.observed}** ({self.ratio:.2f}x, z≳{self.z_indep:+.2f}).\n\n"
            f"> {self.verdict}\n"
        )


def grid_null_check(pvalues, alpha: float = 0.10) -> GridNullCheck:
    """So so bac bo tho voi n*alpha.

    Goi tren TOAN BO p-value focal cua luoi (moi thuoc do, moi kenh, moi ban
    battery, moi horizon focal) — khong phai tren mot ho.

    >>> import numpy as np
    >>> r = grid_null_check(np.full(432, 0.5), alpha=0.10)   # khong o nao bac bo
    >>> r.observed, round(r.expected, 1)
    (0, 43.2)
    """
    import numpy as np

    p = np.asarray([x for x in pvalues if x == x], dtype=float)   # bo NaN
    n = int(p.size)
    if n == 0:
        raise ValueError("grid_null_check: khong co p-value nao.")
    obs = int((p < alpha).sum())
    exp = n * alpha
    sd = float(np.sqrt(n * alpha * (1 - alpha)))
    return GridNullCheck(
        n_tests=n, alpha=alpha, observed=obs, expected=exp,
        z_indep=(obs - exp) / sd if sd > 0 else 0.0,
        ratio=obs / exp if exp > 0 else float("nan"),
    )
