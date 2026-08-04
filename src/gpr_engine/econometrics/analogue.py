"""analogue.py — TANG 4: truy hoi episode tuong tu (M5, docs/11 §6). 🔬 research

"Chuyen nay giong nhung lan nao truoc day, va nhung lan do dien bien ra sao."

⚠️ XUAT XU — DOC TRUOC KHI TIN (docs/11 §6 nguyen van): thiet ke nay la SUY LUAN
tu case-based reasoning, **khong co tien le trong literature GPR**. Muc do chac
chan THAP HON §5.2/§5.3/§5.5 von deu co nguon. Tien le PHUONG PHAP gan nhat: IMF
GFSR dinh nghia su kien GPR lon la khi chi so vuot 2 do lech chuan roi do bien
dong tich luy cua chung khoan tai 1 ngay / 1 tuan / 1 thang / 3 / 6 / 12 thang —
event-study phan phoi, cung ho.

CLAIM CEILING = `association`. Day la event-study MO TA, khong co identification.
Khong duoc goi la du bao, khong duoc goi la nhan qua (07v2 §6.4).

GIA TRI: hoat dong **ke ca khi tang 2/3 cho ket qua null** — no khong phu thuoc
vao mot he so nao co y nghia. Va no khong co bac tu do de overfit: descriptor
pre-register, k-NN khong hoc tham so.

BON RANG BUOC BAT BUOC (docs/11 §6), tat ca deu la CO CHE trong code nay:
  1. n < 5  -> IM LANG (khong xuat phan boi canh). Cong P3.
  2. IQR doi dau -> ghi "phan tan, khong ket luan", khong dua trung vi ra mot minh.
  3. LUON liet ke duoc danh sach episode — "6 lan do la nhung lan nao". Tinh kiem
     chung duoc la diem ban hang chinh; day la cho chan A (1985+) tao gia tri ma
     doi thu khong co.
  4. Chi dung du lieu `available_at <= t` (#11), KE CA trong retrieval. Neighbor
     phai NAM TRUOC t — lay episode tuong lai lam "tien le" la look-ahead tra hinh.

Loai tru cua so ±30 ngay quanh t: chong ro ri trung episode (cung mot dot cang
thang bi dem nhieu lan lam "nhieu tien le doc lap").
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_K = 8
MIN_NEIGHBOURS = 5          # docs/11 §6: n<5 -> im lang (cong P3)
DEFAULT_EXCLUDE_DAYS = 30   # ±30 ngay quanh t
REGIME_EDGES = ("2008-01-01", "2015-01-01")


class InsufficientAnalogues(Exception):
    """n < MIN_NEIGHBOURS — KHONG xuat boi canh, khong ha nguong de co so.

    Ha nguong khi khong tim du tien le la bien "khong biet" thanh "biet mo ho",
    dung kieu that bai ma cong P3 sinh ra de chan.

    Mang theo `n_found`/`n_required` dang SO (khong chi trong message): composer
    phai dung duoc chung ma khong phai parse chuoi — so trong van xuoi khong doi
    chieu duoc voi payload, Guard P1 se chan (va no da chan that).
    """

    def __init__(self, message: str, n_found: int = 0, n_required: int = MIN_NEIGHBOURS):
        super().__init__(message)
        self.n_found = int(n_found)
        self.n_required = int(n_required)


def regime_flag(idx: pd.DatetimeIndex) -> pd.Series:
    """pre-2008 / 2008-2015 / post-2015 — mot cot so hang thu tu (docs/11 §6)."""
    a, b = (pd.Timestamp(x) for x in REGIME_EDGES)
    vals = np.where(idx < a, 0.0, np.where(idx < b, 1.0, 2.0))
    return pd.Series(vals, index=idx, name="regime")


def build_descriptor(
    shocks: pd.DataFrame,
    macro: pd.DataFrame | None = None,
    ladder: pd.DataFrame | None = None,
    trend_window: int = 20,
) -> pd.DataFrame:
    """Descriptor episode (docs/11 §6) — moi thanh phan chi dung du lieu <= t.

    shocks : cot `LEVEL`, `INNOVATION`, `JUMP`, va (tuy chon) `ACT`/`THREAT`.
    macro  : cot `vix`/`dxy`/`oil` (mac hoac return) — dung cho percentile/trend.
    ladder : cot `state`/`days_in_state` tu `econometrics.ladder`.

    ⚠️ z-score va percentile o day dung EXPANDING (chi qua khu), khong phai
    toan mau. Chuan hoa bang mean/std toan mau la ro ri: descriptor cua nam 1990
    se chua thong tin cua 2026 va neighbor "giong nhau" thanh giong theo tuong lai.
    """
    out = pd.DataFrame(index=shocks.index)

    def _z(s: pd.Series) -> pd.Series:
        exp = s.expanding(min_periods=60)
        return (s - exp.mean()) / exp.std()

    for col in ("LEVEL", "INNOVATION"):
        if col in shocks.columns:
            out[f"z_{col.lower()}"] = _z(shocks[col])
    if "JUMP" in shocks.columns:
        out["jump"] = shocks["JUMP"]
    if {"ACT", "THREAT"} <= set(shocks.columns):
        # Ti le ACT/THREAT: +eps tranh chia 0; log de doi xung quanh 1.
        out["act_threat_log_ratio"] = np.log(
            (shocks["ACT"] + 1e-6) / (shocks["THREAT"] + 1e-6))

    if macro is not None:
        if "vix" in macro.columns:
            out["vix_pct"] = macro["vix"].expanding(min_periods=60).apply(
                lambda x: float((x[:-1] < x[-1]).mean()) if len(x) > 1 else 0.0,
                raw=True)
        for col in ("dxy", "oil"):
            if col in macro.columns:
                out[f"{col}_trend"] = macro[col].rolling(trend_window).sum()

    if ladder is not None:
        if "state" in ladder.columns:
            out["ladder_state"] = ladder["state"].astype(float)
        if "days_in_state" in ladder.columns:
            out["days_in_state"] = ladder["days_in_state"].astype(float)

    out["regime"] = regime_flag(out.index)
    return out


@dataclass(frozen=True)
class Neighbour:
    """Mot tien le — LUON hien thi duoc (rang buoc 3)."""
    date: pd.Timestamp
    similarity: float
    outcome: float


@dataclass(frozen=True)
class AnalogueResult:
    """Ket qua truy hoi. `dispersed=True` -> IQR doi dau, khong ket luan."""
    as_of: pd.Timestamp
    horizon: int
    outcome_name: str
    n: int
    median: float
    q25: float
    q75: float
    share_same_sign: float
    dispersed: bool
    neighbours: list[Neighbour] = field(default_factory=list)
    claim: str = "association"

    def episode_table(self) -> pd.DataFrame:
        """Danh sach episode — rang buoc 3: nguoi dung bam xem duoc."""
        return pd.DataFrame(
            [{"date": nb.date, "similarity": nb.similarity, "outcome": nb.outcome}
             for nb in self.neighbours])


def _cosine(query: np.ndarray, mat: np.ndarray) -> np.ndarray:
    qn = np.linalg.norm(query)
    mn = np.linalg.norm(mat, axis=1)
    ok = (mn > 0) & np.isfinite(mn)
    sims = np.full(len(mat), -np.inf)
    if qn == 0:
        return sims
    sims[ok] = (mat[ok] @ query) / (mn[ok] * qn)
    return sims


def find_analogues(
    descriptor: pd.DataFrame,
    outcome: pd.Series,
    as_of: pd.Timestamp,
    horizon: int,
    k: int = DEFAULT_K,
    exclude_days: int = DEFAULT_EXCLUDE_DAYS,
    min_neighbours: int = MIN_NEIGHBOURS,
    outcome_name: str = "outcome",
) -> AnalogueResult:
    """k-NN cosine tren descriptor chuan hoa -> phan phoi outcome h buoc sau.

    Bon rang buoc cua docs/11 §6 deu cung o day:
      - ung vien PHAI co `available_at <= as_of` (chi lay index < as_of) VA phai
        da quan sat duoc ket cuc (index + horizon <= as_of) — neu khong thi
        "tien le" cua ta chua xay ra xong, tuc dung tuong lai lam qua khu;
      - loai ±`exclude_days` quanh as_of (chong trung episode);
      - n < min_neighbours -> raise InsufficientAnalogues (im lang, khong ha nguong);
      - IQR doi dau -> `dispersed=True`.

    outcome: chuoi ket cuc theo cung index; gia tri tai t+horizon.
    """
    as_of = pd.Timestamp(as_of)
    if as_of not in descriptor.index:
        raise KeyError(f"as_of={as_of.date()} khong co trong descriptor.")

    desc = descriptor.dropna()
    if as_of not in desc.index:
        raise InsufficientAnalogues(
            f"Descriptor tai {as_of.date()} con NaN (chua du warm-up) — khong "
            "truy hoi duoc. Im lang thay vi dien khuyet.")

    # Ket cuc h buoc sau, gan vao thoi diem GOC cua episode.
    fut = outcome.shift(-horizon)

    # Ung vien: TRUOC as_of, ngoai cua so loai tru, VA da biet ket cuc.
    cutoff = as_of - pd.Timedelta(days=exclude_days)
    cand = desc.index[(desc.index < cutoff)]
    # Ket cuc phai da quan sat duoc TINH DEN as_of.
    observed = fut.reindex(cand).notna()
    horizon_ok = pd.DatetimeIndex(cand) <= as_of
    cand = cand[observed.to_numpy() & horizon_ok]
    if len(cand) < min_neighbours:
        raise InsufficientAnalogues(
            f"Chỉ có {len(cand)} ứng viên hợp lệ trước {as_of.date()} "
            f"(cần ≥{min_neighbours}). KHÔNG xuất phần bối cảnh (docs/11 §6, cổng "
            "P3) — hạ ngưỡng để có số là biến 'không biết' thành 'biết mơ hồ'.",
            n_found=len(cand), n_required=min_neighbours)

    # Chuan hoa bang thong ke cua UNG VIEN (chi qua khu) — khong dung toan mau.
    sub = desc.loc[cand]
    mu, sd = sub.mean(), sub.std().replace(0.0, 1.0)
    mat = ((sub - mu) / sd).to_numpy(dtype=float)
    query = ((desc.loc[as_of] - mu) / sd).to_numpy(dtype=float)

    sims = _cosine(query, mat)
    take = min(k, len(cand))
    order = np.argsort(sims)[::-1][:take]
    picked = [Neighbour(date=cand[i], similarity=float(sims[i]),
                        outcome=float(fut.loc[cand[i]])) for i in order
              if np.isfinite(sims[i])]
    if len(picked) < min_neighbours:
        raise InsufficientAnalogues(
            f"Chỉ {len(picked)} láng giềng có similarity hợp lệ (cần "
            f"≥{min_neighbours}).", n_found=len(picked), n_required=min_neighbours)

    vals = np.array([nb.outcome for nb in picked], dtype=float)
    q25, med, q75 = (float(np.quantile(vals, q)) for q in (0.25, 0.50, 0.75))
    same_sign = float(np.mean(np.sign(vals) == np.sign(med))) if med != 0 else 0.0
    return AnalogueResult(
        as_of=as_of, horizon=horizon, outcome_name=outcome_name, n=len(picked),
        median=med, q25=q25, q75=q75, share_same_sign=same_sign,
        dispersed=bool(q25 < 0 < q75), neighbours=picked)


def describe(result: AnalogueResult) -> str:
    """Cau van cho Model Brief — sinh tu KET QUA, khong phai tu LLM.

    IQR doi dau -> noi thang "phan tan, khong ket luan" thay vi dua trung vi ra
    mot minh (rang buoc 2). Trung vi cua mot phan phoi bac ngang 0 la con so dung
    ve so hoc va sai ve thong diep.
    """
    if result.dispersed:
        return (f"{result.outcome_name}: {result.n} tiền lệ, IQR "
                f"[{result.q25:+.3f}, {result.q75:+.3f}] **đổi dấu** — phân tán, "
                f"không kết luận. (claim: {result.claim})")
    return (f"{result.outcome_name}: {result.n} tiền lệ, trung vị {result.median:+.3f} "
            f"(IQR [{result.q25:+.3f}, {result.q75:+.3f}]), "
            f"{result.share_same_sign * 100:.0f}% cùng dấu. "
            f"(claim: {result.claim})")


def batch_analogues(
    descriptor: pd.DataFrame,
    outcomes: pd.DataFrame,
    as_of: pd.Timestamp,
    horizons: Iterable[int],
    names: Sequence[str] | None = None,
    **kwargs,
) -> tuple[list[AnalogueResult], list[dict]]:
    """Chay nhieu (outcome, horizon). Tra (ket qua, danh sach bi bo qua).

    O nao khong du tien le thi vao `skipped` KEM LY DO — bien mat im lang la cach
    de nhat de mot brief trong rong trong ma trong co day du.

    `skipped` la dict CO CAU TRUC {outcome, horizon, n_found, n_required}, khong
    phai chuoi van xuoi: so nam trong chuoi thi Guard P1 o tang 4 khong doi chieu
    duoc voi payload va se chan ca brief. Composer tu dat cau tu cac truong nay.
    """
    names = list(names) if names is not None else list(outcomes.columns)
    results: list[AnalogueResult] = []
    skipped: list[dict] = []
    for name in names:
        for h in horizons:
            try:
                results.append(find_analogues(
                    descriptor, outcomes[name], as_of, h,
                    outcome_name=name, **kwargs))
            except InsufficientAnalogues as e:
                skipped.append({"outcome": name, "horizon": int(h),
                                "n_found": e.n_found, "n_required": e.n_required})
    return results, skipped
