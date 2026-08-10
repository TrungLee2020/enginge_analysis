"""policy_shock.py — cu soc chinh sach tien te My tu cua so cong bo FOMC. 🔬 research

VI SAO MODULE NAY CAN CO TRONG DU AN GPR:
    Bang γ tang 2 uoc luong "cu soc GPR -> vi mo toan cau". Nhung tin Fed CUNG
    day dung nhung bien do (lai suat, DXY, VIX, gia dau). Neu mot thang co ca cu
    soc GPR lan cong bo FOMC ma khong tach ra, he so γ HUT luon phan do Fed gay
    ra. Battery hien tai (EPU) kiem soat BAT DINH chinh sach, KHONG kiem soat
    CU SOC chinh sach — hai thu khac nhau.
    Nen day khong phai module rieng le: no la bien kiem soat con thieu cua γ.

CACH DO — va vi sao KHONG dung LLM cho phan nay:
    Cu soc chinh sach My do duoc TRUC TIEP tu phan ung gia tai san quanh cong bo
    (Kuttner 2001; Gurkaynak-Sack-Swanson 2005; Nakamura-Steinsson 2018). Gia
    phai sinh da chua ky vong thi truong, nen phan thay doi NGAY quanh cong bo
    la phan BAT NGO — dung dinh nghia cu soc.
    Cham "giong dieu" bang LLM roi suy ra do lon cu soc la thay mot phep do truc
    tiep bang mot proxy nhieu hon (CLAUDE.md #2).
    LLM VAN CO CHO, nhung o chieu khac: cac chieu ma gia KHONG dinh gia rieng ra
    duoc (ngon ngu forward guidance, bat dong trong bieu quyet, do bat dinh cua
    chinh cau chu). Do la viec sau, khong phai viec nay.

GIOI HAN PHAI DOC — ban nay la proxy NGAY, khong phai intraday:
    Chuan vang la cua so 30 phut quanh 14:00 ET; o day dung thay doi ca NGAY cua
    lai suat 2 nam. Ngay do con chua tin khac (so lieu vi mo, tin dia chinh tri)
    nen phep do NHIEU HON chuan vang. Do duoc muc nhiem: |Δ2y| ngay FOMC =
    1.50x ngay thuong, phuong sai 2.01x (do that 2026-08-09, 193 ngay FOMC
    2003-2026) — tin hieu that nhung khong sach.
    Chuoi intraday da publish (Bauer-Swanson 2023; Bu-Rogers-Wu 2021) sach hon;
    dung duoc chung thi NEN dung. Ban nay de chay duoc ngay voi du lieu da co.

    ⚠️ Vi la proxy ngay, dung goi ket qua la "cu soc chinh sach" khi bao cao ma
    goi "policy-window surprise (daily proxy)". Tran claim: `measurement`.
"""
from __future__ import annotations

import pandas as pd

# Lai suat dung lam thuoc do. 2 nam la chuan cua van lieu: du nhay voi duong lai
# suat chinh sach ky vong, it nhieu ky han dai hon 10 nam.
DEFAULT_YIELD_SERIES = "DGS2"


def event_days(published_at, tz: str = "America/New_York") -> pd.DatetimeIndex:
    """Timestamp cong bo (UTC) -> NGAY GIAO DICH My cua cong bo do.

    Doi ve gio New York TRUOC khi lay ngay: cong bo 14:00 ET = 18:00/19:00 UTC,
    nen lay ngay theo UTC van dung o day, nhung se SAI voi bat ky nguon nao cong
    bo sau 19:00 ET. Quy doi tuong minh de khong phu thuoc vao may man do.
    """
    ts = pd.DatetimeIndex(pd.to_datetime(list(published_at), utc=True))
    return pd.DatetimeIndex(sorted(set(ts.tz_convert(tz).normalize().tz_localize(None))))


def policy_surprise(yields: pd.Series, events: pd.DatetimeIndex,
                    fill_non_event: float | None = 0.0) -> pd.Series:
    """Thay doi lai suat trong NGAY cong bo = do bat ngo cua cong bo do.

    `fill_non_event=0.0`: ngay khong hop -> 0, tuc "khong co cong bo nao" chu
    KHONG phai thieu du lieu. Dat None neu muon NaN de phan biet ro hai truong
    hop trong hoi quy.

    ⚠️ CHI dien 0 TRONG pham vi co su kien (tu su kien dau den su kien cuoi).
    Ngoai pham vi do -> NaN. Ly do: neu ta chua thu thap duoc ngay cong bo cua
    2000-2002 thi dien 0 cho ca giai doan do la NOI DOI — bao "khong co cong bo"
    trong khi thuc te co 8 cuoc hop moi nam. Bien kiem soat mang gia tri sai se
    lam he so cua bien CHINH lech ma khong co dau hieu gi. NaN thi complete-case
    cat mau va nguoi doc NHIN THAY chi phi do.

    Ngay cong bo ma khong co gia (nghi le/thieu du lieu) bi BO — khong noi suy.
    """
    y = pd.Series(yields).dropna()
    y.index = pd.DatetimeIndex(pd.to_datetime(y.index)).tz_localize(None)
    d = y.diff().dropna()
    hit = d.reindex(events).dropna()
    if fill_non_event is None:
        return hit.rename("policy_surprise").sort_index()
    if hit.empty:
        raise ValueError(
            "Khong ngay su kien nao khop chuoi gia — kiem lai `events`. "
            "Tra ve toan 0 se la mot chuoi 'khong co cu soc nao' hoan toan bia.")
    out = pd.Series(fill_non_event, index=d.index, dtype=float)
    out.loc[hit.index] = hit.to_numpy()
    out.loc[(out.index < hit.index.min()) | (out.index > hit.index.max())] = float("nan")
    return out.rename("policy_surprise").sort_index()


def to_monthly(surprise: pd.Series, how: str = "sum") -> pd.DataFrame:
    """Gop ve THANG cho panel tang 2 (grid dau thang that, khong forward-fill #10).

    `sum`  : tong bat ngo trong thang — dung khi coi tac dong cong don. Mac dinh.
    `absmax`: cu soc DON le lon nhat (giu dau) — dung khi quan tam su kien lon.
    Tra ca hai cot + `n_events` de nguoi dung chon, khong ep mot cach doc.
    """
    if how not in ("sum", "absmax"):
        raise ValueError(f"how phai la 'sum'|'absmax', nhan {how!r}")
    s = surprise.dropna()
    s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
    grp = s.groupby(s.index.to_period("M").to_timestamp())
    out = pd.DataFrame({
        "mp_surprise_sum": grp.sum(),
        "mp_surprise_absmax": grp.apply(
            lambda x: x.loc[x.abs().idxmax()] if len(x) else 0.0),
        "mp_n_events": grp.apply(lambda x: int((x != 0).sum())),
    })
    out["mp_surprise"] = (out["mp_surprise_sum"] if how == "sum"
                          else out["mp_surprise_absmax"])
    return out.sort_index()


def contamination_ratio(surprise_all_days: pd.Series,
                        events: pd.DatetimeIndex) -> dict[str, float]:
    """Do do "sach" cua proxy ngay: bien dong ngay FOMC vs ngay thuong.

    Ty le ~1 nghia la ngay cong bo KHONG khac ngay thuong — luc do phep do gan
    nhu chi la nhieu thi truong, va dung no lam bien kiem soat se khong giup gi.
    Do that 2026-08-09: |Δ| 1.50x, phuong sai 2.01x tren 193 ngay FOMC.
    """
    d = pd.Series(surprise_all_days).dropna()
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).tz_localize(None)
    on = d.reindex(events).dropna()
    off = d.drop(on.index, errors="ignore")
    if on.empty or off.empty:
        raise ValueError("Khong du ngay de so — kiem lai `events` co khop index khong.")
    return {
        "n_events": int(len(on)),
        "n_other": int(len(off)),
        "abs_ratio": float(on.abs().mean() / off.abs().mean()),
        "var_ratio": float(on.var() / off.var()),
    }
