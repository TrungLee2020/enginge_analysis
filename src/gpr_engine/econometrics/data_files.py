"""data_files.py — nap du lieu OFFLINE (file + FRED) cho research cascade. 🔬

Day la ban song song file-based cua dataset.load_global_macro (vốn doc tu
PostgreSQL). G2a la research offline (docs/05), khong bat buoc co PG — module
nay doc GPR daily tu data/*.xls va keo Oil/DXY/VIX/US10Y tu FRED, cache lai CSV
de chay lai khong can mang.

Transform van dung dataset.transform_global_macro / log1p_gpr — KHONG lap lai
quy uoc bien doi (docs/07 §0). Chi khac nguon I/O.

Khong dung trong production. Production di qua ext_series (dataset.load_*).
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from ..ingest.gpr_daily import PUBLISH_LAG_DAYS as GPR_DAILY_PUBLISH_LAG_DAYS
from ..ingest.gpr_daily import SERIES as GPR_DAILY_SERIES
from ..ingest.market_data import FRED_MAP
from .dataset import dlog, fill_weekend, log1p_gpr, transform_global_macro

DEFAULT_GPR_DAILY = "data/data_gpr_daily_recent.xls"
DEFAULT_CACHE_DIR = "data/cache"

# Cac macro dua vao tang 2 mac dinh — DU 4 KENH global.
#   - dxy dung chuoi NOI DAI (load_dxy_spliced): DTWEXM (major, 1973->2019) noi
#     DTWEXBGS (broad, 2006->) o cap return, phu 1990+ (overlap corr Δln=0.926).
#     Nho vay dxy khong con cat mau nhu ban broad-only 2006+.
CORE_MACRO = ["oil", "dxy", "vix", "us10y"]


# ---------------------------------------------------------------------------
# GPR daily tu file
# ---------------------------------------------------------------------------
def load_gpr_daily(path: str = DEFAULT_GPR_DAILY) -> pd.DataFrame:
    """Doc GPRD/GPRD_ACT/GPRD_THREAT tu file -> wide, index=date (DatetimeIndex).

    Dung dung parser cua ingest.gpr_daily (guard cot thieu). Gia tri THO,
    chua transform.
    """
    df = pd.read_excel(path, sheet_name="Sheet1", header=0)
    missing = [c for c in [*GPR_DAILY_SERIES, "date"] if c not in df.columns]
    if missing:
        raise ValueError(
            f"File thieu cot bat buoc: {missing}. Cot hien co: {list(df.columns)}")
    df = df[["date", *GPR_DAILY_SERIES]].dropna(subset=["date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def transform_gpr_shocks(gpr_wide: pd.DataFrame, method: str = "innovation") -> pd.DataFrame:
    """Bien doi shock GPR daily cho hoi quy tang 2. Giu ten cot goc.

    method:
      - "innovation" (G2.0, docs/07v2 §2.0): shock = LEVEL − Ê_{t-1}[LEVEL], AR(p)
        rolling one-step (p chon bang BIC tren dev window). Day la SHOCK HOP LE cho
        hoi quy tang 2 (CLAUDE.md #9). Cot giu ten goc (GPRD -> GPRD la innovation).
      - "zscore" (LEVEL, doi chung): chuan hoa (x-mean)/std. GPRD ~ 10..370, γ doc la
        "phan ung / 1 do lech chuan". La LEVEL -> run_tier2 tu danh dau INELIGIBLE (#9).
      - "log1p": LEVEL = log(1+GPR), chi dung lam doi chung khi goi truc tiep.
        Innovation cung xay tren LEVEL log1p theo contract docs/07 §0; JUMP tinh
        rieng tren raw rolling de giu thong tin spike/duoi.
    """
    if method == "innovation":
        # innovation() log1p GPR thanh LEVEL roi tru persistent; ap tung cot, order/BIC.
        from .shocks import innovation
        return gpr_wide.apply(lambda col: innovation(col))
    if method == "log1p":
        return gpr_wide.apply(log1p_gpr)
    if method == "zscore":
        return (gpr_wide - gpr_wide.mean()) / gpr_wide.std()
    raise ValueError(
        f"method khong ho tro: {method!r} (dung 'innovation' | 'zscore' | 'log1p')")


def align_daily_gpr_to_information_time(
    gpr: pd.DataFrame,
    decision_days: Iterable[pd.Timestamp],
    publish_lag_days: int = GPR_DAILY_PUBLISH_LAG_DAYS,
) -> pd.DataFrame:
    """Gan GPR vao phien DA BIET du lieu, khong vao ngay bao chi duoc dem.

    GPR cua ngay D duoc publish som nhat o D+publish_lag_days. Moi phien quyet
    dinh nhan trung binh cac gia tri moi biet tu sau phien truoc; vi vay tin
    Thu Bay/Chu Nhat khong bi loai ma di vao phien tiep theo.
    """
    days = pd.DatetimeIndex(pd.to_datetime(list(decision_days))).sort_values().unique()
    known = gpr.copy()
    known.index = pd.to_datetime(known.index) + pd.Timedelta(days=publish_lag_days)
    return pd.DataFrame(
        {col: fill_weekend(known[col], days) for col in known.columns},
        index=days,
    )


def align_monthly_gpr_to_information_time(
    obj: pd.Series | pd.DataFrame,
) -> pd.Series | pd.DataFrame:
    """Gan gia tri thang M vao bucket quyet dinh M+1.

    GPR monthly tong hop ca thang M va chi publish sau khi M ket thuc. Track
    monthly khong bieu dien duoc gio/ngay +5, nen bucket som nhat hop le la M+1;
    caller realtime van phai ap dung available_at chinh xac.
    """
    out = obj.copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)) + pd.offsets.MonthBegin(1)
    return out


# ---------------------------------------------------------------------------
# Macro tu FRED (co cache)
# ---------------------------------------------------------------------------
def _cache_path(cache_dir: str) -> Path:
    return Path(cache_dir) / "global_macro_raw.csv"


def load_global_macro_fred(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """Keo Oil(BRENT)/DXY/VIX/US10Y tu FRED (raw, chua transform), co cache CSV.

    refresh=False va cache ton tai -> doc cache (khong goi mang).
    Tra ve wide raw: cot BRENT/DXY/VIX/US10Y, index=date.
    """
    cache = _cache_path(cache_dir)
    if cache.exists() and not refresh:
        raw = pd.read_csv(cache, parse_dates=["date"]).set_index("date").sort_index()
        return raw

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    cols = {}
    for sid, code in FRED_MAP.items():
        s = pdr.DataReader(code, "fred", start, end)[code]
        cols[sid] = s
    raw = pd.DataFrame(cols)
    raw.index.name = "date"
    raw = raw.sort_index()

    cache.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(cache)
    return raw


# FRED code cho DXY nối dài. DTWEXBGS chi 2006+; DTWEXM (major currencies)
# 1973 -> 2019-12 (FRED ngung cap nhat). Noi o CAP RETURN (Δln): broad uu tien
# khi co, fallback major. Overlap 2006-2019 corr(Δln)=0.926 -> splice hop le.
FRED_DXY_BROAD = "DTWEXBGS"
FRED_DXY_MAJOR = "DTWEXM"


def _dxy_cache(cache_dir: str) -> Path:
    return Path(cache_dir) / "dxy_spliced_raw.csv"


def splice_dxy_returns(broad: pd.Series, major: pd.Series) -> pd.Series:
    """Ghep Δln DXY: broad uu tien, fallback major. PURE (test khong can mang).

    broad/major la MUC (level) tho. Ghep o cap return vi hai ro tien khac muc.
    """
    r_broad = np.log(broad.dropna()).diff()
    r_major = np.log(major.dropna()).diff()
    idx = r_broad.index.union(r_major.index)
    dxy = r_broad.reindex(idx)
    dxy[dxy.isna()] = r_major.reindex(idx)[dxy.isna()]  # fallback major
    dxy = dxy.dropna().rename("dxy")
    dxy.index.name = "date"
    return dxy


def load_dxy_spliced(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.Series:
    """Δln DXY noi dai (major<->broad) — Series ten 'dxy', index=date.

    Tra ve TRUC TIEP log-return (da transform), vi hai ro tien khac muc nen khong
    the ghep muc; ghep return moi hop ly. broad uu tien, fallback major.
    """
    cache = _dxy_cache(cache_dir)
    if cache.exists() and not refresh:
        s = pd.read_csv(cache, parse_dates=["date"]).set_index("date")["dxy"]
        return s.sort_index()

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    broad = pdr.DataReader(FRED_DXY_BROAD, "fred", start, end)[FRED_DXY_BROAD]
    major = pdr.DataReader(FRED_DXY_MAJOR, "fred", start, end)[FRED_DXY_MAJOR]
    dxy = splice_dxy_returns(broad, major)

    cache.parent.mkdir(parents=True, exist_ok=True)
    dxy.to_frame().to_csv(cache)
    return dxy


def load_macro_transformed(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    dxy_spliced: bool = True,
) -> pd.DataFrame:
    """FRED raw -> {oil, dxy, vix, us10y} da transform (dataset.transform_global_macro).

    dxy_spliced=True: thay cot dxy bang chuoi noi dai major<->broad (1985+ thay vi
    chi 2006+). False: giu dxy = Δln DTWEXBGS (chi 2006+).
    """
    raw = load_global_macro_fred(start, end, cache_dir, refresh)
    out = transform_global_macro(raw)
    if dxy_spliced:
        out["dxy"] = load_dxy_spliced(start, end, cache_dir, refresh).reindex(out.index)
    return out


# ---------------------------------------------------------------------------
# Panel hop nhat cho tang 2
# ---------------------------------------------------------------------------
def build_tier2_panel(
    gpr_path: str = DEFAULT_GPR_DAILY,
    start: str = "1990-01-02",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    macro_vars: Iterable[str] = CORE_MACRO,
    shock_method: str = "innovation",
    ffill_limit: int = 3,
) -> pd.DataFrame:
    """Panel san sang cho estimate_tier2 tren cac phien macro cung quan sat.

    Dung giao cac ngay macro THUC SU co du lieu, khong forward-fill return/difference
    qua ngay nghi (lam vay se tao quan sat gia). GPR ngay D duoc can theo
    available_at D+1; cac gia tri moi biet giua hai phien duoc trung binh vao phien
    tiep theo, nen tin cuoi tuan khong bi mat.

    Params
    ------
    macro_vars : cac kenh macro dua vao (mac dinh CORE_MACRO = du 4 kenh; dxy da noi dai).
    shock_method : "innovation" (mac dinh hop le) | "zscore"/"log1p" (LEVEL doi chung).
    ffill_limit : giu de tuong thich API; macro transformed KHONG con duoc ffill.
    """
    gpr_raw = load_gpr_daily(gpr_path)
    gpr = transform_gpr_shocks(gpr_raw, method=shock_method)
    macro = load_macro_transformed(start, end, cache_dir, refresh)

    cols = [c for c in macro_vars if c in macro.columns]
    macro = macro[cols]

    # `ffill_limit` la tham so legacy. Khong ffill oil/dxy returns hay yield diff:
    # lap lai gia tri cu qua holiday se tao mot quan sat thi truong khong ton tai.
    _ = ffill_limit
    macro = macro.sort_index().loc[start:end] if end else macro.sort_index().loc[start:]
    macro_g = macro.dropna()
    decision_days = macro_g.index
    gpr_g = align_daily_gpr_to_information_time(gpr, decision_days)

    panel = macro_g.join(gpr_g, how="inner").sort_index()
    # Complete-case 1 lan -> moi horizon khong thay doi mau vi NaN rai rac.
    return panel.dropna()


# ---------------------------------------------------------------------------
# Track MONTHLY (docs/10 F3, docs/11 E3) — GPR global + GPRC_VNM, #10 no-ffill
# ---------------------------------------------------------------------------
DEFAULT_GPR_MONTHLY = "data/data_gpr_export_202607.xls"


def load_gpr_monthly(path: str = DEFAULT_GPR_MONTHLY) -> pd.DataFrame:
    """Doc GPR (global monthly) + GPRC_VNM tu file monthly -> wide, index=dau thang.

    Gia tri THO, chua transform. Guard cot GPRC_VNM (tranh nham vintage 39 nuoc).
    """
    df = pd.read_excel(path, sheet_name="Sheet1", header=0)
    if "GPRC_VNM" not in df.columns:
        raise ValueError(
            "File monthly thieu GPRC_VNM — co the la vintage cu 39 nuoc historical-only.")
    keep = ["month", "GPR", "GPRC_VNM"]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise ValueError(f"File monthly thieu cot: {missing}")
    out = df[keep].copy()
    out["month"] = pd.to_datetime(out["month"])
    return out.set_index("month").sort_index()


# Cước vận tải biển (docs/11 §5.3) — PPI deep sea freight transportation, FRED.
# Phủ 1990+ monthly (đủ mẫu). Điểm nghẽn Hormuz/Malacca không nằm trong 4 kênh
# Oil/DXY/VIX/US10Y; Malacca là cửa ngõ thương mại VN → biến generic nhưng nước
# xuất khẩu châu Á nhạy hơn. Là CHỈ SỐ GIÁ monthly → Δln.
#
# ⚠️ CẢNH BÁO DIỄN GIẢI (bắt buộc đọc trước khi dùng hệ số freight):
# PCU483111483111 là PPI Mỹ cho vận tải biển viễn dương — khảo sát, hàng tháng,
# DÍNH (sticky), là giá doanh nghiệp Mỹ thu. Nó ĐO TRUYỀN DẪN CHI PHÍ vận tải vào
# giá sản xuất, KHÔNG đo gián đoạn điểm nghẽn (Hormuz/Malacca) — một chỉ số khảo
# sát dính sẽ LÀM MƯỢT đúng cái đuôi sắc mà giả thuyết tắc nghẽn cần thấy. Chọn
# series này vì phủ 1990+ (spot rate như Baltic Dry mẫu ngắn hơn nhiều); đánh đổi
# hợp lý nhưng KHÔNG được đọc hệ số freight như "đo tắc nghẽn". Nếu có chuỗi cước
# GIAO NGAY (Baltic Dry / container spot) → đưa vào làm ROBUSTNESS mẫu ngắn, đó mới
# là thước đo khớp giả thuyết Hormuz/Malacca.
FRED_FREIGHT = "PCU483111483111"


def transform_freight(raw: pd.Series) -> pd.Series:
    """Freight PPI (mức giá) -> Δln (log-return), giữ tên 'freight'.

    ⚠️ Đo TRUYỀN DẪN CHI PHÍ vận tải vào giá sản xuất (PPI khảo sát dính), KHÔNG
    đo tắc nghẽn điểm nghẽn Hormuz/Malacca. Xem cảnh báo ở FRED_FREIGHT. Mọi report
    dùng cột này phải ghi lại cách diễn giải này.
    """
    return dlog(raw).rename("freight")


def load_freight_monthly(
    start: str = "1990-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.Series:
    """Freight PPI THÔ (mức giá) monthly từ FRED, cache CSV. Chưa transform.

    Trả Series 'freight' index=đầu tháng. build_monthly_panel gọi transform_freight.
    """
    cache = Path(cache_dir) / "freight_raw.csv"
    if cache.exists() and not refresh:
        s = pd.read_csv(cache, parse_dates=["date"]).set_index("date")["freight"]
        return s.sort_index()

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    s = pdr.DataReader(FRED_FREIGHT, "fred", start, end)[FRED_FREIGHT]
    s = s.rename("freight")
    s.index.name = "date"
    s = s.resample("MS").last().sort_index()

    cache.parent.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_csv(cache)
    return s


def freight_vintage(cache_dir: str = DEFAULT_CACHE_DIR) -> str | None:
    """Hash sha256[:12] của cache freight (vintage FRED). None nếu chưa cache.

    #4 (docs review): data_version hiện chỉ hash GPRD → hai lần chạy với vintage
    FRED freight KHÁC NHAU (PPI có hiệu chỉnh hồi tố!) mang cùng data_version. Report
    nào dùng freight PHẢI ghi riêng `freight_vintage` này vào metadata để audit được.
    """
    import hashlib
    cache = Path(cache_dir) / "freight_raw.csv"
    if not cache.exists():
        return None
    return hashlib.sha256(cache.read_bytes()).hexdigest()[:12]


def load_macro_monthly(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    how: str = "last",
) -> pd.DataFrame:
    """Macro tai chinh {oil, dxy, vix, us10y} da transform, TONG HOP ve THANG.

    Tai su dung load_macro_transformed (daily) roi resample MS. `how`:
      - "last": gia tri cuoi thang (level-like: vix).
      - Returns (oil/dxy: Δln) va diff (us10y) da la thay doi -> lay TONG trong thang
        de giu y nghia "thay doi ca thang" (sum cua daily Δln = Δln thang).
    Don gian & hop ly cho SCA freq_outcome=monthly; E3 co the tinh chinh sau.
    """
    daily = load_macro_transformed(start, end, cache_dir, refresh)
    # oil/dxy/us10y la thay doi (return/diff) -> sum trong thang; vix la level -> last.
    agg = {c: ("sum" if c in {"oil", "dxy", "us10y"} else "last")
           for c in daily.columns}
    monthly = daily.resample("MS").agg(agg)
    return monthly


def build_monthly_panel(
    gpr_path: str = DEFAULT_GPR_MONTHLY,
    start: str = "1990-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    macro_vars: Iterable[str] = CORE_MACRO,
    min_train: int = 60,
    max_order: int = 5,
    extra_monthly: pd.DataFrame | None = None,
    freight: bool = False,
) -> pd.DataFrame:
    """Panel MONTHLY cho track monthly (docs/10 F3): GPR global + GPRC_VNM⊥ + macro.

    Nguyen tac #10: KHONG forward-fill xuong daily. Grid la dau thang that.

    Cot ra:
      - `GPR_INNOV`            : β global-direct (GPR global monthly, innovation)
      - `GPRC_VNM_ORTH_INNOV`  : λ domestic-direct — GPRC_VNM da ORTHOGONALIZE khoi
                                 GPR global (bo phan chung) roi innovation. KHONG
                                 lo GPRC_VNM tho (#9).
      - macro_vars (oil/dxy/vix/us10y) tong hop ve thang.
      - freight=True: them cot `freight` (Δln PPI deep sea freight, docs/11 §5.3) —
        kenh vat ly Hormuz/Malacca ngoai 4 kenh tai chinh. Mac dinh False de khong
        pha panel cu.
      - extra_monthly: outcome vi mo thuc (IP/CPI...) neu E3 cung cap — join theo thang.

    Innovation monthly: AR(p) rolling, p chon BIC/dev-window (giong daily, nhung
    min_train nho hon vi mau thang it). Complete-case 1 lan.
    """
    from .shocks import innovation
    from .tier3_country import orthogonalize

    gpr_m = load_gpr_monthly(gpr_path)                       # GPR, GPRC_VNM (tho)
    gpr_m = gpr_m.loc[start:end] if end else gpr_m.loc[start:]

    # GPR global -> innovation (β). log1p ap trong innovation(is_level=False).
    gpr_innov = innovation(gpr_m["GPR"], min_train=min_train,
                           max_order=max_order).rename("GPR_INNOV")

    # GPRC_VNM: log1p -> orthogonalize khoi GPR global (level) -> innovation (λ).
    #   Phan RIENG cua VN (⊥ global) moi la domestic-direct (docs/07v2 §4.1, #8).
    lg = pd.DataFrame({
        "vnm": log1p_gpr(gpr_m["GPRC_VNM"]),
        "gpr": log1p_gpr(gpr_m["GPR"]),
    }).dropna()
    vnm_orth = orthogonalize(lg, target="vnm", on=["gpr"])   # residual = VN rieng
    vnm_orth_innov = innovation(vnm_orth, is_level=True, min_train=min_train,
                                max_order=max_order).rename("GPRC_VNM_ORTH_INNOV")

    # Gia tri cua thang M chi duoc dung trong bucket M+1 (sau khi thang M ket
    # thuc). Khong join GPR thang M voi outcome cung thang M nhu the da biet tu
    # dau thang.
    gpr_innov = align_monthly_gpr_to_information_time(gpr_innov)
    vnm_orth_innov = align_monthly_gpr_to_information_time(vnm_orth_innov)

    macro = load_macro_monthly(start, end, cache_dir, refresh)
    cols = [c for c in macro_vars if c in macro.columns]
    macro = macro[cols]

    frames = [macro, gpr_innov, vnm_orth_innov]
    if freight:
        fr_raw = load_freight_monthly(start, end, cache_dir, refresh)
        frames.append(transform_freight(fr_raw))
    if extra_monthly is not None:
        frames.append(extra_monthly)
    panel = frames[0].to_frame() if isinstance(frames[0], pd.Series) else frames[0]
    for f in frames[1:]:
        panel = panel.join(f, how="inner")
    return panel.sort_index().dropna()
