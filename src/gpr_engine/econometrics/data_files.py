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
import hashlib
import re
import warnings
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from ..ingest.ai_gpr import AI_GPR_COLUMNS
from ..ingest.gpr_daily import PUBLISH_LAG_DAYS as GPR_DAILY_PUBLISH_LAG_DAYS
from ..ingest.gpr_daily import SERIES as GPR_DAILY_SERIES
from ..ingest.market_data import FRED_MAP
from .dataset import dlog, fill_weekend, log1p_gpr, transform_global_macro

DEFAULT_GPR_DAILY = "data/data_gpr_daily_recent.xls"
DEFAULT_CACHE_DIR = "data/cache"

# Thu muc con cua data/ bi BO QUA khi do tim (cache la thu muc GHI, khong phai
# nguon; do vao day se nham file cache voi file nguon).
_RESOLVE_SKIP_DIRS = {"cache"}
_RESOLVE_MAX_DEPTH = 3
# Duoi " (1)", " (2)"... trinh duyet them khi tai trung ten — bo truoc khi so.
_COPY_SUFFIX_RE = re.compile(r"\s*\(\d+\)$")
# Ky tu duoc coi la RANH GIOI token khi so hai ten. Bat buoc co ranh gioi de
# "data_gpr" khong khop "data_gpr_daily_recent" — hai file khac nhau that.
_STEM_BOUNDARY = ("_", "-", " ", ".")


def _stems_match(candidate_stem: str, target_stem: str) -> bool:
    """Hai ten file co phai cung MOT nguon du lieu, khac cach dat ten?

    Doi xung hai chieu, vi ca hai huong deu gap that:
      - `data_gpr_daily_recent (1)` vs `data_gpr_daily_recent` — ban sao trinh
        duyet, ung vien DAI hon.
      - `data_gpr_export (1)` vs `data_gpr_export_202607` — DEFAULT_* mang hau
        to vintage ma file tai ve khong co, ung vien NGAN hon.

    Phan noi them phai bat dau bang mot ky tu ranh gioi (`_`, `-`, ` `, `.`),
    nen `data_gpr_exp` KHONG khop `data_gpr_export` (cat giua token). Mot tien
    to DUNG ranh gioi thi VAN khop (`data_gpr` ~ `data_gpr_daily_recent`) —
    day la co y, vi hai file cung goc thuong chi khac hau to vintage; truong
    hop nhap nhang that su duoc chan o tang tren: nhieu ket qua -> raise.
    """
    a = _COPY_SUFFIX_RE.sub("", candidate_stem).strip()
    b = _COPY_SUFFIX_RE.sub("", target_stem).strip()
    if a == b:
        return True
    long_, short = (a, b) if len(a) > len(b) else (b, a)
    return long_.startswith(short) and long_[len(short)] in _STEM_BOUNDARY


def resolve_data_path(path: str | Path, *, search_root: str | Path = "data") -> Path:
    """Tim file du lieu khi layout thu muc THAT khac `DEFAULT_*`.

    Ly do ton tai: file GPR/AI-GPR la file TAI TAY, nguoi van hanh tha vao
    `data/` theo cach cua ho — thuc te da gap `data/AI-GPRs/ai_gpr_data_daily.csv`
    va `data/GPR index/data_gpr_daily_recent (1).xls` trong khi `DEFAULT_*` tro
    thang `data/<ten>`. Truoc thay doi nay, KHONG script nao chay duoc ngay sau
    khi clone + tha file (tests/test_report_guard_p1.py fail dung vi the).

    Thu tu do tim, DUNG lai o buoc dau tien co ket qua:
      1. Chinh `path` (duong dan tuyet doi/tuong doi nguoi goi dua vao).
      2. Cung TEN FILE, o bat ky thu muc con nao cua `search_root` (bo qua
         `cache/`), sau toi da `_RESOLVE_MAX_DEPTH` cap.
      3. Cung phan mo rong + ten file la TIEN TO — bat cac ban sao trinh duyet
         dat ten kieu `data_gpr_daily_recent (1).xls`.

    KHONG tim thay -> tra ve `Path(path)` nguyen ban, de cac guard `.exists()`
    san co in ra thong bao huong dan tai file (chung noi ro hon loi cua ham nay).

    NHIEU ket qua o cung mot buoc -> `FileNotFoundError` liet ke het. Tu chon
    mot ban trong im lang la chon vintage du lieu ho nguoi dung — vi pham #7
    (ghim vintage) va lam report mat tai lap khi hai ban khac noi dung.
    """
    p = Path(path)
    if p.exists():
        return p

    root = Path(search_root)
    if not root.is_dir():
        return p

    def _candidates(depth_limit: int) -> list[Path]:
        out: list[Path] = []
        for child in root.rglob("*"):
            if not child.is_file():
                continue
            rel = child.relative_to(root)
            if len(rel.parts) > depth_limit:
                continue
            if any(part in _RESOLVE_SKIP_DIRS for part in rel.parts[:-1]):
                continue
            out.append(child)
        return out

    files = _candidates(_RESOLVE_MAX_DEPTH)
    exact = sorted(f for f in files if f.name == p.name)
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise FileNotFoundError(
            f"{path}: tim thay {len(exact)} file cung ten trong {root}/ — "
            f"{[str(f) for f in exact]}. Chi ro duong dan (tham so `path`) "
            "thay vi de ham tu chon: chon ho la chon vintage du lieu ho ban.")

    prefixed = sorted(f for f in files
                      if f.suffix == p.suffix and _stems_match(f.stem, p.stem))
    if len(prefixed) == 1:
        warnings.warn(
            f"{path} khong co; dung {prefixed[0]} (khop tien to ten file). "
            "Doi ten file ve dung chuan hoac truyen `path` tuong minh de "
            "khong phu thuoc vao suy doan nay.", stacklevel=2)
        return prefixed[0]
    if len(prefixed) > 1:
        raise FileNotFoundError(
            f"{path}: khong co file dung ten, va {len(prefixed)} file khop tien "
            f"to — {[str(f) for f in prefixed]}. Chi ro `path`.")

    return p

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
    df = pd.read_excel(resolve_data_path(path), sheet_name="Sheet1", header=0)
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
    aggregation: str | Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Gan GPR vao phien DA BIET du lieu, khong vao ngay bao chi duoc dem.

    GPR cua ngay D duoc publish som nhat o D+publish_lag_days. Moi phien quyet
    dinh nhan cac gia tri moi biet tu sau phien truoc. ``aggregation`` co the la
    mot toan tu chung hoac mapping theo cot. Contract da dang ky: mean cho
    LEVEL/INNOVATION, max cho JUMP. LEVEL+JUMP phai aggregate hai thanh phan
    rieng roi moi cong bang ``align_daily_shock_measures_to_information_time``.
    """
    if aggregation is None:
        raise ValueError(
            "Phai khai bao aggregation theo shock: mean cho LEVEL/INNOVATION, "
            "max cho JUMP")
    days = pd.DatetimeIndex(pd.to_datetime(list(decision_days))).sort_values().unique()
    known = gpr.copy()
    known.index = pd.to_datetime(known.index) + pd.Timedelta(days=publish_lag_days)

    def reducer(col: str) -> str:
        if isinstance(aggregation, str):
            return aggregation
        if col not in aggregation:
            raise KeyError(f"Thieu aggregation cho cot {col!r}")
        return aggregation[col]

    return pd.DataFrame({
        col: fill_weekend(known[col], days, aggregation=reducer(col))
        for col in known.columns
    }, index=days)


def align_daily_shock_measures_to_information_time(
    measures: pd.DataFrame,
    decision_days: Iterable[pd.Timestamp],
    publish_lag_days: int = GPR_DAILY_PUBLISH_LAG_DAYS,
) -> pd.DataFrame:
    """Align bo shock daily bang toan tu dung cho tung thanh phan.

    LEVEL, PERSISTENT va INNOV dung mean; JUMP dung max. Cot LEVEL_PLUS_JUMP
    khong duoc aggregate truc tiep: ham tinh lai no tu LEVEL da mean va JUMP da
    max, tranh lam mut spike cuoi tuan.
    """
    composite_suffix = "_LEVEL_PLUS_JUMP"
    base = measures.loc[:, [c for c in measures.columns
                            if not c.endswith(composite_suffix)]]
    aggregation = {
        col: ("max" if col.endswith("_JUMP") else "mean")
        for col in base.columns
    }
    aligned = align_daily_gpr_to_information_time(
        base,
        decision_days,
        publish_lag_days=publish_lag_days,
        aggregation=aggregation,
    )

    prefixes = {
        col[:-len(composite_suffix)]
        for col in measures.columns if col.endswith(composite_suffix)
    }
    for prefix in prefixes:
        level_col = f"{prefix}_LEVEL"
        jump_col = f"{prefix}_JUMP"
        if level_col not in aligned or jump_col not in aligned:
            raise KeyError(
                f"Can {level_col!r} va {jump_col!r} de tao {prefix + composite_suffix!r}")
        aligned[f"{prefix}{composite_suffix}"] = (
            aligned[level_col] + aligned[jump_col])
    aligned.attrs.update(measures.attrs)
    aligned.attrs["weekend_aggregation"] = {
        "LEVEL": "mean", "INNOV": "mean", "JUMP": "max",
        "LEVEL_PLUS_JUMP": "mean(LEVEL)+max(JUMP)",
    }
    return aligned


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
    ffill_limit: int | None = None,
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
    ffill_limit : tham so legacy, khong con tac dung. Truyen gia tri se phat
                  ``DeprecationWarning``; hay bo tham so khoi caller.
    """
    gpr_raw = load_gpr_daily(gpr_path)
    gpr = transform_gpr_shocks(gpr_raw, method=shock_method)
    macro = load_macro_transformed(start, end, cache_dir, refresh)

    cols = [c for c in macro_vars if c in macro.columns]
    macro = macro[cols]

    # Khong ffill oil/dxy returns hay yield diff: lap lai gia tri cu qua holiday
    # se tao mot quan sat thi truong khong ton tai.
    if ffill_limit is not None:
        warnings.warn(
            "ffill_limit khong con tac dung; build_tier2_panel chi dung ngay macro "
            "thuc su quan sat. Hay bo tham so nay.",
            DeprecationWarning,
            stacklevel=2,
        )
    macro = macro.sort_index().loc[start:end] if end else macro.sort_index().loc[start:]
    macro_g = macro.dropna()
    decision_days = macro_g.index
    # transform_gpr_shocks o day chi tra LEVEL/INNOVATION co dau; reducer la mean.
    # JUMP/composite cua lưới phai di qua helper chuyen dung o tren.
    gpr_g = align_daily_gpr_to_information_time(
        gpr, decision_days, aggregation="mean")

    panel = macro_g.join(gpr_g, how="inner").sort_index()
    # Complete-case 1 lan -> moi horizon khong thay doi mau vi NaN rai rac.
    return panel.dropna()


# ---------------------------------------------------------------------------
# Track MONTHLY (docs/10 F3, docs/11 E3) — GPR global + GPRC_VNM, #10 no-ffill
# ---------------------------------------------------------------------------
# Vintage 202608 (tai 2026-08-08, cung `data/GPR index/`). Doi tu 202607 sau khi
# KIEM: hai file `data_gpr_export (1).xls` va `data_gpr_export_202608.xls` giong
# nhau TUNG O tren ca 112 cot so (0 o lech, phu 1900-01 -> 2026-07), nen doi
# default KHONG lam so lieu report doi — day la lam ro TEN, khong phai doi du
# lieu. Neu lan sau nap file co so KHAC, phai bump `--data-version` khi ingest
# (#4/#7), dung de trung version cu.
DEFAULT_GPR_MONTHLY = "data/data_gpr_export_202608.xls"


DEFAULT_COUNTRY = "VNM"

# Nguon chuoi GPR TOAN CAU cho panel thang (P1.3). Them nguon moi phai them ca
# nhanh xu ly trong build_monthly_panel — de o day de loi la ValueError ro rang
# chu khong phai KeyError giua chung.
SHOCK_SOURCES = ("gpr_ci", "ai_gpr")


# Tach ACT/THREAT o track THANG (docs/14 §2 muc 1a "tach ACT/THREAT").
# Ten cot trong file monthly KHAC file daily: monthly la GPRA/GPRT, daily la
# GPRD_ACT/GPRD_THREAT. Anh xa ve ten CHUNG de runner khong phai biet tan suat.
GPR_MONTHLY_COMPONENTS = {"GPRA": "GPR_ACT", "GPRT": "GPR_THREAT"}


def load_gpr_monthly(
    path: str = DEFAULT_GPR_MONTHLY,
    country: str = DEFAULT_COUNTRY,
    components: bool = False,
) -> pd.DataFrame:
    """Doc GPR (global monthly) + GPRC_<country> tu file monthly -> wide, index=dau thang.

    Gia tri THO, chua transform. Guard cot GPRC_<country> (tranh nham vintage 39 nuoc).

    ``country`` la ma ISO-3 trong file 44 nuoc (VNM, POL, CHL, THA, IDN, PHL...).
    Tham so hoa nay la dieu kien cua Phase 1b docs/14 §2: cascade tang 3 chay thu
    tren mot NUOC PILOT ngoai lo trinh ban, de khong dot out-of-sample cua VN/TH/ID/PH.
    Mac dinh VNM giu nguyen hanh vi cu.

    ``components=True`` them GPR_ACT/GPR_THREAT (doi ten tu GPRA/GPRT trong file)
    cho viec tach kenh tho giai doan 1 (docs/11 §5.3) — khong can chan B.
    """
    df = pd.read_excel(resolve_data_path(path), sheet_name="Sheet1", header=0)
    col = f"GPRC_{country}"
    if col not in df.columns:
        available = sorted(c for c in df.columns if c.startswith("GPRC_"))
        raise ValueError(
            f"File monthly thieu {col} — co the la vintage cu 39 nuoc historical-only, "
            f"hoac ma nuoc sai. Cac GPRC_* co trong file: {available}")
    keep = ["month", "GPR", col]
    if components:
        keep += list(GPR_MONTHLY_COMPONENTS)
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise ValueError(f"File monthly thieu cot: {missing}")
    out = df[keep].copy()
    out["month"] = pd.to_datetime(out["month"])
    out = out.set_index("month").sort_index()
    return out.rename(columns=GPR_MONTHLY_COMPONENTS) if components else out


# JUMP o track THANG: cua so rolling KHAC daily mot cach co chu dich.
# Daily dung 250 phien (~1 nam). Chuyen thang khong phai la 12 — uoc luong phan
# vi q95 tren 12 quan sat la vo nghia (q95 cua 12 diem = gan nhu max). Quantile
# can co mau; 120 thang (10 nam) cho ~6 quan sat tren nguong, du de nguong on
# dinh ma van thich nghi voi regime. Ghi vao metadata report, khong giau.
MONTHLY_JUMP_WINDOW = 120
MONTHLY_JUMP_MIN_PERIODS = 60


def build_monthly_shock_axis(
    raw: pd.Series,
    prefix: str,
    min_train: int = 60,
    max_order: int = 5,
    jump_window: int = MONTHLY_JUMP_WINDOW,
    jump_q: float = 0.95,
    jump_min_periods: int = MONTHLY_JUMP_MIN_PERIODS,
) -> pd.DataFrame:
    """Ba thuoc do shock cua TRUC BAO CAO (g0 §7.1 = A) o tan suat THANG.

    Tra ve cot `<prefix>_LEVEL`, `<prefix>_INNOVATION`, `<prefix>_LEVEL_PLUS_JUMP`.

    Contract docs/07v2 §0 — sai la hong uoc luong:
      LEVEL           = log1p(GPR)
      INNOVATION      = LEVEL − E[LEVEL | qua khu]   (AR(p) rolling, no leakage)
      LEVEL+JUMP      = LEVEL + JUMP, voi JUMP tinh tren chuoi THO rolling de giu
                        thong tin duoi. TUYET DOI khong phai INNOVATION + JUMP
                        (bug lich su E1b, xem registry KĐ-E1b.artifact_formula).
    """
    from .shocks import innovation, jump, level_plus_jump

    level = log1p_gpr(raw).rename(f"{prefix}_LEVEL")
    innov = innovation(raw, min_train=min_train,
                       max_order=max_order).rename(f"{prefix}_INNOVATION")
    j = jump(raw, window=jump_window, q=jump_q, min_periods=jump_min_periods)
    lpj = level_plus_jump(level, j, name=f"{prefix}_LEVEL_PLUS_JUMP")
    return pd.concat([level, innov, lpj], axis=1)


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


# ---------------------------------------------------------------------------
# AI-GPR (Iacoviello & Tong 2026) — docs/16 §1. FILE TẢI TAY, không tự fetch.
# ---------------------------------------------------------------------------
# Nguồn: matteoiacoviello.com/ai_gpr.html — trang cập nhật ĐỊNH KỲ.
#
# ⚠️ Vì sao KHÔNG tự tải trong code (docs/16 §1, nguyên tắc #4): trang cập nhật
# định kỳ, và nếu chỉ có một file "latest" bị ghi đè mỗi kỳ thì mọi report chạy
# trên nó KHÔNG tái lập được — `data_version` mất nghĩa. Tải tay + ghim vintage
# bằng hash file là cách duy nhất giữ được tái lập, giống `wui_global.csv` và
# `gold_events.csv`. Fetch ngầm mỗi lần chạy = số trong report cũ âm thầm hết đúng.
#
# ✅ SCHEMA ĐÃ XÁC MINH tren file that (2026-08-05, tai tu
# matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv, vintage
# 13b8e8b48d41, 1960-01-01 .. 2026-07-31, 24319 hang). Ten file THAT khac ten
# gia dinh cu (`ai_gpr_daily.csv` -> `ai_gpr_data_daily.csv`), cot ngay la
# `Date` (hoa D) khong phai `date`, va BA cot AIGPR/AIGPRT/AIGPRA gia dinh
# truoc day SAI HOAN TOAN ten that (GPR_AI/THREATS_GPR_AI/ACTS_GPR_AI).
#
# ⚠️ Phat hien quan trong so voi docs/16: ban DAILY DA CO san 8 cot GPR_OIL
# theo VUNG (MiddleEast/Russia/USA/Venezuela/Africa/Americas/Asia/NorthSea) —
# docs/16 §1 doc mo ta trang web thi tuong day chi co o ban THANG, sai. Kiem
# tren du lieu that quan trong hon doc mo ta trang.
#
# ⚠️ Con lai CHUA xac minh (can AI_GPR_PAPER.pdf, KHONG doan):
#   - `GPR_AER` — nghia cot chua ro (co the lien quan American Economic
#     Review, noi paper GPR goc dang — nhung day la DOAN, khong dua vao).
#   - 8 cot GPR_OIL_<vung> KHONG cong don ve dung GPR_OIL (da kiem tay tren
#     nhieu hang — vd hang 2026-07-31: tong 8 vung = 908.44 nhung
#     GPR_OIL=628.92) — co the trung lap vung hoac GPR_OIL tinh rieng, chua
#     ro co che, dung suy dien tong hop khi chua doc paper.
# ✅ Ban MONTHLY xac minh 2026-08-05, tai tu
# matteoiacoviello.com/ai_gpr_files/ai_gpr_data_monthly.csv, vintage
# 92b9ba3bd38f, 1960-01-01 .. 2026-07-01, 799 hang. CUNG SCHEMA voi ban daily
# (cung 15 cot, chi khac tan suat) — dung chung AI_GPR_COLUMNS, load qua
# `load_ai_gpr_monthly()`. Day KHONG PHAI file "Country Decompositions" (
# ai_gpr_country_monthly.csv / ai_gpr_bilateral_monthly.csv /
# ai_gpr_country_eventtype_monthly.csv) — 3 file do CHUA tai, CHUA co loader.
DEFAULT_AI_GPR_MONTHLY = "data/ai_gpr_data_monthly.csv"
DEFAULT_AI_GPR_DAILY = "data/ai_gpr_data_daily.csv"

# AI_GPR_COLUMNS (ten that trong file -> ten dung trong repo, CA daily lan
# monthly) chuyen ve `ingest/ai_gpr.py` lam nguon CHINH THUC (2026-08-05, cung
# lan them ingest script Postgres) — import lai o day, GIONG HET pattern
# GPR_DAILY_SERIES/PUBLISH_LAG_DAYS cua ingest/gpr_daily.py. Ly do: ingest la
# duong PRODUCTION ghi vao ext_series, phai la nguon ten series_id chuan; day
# la duong RESEARCH offline, dung lai chu khong dinh nghia lai (tranh drift
# hai ban ten cot). Doi ten cot phai sua o ingest/ai_gpr.py, KHONG sua o day.

_AI_GPR_MISSING_MSG = (
    "Không tìm thấy {path}. AI-GPR là file TẢI TAY (docs/16 §1):\n"
    "  1. Tải từ matteoiacoviello.com/ai_gpr.html\n"
    "  2. Lưu vào {path}\n"
    "  3. Chạy `describe_ai_gpr_file()` để ĐỐI CHIẾU tên cột thật với "
    "AI_GPR_COLUMNS — schema hiện tại CHƯA xác minh trên file thật\n"
    "Cố ý không tự tải: trang cập nhật định kỳ, fetch ngầm làm report cũ mất "
    "tái lập (nguyên tắc #4)."
)


def describe_ai_gpr_file(path: str = DEFAULT_AI_GPR_DAILY) -> dict:
    """Đọc file AI-GPR THÔ và mô tả nó — dùng để đối chiếu schema lần tải đầu.

    Trả `{columns, n_rows, date_col_guess, vintage}`. KHÔNG transform gì: mục
    đích là xem file thật có gì trước khi tin `AI_GPR_COLUMNS`.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    df = pd.read_csv(p, nrows=200)
    date_guess = [c for c in df.columns
                  if str(c).strip().lower() in {"date", "day", "time", "month"}]
    return {
        "columns": list(df.columns),
        "n_rows_preview": len(df),
        "date_col_guess": date_guess,
        "vintage": ai_gpr_vintage(path),
        "expected_mapping": dict(AI_GPR_COLUMNS),
    }


def ai_gpr_vintage(path: str = DEFAULT_AI_GPR_DAILY) -> str | None:
    """Hash file AI-GPR = vintage. Vào metadata MỌI report chạy trên AI-GPR.

    Trang cập nhật định kỳ nên hai bản tải cách nhau vài tháng là hai dữ liệu
    khác nhau; không ghim cái này thì `data_version` của report không phân biệt
    được chúng.
    """
    p = resolve_data_path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def _load_ai_gpr(
    path: str,
    date_col: str,
    columns: Mapping[str, str] | None,
    index_name: str,
) -> pd.DataFrame:
    """Loi chung cho ban daily va monthly — CUNG mot schema (AI_GPR_COLUMNS),
    chi khac tan suat/path. Khong xuat cong khai — dung qua
    `load_ai_gpr_daily`/`load_ai_gpr_monthly`.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    mapping = dict(AI_GPR_COLUMNS if columns is None else columns)
    df = pd.read_csv(p)
    if date_col not in df.columns:
        raise ValueError(
            f"Không có cột ngày {date_col!r} trong {path}. Cột thực tế: "
            f"{list(df.columns)}. Chạy describe_ai_gpr_file() rồi truyền date_col.")
    missing = [c for c in mapping if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path} thiếu cột {missing} (AI_GPR_COLUMNS chưa xác minh trên file "
            f"thật — docs/16 §1). Cột thực tế: {list(df.columns)}. Đối chiếu bằng "
            "describe_ai_gpr_file() rồi sửa AI_GPR_COLUMNS hoặc truyền `columns`.")
    out = df[[date_col, *mapping]].rename(columns=mapping)
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.set_index(date_col).sort_index()
    out.index.name = index_name
    out.attrs["vintage"] = ai_gpr_vintage(path)
    out.attrs["source"] = "AI-GPR (Iacoviello & Tong 2026), docs/16 §1"
    return out


def load_ai_gpr_daily(
    path: str = DEFAULT_AI_GPR_DAILY,
    date_col: str = "Date",
    columns: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """AI-GPR daily THÔ -> wide, index=ngày.

    File that (xac minh 2026-08-05) KHONG chi co headline+threats/acts nhu
    docs/16 §1 mo ta ban dau — con co GPR_AER, GPR_OIL/GPR_NONOIL, VA 8 cot
    GPR_OIL theo VUNG (energy channel routing co san o muc DAILY, khong phai
    chi THANG nhu doc mo ta trang web). Xem canh bao ben canh AI_GPR_COLUMNS.

    Thay thế vai trò của `load_gpr_daily` cho các run trên AI-GPR (docs/16 §1).
    GPRD gốc **giữ nguyên làm đối chứng** — E0 đã PASS trên nó và tương quan hai
    chỉ số chỉ 0.69, đủ khác để so sánh có nghĩa.

    ⚠️ Trước khi dùng lần đầu: chạy `describe_ai_gpr_file()` và đối chiếu tên cột.
    Hàm này raise nếu cột khai trong `columns` không có trong file — KHÔNG lặng
    lẽ bỏ qua cột thiếu, vì thiếu threats/acts thì mọi phân tách ACT/THREAT sau
    đó âm thầm chạy trên dữ liệu rỗng.

    ⚠️ AI-GPR KHÔNG cùng hình dạng với GPRD (docs/16 §5): mượt hơn, dai hơn
    (tự tương quan 90 ngày 0.73 vs 0.62), đuôi phải mỏng hơn, không có ngày nào
    bằng 0. Ngưỡng JUMP q95/q99 rolling **phải hiệu chuẩn lại** — không bê thẳng
    tham số đã dùng cho GPRD sang.
    """
    return _load_ai_gpr(path, date_col, columns, index_name="date")


def load_ai_gpr_monthly(
    path: str = DEFAULT_AI_GPR_MONTHLY,
    date_col: str = "Date",
    columns: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """AI-GPR monthly THÔ -> wide, index=đầu tháng. CÙNG schema với bản daily
    (xác minh 2026-08-05, vintage `92b9ba3bd38f`) — chỉ khác tần suất, tái
    dùng `AI_GPR_COLUMNS`.

    ⚠️ KHÔNG PHẢI file "Country Decompositions" (`load_ai_gpr_eventtype_monthly`,
    `load_ai_gpr_country_eventtype_monthly`, `load_ai_gpr_bilateral_monthly`
    bên dưới) — đó là dữ liệu KHÁC (theo loại sự kiện/nước/cặp nước). File
    này chỉ là bản monthly của đúng chỉ số tổng hợp mà `load_ai_gpr_daily()`
    đọc ở mức ngày.

    Ghép vào `build_monthly_panel` theo đúng quy ước information-time
    (`align_monthly_gpr_to_information_time`) như GPR gốc — tháng M chỉ dùng
    được ở bucket M+1, KHÔNG join thẳng vào outcome cùng tháng (#9, #11).
    """
    return _load_ai_gpr(path, date_col, columns, index_name="month")


# ---------------------------------------------------------------------------
# AI-GPR "Country Decompositions" — docs/16 §1 v1.2/v1.3. BA file KHÁC chỉ số
# tổng hợp ở trên (theo loại sự kiện / nước+loại sự kiện / cặp nước có hướng).
# XÁC MINH 2026-08-05 trên file thật, tải tay (cùng nguyên tắc §1 phía trên).
# ⚠️ CHƯA có `ai_gpr_country_monthly.csv` (200 nước × 4 vai) — file thứ 4
# docs/16 §1 liệt kê, chưa tải, chưa xác minh, không có loader ở đây.
# ---------------------------------------------------------------------------
DEFAULT_AI_GPR_EVENTTYPE_MONTHLY = "data/ai_gpr_eventtype_monthly.csv"
DEFAULT_AI_GPR_COUNTRY_EVENTTYPE_MONTHLY = "data/ai_gpr_country_eventtype_monthly.csv"
DEFAULT_AI_GPR_BILATERAL_MONTHLY = "data/ai_gpr_bilateral_monthly.csv"

# 8 loại sự kiện (xác minh trên `ai_gpr_eventtype_monthly.csv`, vintage
# 2026-08-05) — CỘNG DỒN ĐÚNG về GPR_AI (kiểm tay: corr=0.9999999999976,
# lệch tuyệt đối tối đa 0.0002 trên toàn mẫu 799 hàng) — KHÁC hẳn 8 cột
# GPR_OIL_<vùng> ở `load_ai_gpr_daily/monthly` (KHÔNG cộng dồn về GPR_OIL —
# CƠ CHẾ ĐÃ XÁC MINH qua AI_GPR_PAPER.pdf, đọc 2026-08-05: prompt phân loại
# vùng cho phép chọn "one or more" vùng cho MỘT bài báo — bài nói về xung đột
# ảnh hưởng cả Middle East lẫn Russia được cộng vào CẢ HAI tổng vùng nhưng chỉ
# tính MỘT LẦN vào tổng GPR_OIL, nên tổng-các-vùng > GPR_OIL là kỳ vọng đúng,
# không phải lỗi dữ liệu. Paper cũng xác nhận: prompt định nghĩa **13** vùng
# gốc (Middle East/Russia/USA/Venezuela/North Africa/West Africa/Central Asia/
# North Sea/Canada/Mexico/Latin America/Southeast Asia/China) — khớp đúng
# "13 vùng" mà docs/16 v1.0 từng ghi; 8 cột trong file CSV công khai là bản
# GOM NHÓM (Africa=North+West Africa, Americas=Canada+Mexico+Latin America,
# Asia=Central Asia+Southeast Asia+China, 5 vùng còn lại giữ nguyên — khớp số
# 5+2+3+3=13 — suy luận từ tên cột, chưa thấy paper nói thẳng cách gộp).
#
# Taxonomy LOẠI SỰ KIỆN (military_conflict/diplomatic_tension/terrorism/
# civil_war/nuclear_threat/coup/sanctions/other) — paper định nghĩa nguyên
# văn (Appendix A.6, prompt phân loại sự kiện): mô tả BẢN CHẤT hành động địa
# chính trị, KHÔNG PHẢI 4 kênh truyền dẫn energy/trade/financial/military mà
# `gamma_lookup.py`/`vn_exposure.py` cần — hai trục này TRỰC GIAO theo đúng
# thiết kế của paper: định nghĩa "spillover" của paper liệt kê energy
# shock/trade disruption như VÍ DỤ CƠ CHẾ lan tỏa, không phải một loại sự
# kiện. Vì vậy KHÔNG có cách nào map 1-1 sạch — xem `EVENT_TYPE_TO_CHANNEL`
# (Ý NGHĨA đã ký `DEC-2026-08-05-event-type-channel`, chưa nối vào production
# nào) ngay dưới đây.
AI_GPR_EVENT_TYPES = (
    "military_conflict", "diplomatic_tension", "terrorism", "civil_war",
    "nuclear_threat", "coup", "sanctions", "other",
)

# Map 8 loại sự kiện -> 4 kênh truyền dẫn — Ý NGHĨA đã KÝ (2026-08-05,
# `DEC-2026-08-05-event-type-channel`, config/hypothesis_registry.yaml
# `decisions:`, khóa bằng test_event_type_channel_decision_matches_code).
# ⚠️ Chữ ký chỉ xác nhận Ý NGHĨA của mapping — CHƯA nối vào bất kỳ đường
# production nào (gamma_lookup.py vẫn chỉ dùng pooled/act/threat như cũ, đó
# là biến thể GPRD dùng làm shock, KHÔNG PHẢI trục 4 kênh này). Nối dây thật
# (nếu có) là quyết định kiến trúc/kỹ thuật RIÊNG, vẫn phải qua nguyên tắc #1
# (research trước khi vào service). Cùng tinh thần `CHANNEL_TO_TRANSMISSION`
# trong statement_scorer.py (chỉ điền cặp hiển nhiên, còn lại None).
#
# Lý do từng dòng:
#   military_conflict, civil_war, coup, nuclear_threat -> military: cả bốn
#     đều là hành động/đe dọa VŨ TRANG trực tiếp — khớp định nghĩa "military"
#     trong transmission-formulas.md §2 (xung đột vũ trang, triển khai quân).
#   sanctions -> financial: khớp định nghĩa "financial" trong
#     transmission-formulas.md §2 (trừng phạt tài chính, đóng băng tài sản) —
#     ĐÃ có tiền lệ y hệt trong statement_scorer.CHANNEL_TO_TRANSMISSION
#     (dù ở đó "sanction" từ chân B vẫn để None chờ chốt — ở đây chốt được vì
#     ngữ cảnh khác: đây là loại sự kiện độc lập, không phải nhãn LLM chấm tin).
#   terrorism, diplomatic_tension, other -> None: KHÔNG map. Terrorism có thể
#     đánh vào hạ tầng năng lượng (energy) hoặc gây risk-off chung (financial)
#     tùy mục tiêu — một nhãn không đủ phân biệt. Diplomatic tension là tiền
#     thân của MỌI kênh, không riêng kênh nào. "other" là catch-all, theo
#     định nghĩa không map được.
#
# ⚠️ QUAN TRỌNG NHẤT: taxonomy 8 loại KHÔNG có category "energy" hay "trade"
# — đây không phải khoảng trống ngẫu nhiên mà là hệ quả thiết kế (xem cảnh báo
# trên AI_GPR_EVENT_TYPES). Hai kênh đó PHẢI lấy từ nguồn khác, đã có sẵn
# trong repo, KHÔNG suy ra từ 8 loại sự kiện:
#   - energy: dùng trực tiếp `AIGPR_OIL`/`AIGPR_OIL_<vùng>` từ
#     `load_ai_gpr_daily/monthly()` — dữ liệu CHUYÊN BIỆT cho oil/energy,
#     không phải suy diễn từ event-type.
#   - trade: dùng `load_ai_gpr_bilateral_monthly()` — paper (Section 5.3,
#     6.x) VALIDATE trực tiếp chỉ số này bằng gravity equation, thấy GPR song
#     phương cao hơn đi cùng THƯƠNG MẠI song phương thấp hơn — đây là bằng
#     chứng thật cho việc bilateral index đo đúng kênh trade, không phải
#     suy diễn.
EVENT_TYPE_TO_CHANNEL: dict[str, str | None] = {
    "military_conflict": "military",
    "civil_war": "military",
    "coup": "military",
    "nuclear_threat": "military",
    "sanctions": "financial",
    "terrorism": None,
    "diplomatic_tension": None,
    "other": None,
}


def load_ai_gpr_eventtype_monthly(
    path: str = DEFAULT_AI_GPR_EVENTTYPE_MONTHLY,
    date_col: str = "Date",
) -> pd.DataFrame:
    """GPR toàn cầu theo 8 LOẠI SỰ KIỆN (không tách nước) -> wide, index=tháng.

    Xác minh 2026-08-05 trên file thật (1960-01-01..2026-07-01, 799 hàng).
    Cột: `AIGPR` (đối chiếu tổng) + 8 cột trong `AI_GPR_EVENT_TYPES`.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    df = pd.read_csv(p)
    need = [date_col, "GPR_AI", *AI_GPR_EVENT_TYPES]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path} thiếu cột {missing}. Cột thực tế: {list(df.columns)}. "
            "Chạy describe_ai_gpr_file() rồi đối chiếu AI_GPR_EVENT_TYPES.")
    out = df[need].rename(columns={date_col: "month", "GPR_AI": "AIGPR"})
    out["month"] = pd.to_datetime(out["month"])
    out = out.set_index("month").sort_index()
    out.attrs["vintage"] = ai_gpr_vintage(path)
    out.attrs["source"] = "AI-GPR (Iacoviello & Tong 2026), docs/16 §1"
    return out


def load_ai_gpr_country_eventtype_monthly(
    path: str = DEFAULT_AI_GPR_COUNTRY_EVENTTYPE_MONTHLY,
    date_col: str = "Date",
) -> pd.DataFrame:
    """GPR theo NƯỚC × LOẠI SỰ KIỆN THÔ -> wide, index=tháng.

    Xác minh 2026-08-05 (1960-01-01..2026-07-01, 799 hàng, 1602 cột =
    Date + GPR_AI + 200 nước × 8 loại sự kiện, tên cột `{Nước}_{loại}` —
    vd `Vietnam_military_conflict`; nước viết đầy đủ, có dấu cách với nước
    ghép ("Saudi Arabia")). KHÔNG rename/tách hết 1600 cột ở đây (nặng
    không cần thiết) — dùng `select_country_eventtype()` để lấy một nước.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    df = pd.read_csv(p)
    if date_col not in df.columns:
        raise ValueError(
            f"Không có cột ngày {date_col!r} trong {path}. Cột thực tế đầu "
            f"tiên: {list(df.columns)[:5]}...")
    df = df.rename(columns={date_col: "month"})
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month").sort_index()
    df.attrs["vintage"] = ai_gpr_vintage(path)
    df.attrs["source"] = "AI-GPR (Iacoviello & Tong 2026), docs/16 §1"
    return df


def select_country_eventtype(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Trích 8 cột loại sự kiện của MỘT nước từ
    `load_ai_gpr_country_eventtype_monthly()`, bỏ tiền tố tên nước.

    Raise nếu nước không có trong file (KHÔNG trả DataFrame rỗng) — tên nước
    sai chính tả mà lặng lẽ trả rỗng thì phân tích sau đó âm thầm chạy trên
    dữ liệu trống.
    """
    cols = {f"{country}_{et}": et for et in AI_GPR_EVENT_TYPES}
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"Không tìm thấy nước {country!r} (thiếu cột {missing}). Kiểm tra "
            "đúng chính tả/định dạng tên nước trong file gốc (vd 'Vietnam', "
            "'Saudi Arabia', 'South Korea').")
    return df[list(cols)].rename(columns=cols)


def load_ai_gpr_bilateral_monthly(
    path: str = DEFAULT_AI_GPR_BILATERAL_MONTHLY,
    date_col: str = "Date",
) -> pd.DataFrame:
    """GPR song phương CÓ HƯỚNG THÔ -> wide, index=tháng.

    Xác minh 2026-08-05 (1960-01-01..2026-07-01, 799 hàng, 1202 cột =
    Date + GPR_AI + 1.200 cặp nước, tên cột `{Actor}|{Target}` — CÓ HƯỚNG,
    vd cả `USA|Vietnam` lẫn `Vietnam|USA` đều tồn tại RIÊNG. KHÔNG rename hết
    1200 cột — dùng `select_bilateral_pair()` để lấy một cặp.

    ⚠️ Dấu `|` KHÁC quy ước `pair_key()` của `indices.s_gpr` (dùng `>`) —
    KHÔNG trộn lẫn hai định dạng; chuyển đổi tường minh ở nơi dùng nếu cần
    khớp với chuỗi S-GPR nội bộ.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    df = pd.read_csv(p)
    if date_col not in df.columns:
        raise ValueError(
            f"Không có cột ngày {date_col!r} trong {path}. Cột thực tế đầu "
            f"tiên: {list(df.columns)[:5]}...")
    df = df.rename(columns={date_col: "month"})
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month").sort_index()
    df.attrs["vintage"] = ai_gpr_vintage(path)
    df.attrs["source"] = "AI-GPR (Iacoviello & Tong 2026), docs/16 §1"
    return df


def select_bilateral_pair(df: pd.DataFrame, actor: str, target: str) -> pd.Series:
    """Trích MỘT cặp `actor|target` từ `load_ai_gpr_bilateral_monthly()`.

    Raise nếu cặp không có trong 1.200 cặp top — im lặng trả rỗng sẽ biến
    "không đủ dữ liệu cặp này" thành "GPR=0 suốt", hai ý nghĩa khác hẳn nhau.
    """
    col = f"{actor}|{target}"
    if col not in df.columns:
        raise KeyError(
            f"Không tìm thấy cặp {col!r} trong 1.200 cặp top. Kiểm chính tả "
            "tên nước, hoặc cặp này không đủ khối lượng để vào top 1.200.")
    return df[col].rename(col)


# File thứ 4 và cuối cùng trong danh sách "Country Decompositions" docs/16 §1 —
# xác minh 2026-08-05. `all` = tổng, `initiator`/`respondent`/`spillover` CỘNG
# DỒN ĐÚNG về `all` (kiểm tay trên Vietnam + USA, nhiều tháng: khớp tới 4 chữ
# số thập phân) — cùng kiểu cộng dồn sạch với `AI_GPR_EVENT_TYPES`, khác 8 cột
# oil-vùng không cộng dồn. Đây là file khớp THẲNG vào khung docs/16 §3
# ("VN gần như luôn spillover") — `select_country_role(df, "Vietnam")
# ["spillover"]` là chuỗi tháng đo đúng vai trò đó, không cần tự suy ra.
DEFAULT_AI_GPR_COUNTRY_ROLE_MONTHLY = "data/ai_gpr_country_monthly.csv"
AI_GPR_ROLES = ("all", "initiator", "respondent", "spillover")


def load_ai_gpr_country_monthly(
    path: str = DEFAULT_AI_GPR_COUNTRY_ROLE_MONTHLY,
    date_col: str = "Date",
) -> pd.DataFrame:
    """GPR theo NƯỚC × VAI TRÒ THÔ -> wide, index=tháng.

    Xác minh 2026-08-05 (1960-01-01..2026-07-01, 799 hàng, 802 cột =
    Date + GPR_AI + 200 nước × 4 vai, tên cột `{Nước}_{vai}` — vd
    `Vietnam_spillover`). KHÔNG rename hết 800 cột — dùng
    `select_country_role()` để lấy một nước.

    ⚠️ ĐỪNG nhầm với `load_ai_gpr_country_eventtype_monthly()` — cùng 200
    nước nhưng tách theo VAI TRÒ (all/initiator/respondent/spillover) ở đây,
    theo LOẠI SỰ KIỆN (8 category) ở kia — hai trục khác nhau, hai file khác
    nhau.
    """
    p = resolve_data_path(path)
    if not p.exists():
        raise FileNotFoundError(_AI_GPR_MISSING_MSG.format(path=path))
    df = pd.read_csv(p)
    if date_col not in df.columns:
        raise ValueError(
            f"Không có cột ngày {date_col!r} trong {path}. Cột thực tế đầu "
            f"tiên: {list(df.columns)[:5]}...")
    df = df.rename(columns={date_col: "month"})
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month").sort_index()
    df.attrs["vintage"] = ai_gpr_vintage(path)
    df.attrs["source"] = "AI-GPR (Iacoviello & Tong 2026), docs/16 §1"
    return df


def select_country_role(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Trích 4 cột vai trò (`AI_GPR_ROLES`) của MỘT nước từ
    `load_ai_gpr_country_monthly()`, bỏ tiền tố tên nước.

    Raise nếu nước không có trong file — cùng lý do với
    `select_country_eventtype`/`select_bilateral_pair`: không lặng lẽ trả rỗng.
    """
    cols = {f"{country}_{role}": role for role in AI_GPR_ROLES}
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"Không tìm thấy nước {country!r} (thiếu cột {missing}). Kiểm tra "
            "đúng chính tả/định dạng tên nước trong file gốc.")
    return df[list(cols)].rename(columns=cols)


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


def _cache_vintage(cache_dir: str, filename: str) -> str | None:
    """Hash sha256[:12] của một file cache. None nếu chưa cache.

    #4 (docs review): data_version hiện chỉ hash GPRD → hai lần chạy với vintage
    FRED KHÁC NHAU mang cùng data_version. Mọi chuỗi FRED CÓ HIỆU CHỈNH HỒI TỐ
    (PPI freight, INDPRO, CPI, EPU) phải ghi vintage riêng vào metadata report.
    """
    import hashlib
    cache = Path(cache_dir) / filename
    if not cache.exists():
        return None
    return hashlib.sha256(cache.read_bytes()).hexdigest()[:12]


def freight_vintage(cache_dir: str = DEFAULT_CACHE_DIR) -> str | None:
    """Vintage cache freight (PPI có hiệu chỉnh hồi tố). Xem `_cache_vintage`."""
    return _cache_vintage(cache_dir, "freight_raw.csv")


def _load_fred_group(
    codes: Mapping[str, str],
    cache_name: str,
    start: str,
    end: str | None,
    cache_dir: str,
    refresh: bool,
    resample: str | None = "MS",
) -> pd.DataFrame:
    """Kéo một nhóm series FRED -> wide THÔ (chưa transform), cache CSV.

    ``codes`` : {ten_cot: fred_code}. ``resample``: 'MS' lấy giá trị cuối tháng cho
    chuỗi tần suất cao hơn tháng; None giữ nguyên tần suất gốc.
    """
    cache = Path(cache_dir) / cache_name
    if cache.exists() and not refresh:
        return (pd.read_csv(cache, parse_dates=["date"])
                .set_index("date").sort_index())

    from pandas_datareader import data as pdr

    end = end or dt.date.today().isoformat()
    cols = {name: pdr.DataReader(code, "fred", start, end)[code]
            for name, code in codes.items()}
    raw = pd.DataFrame(cols).sort_index()
    raw.index.name = "date"
    if resample:
        raw = raw.resample(resample).last()

    cache.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(cache)
    return raw


# ---------------------------------------------------------------------------
# OUTCOME VĨ MÔ THỰC (SCA-01 report_axis_outcome.real_macro) — docs/14 §1.2
# ---------------------------------------------------------------------------
# Cascade tới giờ dừng ở oil/dxy/vix/us10y/freight — đó là KÊNH TRUYỀN DẪN, chưa
# phải vĩ mô. Sản phẩm "đánh giá xu hướng kinh tế vĩ mô" cần chính các biến này.
# Registry SCA-01 đã đăng ký real_macro=[IP, CPI, infl_expectation] nhưng chưa có
# loader; E0 tự kéo INDPRO trong script riêng. Đây là loader dùng chung, và nó
# TÁI SỬ DỤNG ĐÚNG transform mà E0 đã validate (100·Δln INDPRO) — không fork.
#
# ⚠️ HIỆU CHỈNH HỒI TỐ: INDPRO và CPIAUCSL đều được revise nhiều kỳ sau publish
# (INDPRO revise tới 5 năm). Bản kéo từ FRED là VINTAGE MỚI NHẤT, không phải cái
# người ra quyết định thấy lúc đó. Với ước lượng γ (mô tả truyền dẫn) điều này
# chấp nhận được; với backtest point-in-time thì KHÔNG — phải qua ALFRED vintage.
# Ghi `real_macro_vintage()` vào metadata mọi report dùng nhóm này.
FRED_REAL_MACRO = {
    "ip": "INDPRO",         # Industrial Production index, monthly SA
    "cpi": "CPIAUCSL",      # CPI-U all items, monthly SA
    "infl_exp": "MICH",     # Michigan survey, kỳ vọng lạm phát 1 năm (%/năm)
}


def load_real_macro_monthly(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """IP / CPI / kỳ vọng lạm phát THÔ (mức) monthly từ FRED, cache CSV."""
    return _load_fred_group(FRED_REAL_MACRO, "real_macro_raw.csv",
                            start, end, cache_dir, refresh)


def transform_real_macro(raw: pd.DataFrame) -> pd.DataFrame:
    """Mức -> biến đích của LP. Quy ước (docs/07 §0, nhất quán với E0):

    - ``ip``       : 100·Δln  → tăng trưởng sản xuất công nghiệp %/tháng. ĐÚNG
      transform E0 đã tái lập được C-I 2022 trên chính pipeline này (β=−0.37, h=2).
    - ``cpi``      : 100·Δln  → lạm phát %/tháng.
    - ``infl_exp`` : sai phân → THAY ĐỔI kỳ vọng lạm phát (điểm %). Là mức khảo sát
      dai dẳng nên xử như us10y (#9: mức không đọc được là phản ứng cú sốc).
    """
    out = pd.DataFrame(index=raw.index)
    if "ip" in raw:
        out["ip"] = 100.0 * dlog(raw["ip"])
    if "cpi" in raw:
        out["cpi"] = 100.0 * dlog(raw["cpi"])
    if "infl_exp" in raw:
        out["infl_exp"] = raw["infl_exp"].diff()
    return out


def real_macro_vintage(cache_dir: str = DEFAULT_CACHE_DIR) -> str | None:
    """Vintage cache real macro (INDPRO/CPI revise hồi tố). Xem `_cache_vintage`."""
    return _cache_vintage(cache_dir, "real_macro_raw.csv")


# ---------------------------------------------------------------------------
# BENCHMARK BATTERY (docs/14 §1.1 + §2 mục 1a bản b) — EPU / WUI
# ---------------------------------------------------------------------------
# Nguyên tắc #6 đo incremental IC; docs/14 nâng lên: hệ số GPR phải sống sót KHI
# CÓ MẶT các chỉ số bất định đã publish của đội khác. Không so với zero, so với
# state of the art. EPU=Baker-Bloom-Davis, WUI=Ahir-Bloom-Furceri.
#
# GPR và EPU/WUI cùng họ "chỉ số đếm tin" → dùng CHUNG quy ước log1p của GPR
# (dataset.log1p_gpr), không đặt quy ước riêng.
#
# ⚠️ CÁCH DÙNG: battery vào hồi quy như CONTROL, và phải ĐỒNG THƯỚC ĐO với shock —
# shock chạy LEVEL thì control là LEVEL; shock chạy INNOVATION thì control phải qua
# `shocks.innovation` cùng spec. So level-control với innovation-shock là khập
# khiễng và sẽ thổi phồng phần "riêng của GPR". Loader này trả LEVEL (log1p);
# việc khớp thước đo là của runner.
FRED_BENCHMARK = {
    "epu_us": "USEPUINDXM",      # US Economic Policy Uncertainty, monthly, 1985+
    "epu_global": "GEPUCURRENT",  # Global EPU (GDP-weighted, current prices), 1997+
}

# WUI không có trên FRED — tải tay từ worlduncertaintyindex.com, đặt vào đây với
# 2 cột: date (đầu tháng hoặc quý), wui. Cùng kiểu "dữ liệu người phải cung cấp"
# như data/gold_events.csv.
DEFAULT_WUI_PATH = "data/wui_global.csv"


def load_benchmark_monthly(
    start: str = "1985-01-01",
    end: str | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    wui_path: str | None = DEFAULT_WUI_PATH,
) -> pd.DataFrame:
    """Battery THÔ (mức chỉ số) monthly: epu_us, epu_global, + wui nếu có file.

    WUI thiếu file -> BỎ QUA im lặng nhưng cột vắng mặt; runner phải ghi vào report
    rằng battery chạy thiếu WUI. Không tự bịa chuỗi thay thế.
    """
    out = _load_fred_group(FRED_BENCHMARK, "benchmark_raw.csv",
                           start, end, cache_dir, refresh)
    if wui_path and Path(wui_path).exists():
        wui = pd.read_csv(wui_path, parse_dates=["date"]).set_index("date")["wui"]
        # WUI công bố theo QUÝ ở nhiều vintage; upsample về đầu tháng KHÔNG được
        # forward-fill (#10). Chỉ join đúng tháng có quan sát.
        out = out.join(wui.resample("MS").last(), how="outer").sort_index()
    return out


def transform_benchmark(raw: pd.DataFrame) -> pd.DataFrame:
    """Battery mức -> log1p (cùng quy ước GPR). Giữ tên cột."""
    return raw.apply(log1p_gpr)


def benchmark_vintage(cache_dir: str = DEFAULT_CACHE_DIR) -> str | None:
    """Vintage cache battery (EPU có revise khi thêm báo). Xem `_cache_vintage`."""
    return _cache_vintage(cache_dir, "benchmark_raw.csv")


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
    country: str = DEFAULT_COUNTRY,
    real_macro: bool = False,
    battery: bool = False,
    shock_axis: bool = False,
    components: bool = False,
    dual_component: bool = False,
    shock_source: str = "gpr_ci",
    ai_gpr_path: str = DEFAULT_AI_GPR_MONTHLY,
) -> pd.DataFrame:
    """Panel MONTHLY cho track monthly (docs/10 F3): GPR global + GPRC_<c>⊥ + macro.

    Nguyen tac #10: KHONG forward-fill xuong daily. Grid la dau thang that.

    Cot ra:
      - `GPR_INNOV`                : β global-direct (GPR global monthly, innovation)
      - `GPRC_<country>_ORTH_INNOV`: λ domestic-direct — GPRC_<country> da
                                 ORTHOGONALIZE khoi GPR global (bo phan chung) roi
                                 innovation. KHONG lo GPRC_<country> tho (#9).
      - macro_vars (oil/dxy/vix/us10y) tong hop ve thang.
      - freight=True: them cot `freight` (Δln PPI deep sea freight, docs/11 §5.3) —
        kenh vat ly Hormuz/Malacca ngoai 4 kenh tai chinh. Mac dinh False de khong
        pha panel cu.
      - real_macro=True: them `ip`/`cpi`/`infl_exp` (SCA-01 report_axis_outcome
        .real_macro) — OUTCOME vi mo THUC, cai ma san pham goi la "xu huong kinh te
        vi mo". Ghi `real_macro_vintage()` vao metadata report (revise hoi to).
      - battery=True: them `epu_us`/`epu_global` LEVEL log1p lam CONTROL benchmark
        (docs/14 §2 muc 1a ban b). Xem canh bao dong thuoc do o `FRED_BENCHMARK` —
        control phai cung thuoc do voi shock. ⚠️ `epu_global` chi tu 1997 nen
        complete-case se CAT PANEL ve 1997+ (mat ~7 nam so ban khong battery);
        chay ca hai ban a/b thi phai so tren CUNG MAU, khong so 1990+ voi 1997+.
        WUI KHONG vao day (quy, xem ghi chu trong than ham).
      - shock_axis=True: them `GPR_LEVEL`/`GPR_INNOVATION`/`GPR_LEVEL_PLUS_JUMP` —
        TRUC BAO CAO shock cua bang γ (g0 §7.1 = A, chot 2026-08-02). `GPR_INNOV`
        van giu (ban cu, KHONG doi ten) va bang `GPR_INNOVATION`.
      - components=True: them truc shock cho GPR_ACT/GPR_THREAT (tach kenh tho
        giai doan 1, docs/11 §5.3 — khong can chan B). Chi co tac dung khi
        shock_axis=True (VOI truc 3 thuoc do) hoac dual_component=True.
      - dual_component=True: them `GPR_ANTICIPATED`/`GPR_SURPRISE` — SPEC CHINH
        cua docs/17_master_plan.md §4.1 (spec kep, `DEC-2026-08-03-dual-component`).
        Hai cot cong lai bang DUNG Δ LEVEL. Voi components=True them ca cap
        cua GPR_ACT/GPR_THREAT (spec 4 regressor, §4.1).
        ⚠️ Dua CA HAI vao cung mot hoi quy — dung chon mot. Va bao cao dong gop
        phai CHUAN HOA (`shocks.standardized_contribution`): he so tho cua hai
        cot nay khong so duoc, Var(ANT)/Var(SUR) ~0.1.
      - extra_monthly: cot monthly khac do caller cung cap — join theo thang.

    `shock_source` — nguon chuoi GPR TOAN CAU (P1.3, docs/17_master_plan.md §6):
      - "gpr_ci"  (mac dinh): GPR goc Caldara-Iacoviello tu `gpr_path`. Ban cu,
        khong doi gi.
      - "ai_gpr": AI-GPR monthly tu `ai_gpr_path` (AIGPR/AIGPR_ACT/AIGPR_THREAT
        -> doi ten thanh GPR/GPR_ACT/GPR_THREAT de MOI cot phia sau giu nguyen
        ten). Dung de chay bang γ ban thu hai cua Phase 1a va do attenuation
        do sai so do.
        ⚠️ Cot nuoc `GPRC_<c>` VAN lay tu `gpr_path` (file C-I): AI-GPR tach
        nuoc nam o file RIENG (`ai_gpr_country_monthly.csv`) voi 4 vai tro, KHONG
        phai cung schema — tron hai thu do vao day se lam λ doi nghia trong im
        lang. Doi nguon λ la viec rieng, chua lam.
        ⚠️ Hai nguon co PHAN PHOI khac han (sd 47.6 vs 61.5, autocorr 0.580 vs
        0.754 tren mau chung 1985+ — `scripts/check_master_plan_claims.py`), nen
        nguong/phan vi hieu chuan tren ban nay KHONG dung cho ban kia.

    ⚠️ `country`: doi nuoc KHONG doi bat cu gi khac trong panel — tang 1-2 la ENGINE
    generic (#8), chi tang 3 co params rieng nuoc. Dung cho Phase 1b (nuoc pilot).

    Innovation monthly: AR(p) rolling, p chon BIC/dev-window (giong daily, nhung
    min_train nho hon vi mau thang it). Complete-case 1 lan.
    """
    from .shocks import delta_decomposition, innovation
    from .tier3_country import orthogonalize

    if shock_source not in SHOCK_SOURCES:
        raise ValueError(
            f"shock_source={shock_source!r} khong thuoc {SHOCK_SOURCES}.")

    gpr_m = load_gpr_monthly(gpr_path, country=country,
                             components=components)          # GPR, GPRC_<c> (tho)
    if shock_source == "ai_gpr":
        # Thay CHUOI TOAN CAU bang AI-GPR; giu nguyen cot nuoc cua file C-I
        # (xem canh bao o docstring — AI-GPR tach nuoc o file khac, schema khac).
        ai = load_ai_gpr_monthly(ai_gpr_path)
        rename = {"AIGPR": "GPR", "AIGPR_ACT": "GPR_ACT", "AIGPR_THREAT": "GPR_THREAT"}
        ai = ai[[c for c in rename if c in ai.columns]].rename(columns=rename)
        keep = [c for c in gpr_m.columns if c.startswith("GPRC_")]
        gpr_m = ai.join(gpr_m[keep], how="inner")
        gpr_m.attrs["shock_source"] = "ai_gpr"
        gpr_m.attrs["ai_gpr_vintage"] = ai_gpr_vintage(ai_gpr_path)
    else:
        gpr_m.attrs["shock_source"] = "gpr_ci"
    gpr_m = gpr_m.loc[start:end] if end else gpr_m.loc[start:]
    country_col = f"GPRC_{country}"

    # GPR global -> innovation (β). log1p ap trong innovation(is_level=False).
    gpr_innov = innovation(gpr_m["GPR"], min_train=min_train,
                           max_order=max_order).rename("GPR_INNOV")

    # GPRC_<c>: log1p -> orthogonalize khoi GPR global (level) -> innovation (λ).
    #   Phan RIENG cua nuoc c (⊥ global) moi la domestic-direct (docs/07v2 §4.1, #8).
    lg = pd.DataFrame({
        "ctry": log1p_gpr(gpr_m[country_col]),
        "gpr": log1p_gpr(gpr_m["GPR"]),
    }).dropna()
    ctry_orth = orthogonalize(lg, target="ctry", on=["gpr"])  # residual = phan rieng
    vnm_orth_innov = innovation(ctry_orth, is_level=True, min_train=min_train,
                                max_order=max_order).rename(f"{country_col}_ORTH_INNOV")

    # Gia tri cua thang M chi duoc dung trong bucket M+1 (sau khi thang M ket
    # thuc). Khong join GPR thang M voi outcome cung thang M nhu the da biet tu
    # dau thang.
    gpr_innov = align_monthly_gpr_to_information_time(gpr_innov)
    vnm_orth_innov = align_monthly_gpr_to_information_time(vnm_orth_innov)

    macro = load_macro_monthly(start, end, cache_dir, refresh)
    cols = [c for c in macro_vars if c in macro.columns]
    macro = macro[cols]

    frames = [macro, gpr_innov, vnm_orth_innov]
    if shock_axis:
        # Ba thuoc do di CUNG mot duong information-time nhu GPR_INNOV — thang M
        # chi dung o bucket M+1. Quen align o day = mot thuoc do nhin truoc mot
        # thang so voi cac thuoc do khac, va so sanh giua chung thanh vo nghia.
        series = ["GPR", *(["GPR_ACT", "GPR_THREAT"] if components else [])]
        for name in series:
            prefix = "GPR" if name == "GPR" else name
            axis = build_monthly_shock_axis(
                gpr_m[name], prefix=prefix, min_train=min_train,
                max_order=max_order)
            frames.append(align_monthly_gpr_to_information_time(axis))
    if dual_component:
        # Spec CHINH docs/17_master_plan.md §4.1. Di cung duong information-time
        # nhu moi thuoc do khac — thang M chi dung o bucket M+1.
        for name in ["GPR", *(["GPR_ACT", "GPR_THREAT"] if components else [])]:
            comp = delta_decomposition(gpr_m[name].rename(name),
                                       min_train=min_train, max_order=max_order)
            frames.append(align_monthly_gpr_to_information_time(comp))
    if freight:
        fr_raw = load_freight_monthly(start, end, cache_dir, refresh)
        frames.append(transform_freight(fr_raw))
    if real_macro:
        frames.append(transform_real_macro(
            load_real_macro_monthly(start, end, cache_dir, refresh)))
    if battery:
        # wui_path=None CÓ CHỦ ĐÍCH: WUI publish theo QUÝ ở nhiều vintage; join vào
        # grid tháng để lại NaN 2/3 số hàng, và complete-case ở cuối hàm sẽ XÓA 2/3
        # panel — im lặng. Forward-fill quý->tháng thì vi phạm #10. WUI phải do
        # runner xử lý tường minh ở tần suất của nó (load_benchmark_monthly).
        frames.append(transform_benchmark(
            load_benchmark_monthly(start, end, cache_dir, refresh, wui_path=None)))
    if extra_monthly is not None:
        frames.append(extra_monthly)
    panel = frames[0].to_frame() if isinstance(frames[0], pd.Series) else frames[0]
    for f in frames[1:]:
        panel = panel.join(f, how="inner")
    return panel.sort_index().dropna()
