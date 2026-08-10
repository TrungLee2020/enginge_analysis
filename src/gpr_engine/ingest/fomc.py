"""fomc.py — thu thap van ban chinh sach cua Fed (statement / minutes). 🔬 research

MUC DICH — doc ky truoc khi dung, vi rat de dung nham truc:
    Module nay KHONG do cu soc chinh sach tien te My. Cu soc do da co ban do
    SACH hon nhieu tu gia phai sinh quanh cua so FOMC (high-frequency
    identification: Kuttner 2001; Gurkaynak-Sack-Swanson 2005; Nakamura-
    Steinsson 2018; chuoi Bauer-Swanson 2023, Bu-Rogers-Wu 2021 da publish).
    Cham "giong dieu hawkish" bang LLM de suy ra cu soc do la dung lai cai da co
    bang mot proxy nhieu hon — vi pham CLAUDE.md #2.
    (Ly do `docs/14` §5 chon Aruoba-Drechsel cho khoi chinh sach la vi **VN**
    khong co phai sinh lai suat. My thi co. Dung nham module nay cho My la doc
    nguoc ly do do.)

    Cai module nay phuc vu la cau hoi NGUOC LAI, va la cau hoi rieng cua du an:
    **rui ro dia chinh tri co di vao ham phan ung chinh sach khong, manh toi
    dau, qua kenh nao** — do bang chinh van ban Fed. Khong nguon nao ban san;
    Caldara-Iacoviello lam bien the tuong tu tren Beige Book va earnings call.
    Cham diem o `scoring/policy_gpr_scorer.py` (rubric RIENG, khong dung lai
    thang leo thang ±1.0 — hai construct khac nhau).

NGUON: federalreserve.gov, cong khai, mien phi.
    ⚠️ Tra 403 neu khong dat `User-Agent` kieu trinh duyet — do la chan BOT,
    khong phai chan egress (da kiem 2026-08-09: khong UA -> 403, co UA -> 200).
    Dung nham hai cai nay se dan den ket luan "khong tai duoc" sai.

`published_at`: lay tu `pubDate` cua RSS — chinh xac den PHUT (CLAUDE.md #5).
    Statement ra 14:00 ET = 18:00 GMT; feed ghi dung moc do. KHONG duoc thay
    bang ngay: event study quanh cong bo FOMC song bang phut.

I/O TIEM VAO: moi ham mang truyen `fetcher` callable -> test khong cham mang.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

BASE = "https://www.federalreserve.gov"
PRESS_FEED_URL = f"{BASE}/feeds/press_monetary.xml"

# Bat buoc — thieu la 403 (chan bot). Xem docstring module.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124 Safari/537.36")

DOC_TYPES = ("statement", "minutes", "other")

Fetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class FomcRelease:
    """Mot muc trong feed — CHUA co noi dung, chi metadata + link."""

    doc_type: str
    title: str
    url: str
    published_at: pd.Timestamp     # UTC, den phut

    def __post_init__(self) -> None:
        if self.doc_type not in DOC_TYPES:
            raise ValueError(f"doc_type={self.doc_type!r} khong thuoc {DOC_TYPES}")
        ts = pd.Timestamp(self.published_at)
        if pd.isna(ts):
            raise ValueError("published_at la NaT — bat buoc co (CLAUDE.md #5).")


@dataclass(frozen=True)
class FomcDocument:
    """Mot van ban day du, san sang dua vao scorer.

    `url` la trang CO NOI DUNG duoc cham; `release_url` la trang thong cao trong
    feed. Voi minutes hai cai KHAC NHAU — xem `resolve_minutes_url`.
    """

    doc_type: str
    title: str
    url: str
    published_at: pd.Timestamp
    text: str
    release_url: str | None = None

    @property
    def doc_id(self) -> str:
        """Dinh danh on dinh: loai + moc thoi gian cong bo."""
        return f"fomc_{self.doc_type}_{self.published_at.strftime('%Y%m%dT%H%M')}"


def default_fetcher(url: str) -> bytes:
    """Tai that. Tach rieng de moi cho khac tiem duoc fake."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def classify_title(title: str) -> str:
    """Nhan loai van ban tu tieu de feed.

    CHI nhan hai loai co lich cong bo on dinh (statement, minutes cua FOMC).
    Moi thu khac -> "other" va KHONG duoc coi la van ban chinh sach: feed tien
    te con chua thong cao nhan su, discount-rate minutes cua cac Bank, ban tin
    ky thuat... Gop het vao mot ro se lam loang chuoi do luong.
    """
    t = title.lower()
    if "fomc statement" in t or "issues fomc statement" in t:
        return "statement"
    if "minutes of the federal open market committee" in t:
        return "minutes"
    return "other"


def parse_feed(xml_bytes: bytes) -> list[FomcRelease]:
    """RSS -> danh sach FomcRelease (ke ca `other`; loc la viec cua caller)."""
    root = ET.fromstring(xml_bytes)
    out: list[FomcRelease] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not (title and link and pub):
            continue                       # muc thieu truong -> bo, khong doan
        ts = pd.to_datetime(pub, utc=True, errors="coerce")
        if pd.isna(ts):
            continue
        out.append(FomcRelease(
            doc_type=classify_title(title), title=title,
            url=link if link.startswith("http") else BASE + link,
            published_at=ts))
    return out


_TAG_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_ARTICLE_RE = re.compile(r'<div[^>]+id="article".*?</div>\s*</div>', re.S | re.I)


def extract_text(html: bytes | str) -> str:
    """HTML trang thong cao -> van ban thuan.

    Uu tien khoi `<div id="article">` (than bai). Khong thay thi lay ca trang —
    ban day du van tot hon ban rong, va scorer co nguong do dai rieng.
    """
    raw = html.decode("utf-8", "ignore") if isinstance(html, bytes) else html
    raw = _TAG_RE.sub(" ", raw)
    m = _ARTICLE_RE.search(raw)
    body = m.group(0) if m else raw
    text = re.sub(r"<[^>]+>", " ", body)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&#8217;", "'").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", text).strip()


def fetch_releases(fetcher: Fetcher | None = None,
                   doc_types: tuple[str, ...] = ("statement", "minutes"),
                   ) -> list[FomcRelease]:
    """Feed -> cac release thuoc `doc_types`, moi nhat truoc. Duong CAP NHAT.

    ⚠️ Feed CHI giu ~15 muc gan nhat va khong co phan trang. Dung chuoi lich su
    la viec cua `list_archive()` — doc VAN BAN THAT tu kho cua Fed.
    """
    fetch = fetcher or default_fetcher
    return [r for r in parse_feed(fetch(PRESS_FEED_URL)) if r.doc_type in doc_types]


# ---------------------------------------------------------------------------
# Backfill lich su — doc VAN BAN THAT, khong hoi LLM "nho lai"
# ---------------------------------------------------------------------------
# ⚠️ KHONG BAO GIO backfill bang cach hoi LLM noi dung van ban cu. Do la SINH du
# lieu tu tri nho model, khong phai DO van ban (CLAUDE.md #1), va model biet
# chuyen xay ra sau do nen moi diem se nhiem hindsight — dung thu ma
# `training_cutoff` sinh ra de chan. Truong `evidence` doi trich NGUYEN VAN cung
# se thanh trich dan bia, khong doi chieu duoc. Kho van ban that tai duoc (kiem
# 2026-08-09): trang lich hien tai phu 2021-01..nay, trang
# fomchistorical<YYYY>.htm phu tung nam cu.
CALENDAR_URL = f"{BASE}/monetarypolicy/fomccalendars.htm"
ARCHIVE_YEAR_URL = BASE + "/monetarypolicy/fomchistorical{year}.htm"

# Statement co NHIEU dang URL theo thoi ky (2021+: pressreleases/monetary…;
# giua: press/monetary/…; <=2005: boarddocs/press/monetary/YYYY/YYYYMMDD/…).
# Khong doan quy tac theo nam — doc thang chinh trang muc luc cua Fed.
_STATEMENT_HREF_RE = re.compile(
    r'href="([^"]*(?:press(?:releases)?/monetary/?)(\d{8})a?\.htm)"', re.I)
# Thoi ky <=2005 nam duoi /boarddocs/. HAI bien the, deu la statement FOMC:
#   .../press/monetary/YYYY/YYYYMMDD/default.htm   (2003-2005)
#   .../press/general/YYYY/YYYYMMDD/              (2000-2002, KHONG co default.htm)
# Thieu bien the `general` + duoi `/` thi mat sach statement 2000-2002 — va mat
# AM THAM neu chuoi do di lam bien kiem soat: thang khong lay duoc se thanh
# "khong co cong bo" thay vi "chua thu thap".
# An toan vi cac link nay lay tu TRANG MUC LUC FOMC, khong phai quet ca site.
_BOARDDOCS_HREF_RE = re.compile(
    r'href="([^"]*boarddocs/press/(?:monetary|general)/\d{4}/(\d{8})/'
    r'(?:default\.htm)?)"', re.I)
# Minutes cung doi dang URL: 2009+ dung `fomcminutesYYYYMMDD.htm`, truoc do dung
# `/fomc/minutes/YYYYMMDD.htm`. Thieu dang cu thi mat toan bo minutes 2003-2008
# (do that: 0/8 moi nam) — va mat AM THAM, vi statement van day du nen bang
# coverage trong "co du lieu" cho ca giai doan do.
_MINUTES_HREF_RE = re.compile(
    r'href="([^"]*(?:fomcminutes|fomc/minutes/)(\d{8})\.htm)"', re.I)
_RELEASED_RE = re.compile(r"Released\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)

# Gio cong bo (America/New_York): statement 14:00 sau phien hop, minutes 14:00.
# ⚠️ GIA DINH THAN TRONG, CHUA VERIFY tung thoi ky (thap nien 2000-2013 co giai
# doan cong bo 14:15). Chi anh huong duong BACKFILL: van ban lay tu RSS mang
# timestamp CHINH XAC nen duong cap nhat khong dung gia dinh nay. Cung tinh
# trang voi PUBLISH_LAG_DAYS cua gpr_daily.py.
RELEASE_HOUR_ET = 14
RELEASE_TZ = "America/New_York"


def _et(day: pd.Timestamp) -> pd.Timestamp:
    """Ngay cong bo -> timestamp UTC. tz America/New_York xu ly DST giup."""
    naive = pd.Timestamp(day).normalize() + pd.Timedelta(hours=RELEASE_HOUR_ET)
    return naive.tz_localize(RELEASE_TZ).tz_convert("UTC")


def parse_index(html: bytes | str, strict: bool = True) -> list[FomcRelease]:
    """Trang muc luc (lich hien tai hoac fomchistorical<YYYY>) -> cac release.

    HAI NGAY KHAC NHAU, tron la look-ahead ba tuan:
      statement: URL mang ngay HOP = ngay cong bo (ra cuoi phien hop);
      minutes  : URL mang ngay HOP, nhung cong bo ~3 TUAN SAU. Ngay cong bo nam
                 trong text quanh link — "(Released July 08, 2026)" o trang lich
                 hien tai, "Minutes (Released February 18, 2015):" o trang cu.
    Khong tim thay ngay cong bo cua minutes thi `strict=True` raise; KHONG duoc
    lay tam ngay hop, vi lam vay la gan cho van ban mot moc som hon ba tuan so
    voi luc no ton tai.
    """
    raw = html.decode("utf-8", "ignore") if isinstance(html, bytes) else html
    out: list[FomcRelease] = []

    for rx in (_STATEMENT_HREF_RE, _BOARDDOCS_HREF_RE):
        for m in rx.finditer(raw):
            day = pd.to_datetime(m.group(2), format="%Y%m%d", errors="coerce")
            if pd.isna(day):
                continue
            href = m.group(1)
            out.append(FomcRelease(
                doc_type="statement", title=f"FOMC statement {day.date()}",
                url=href if href.startswith("http") else BASE + href,
                published_at=_et(day)))

    for m in _MINUTES_HREF_RE.finditer(raw):
        meeting = pd.to_datetime(m.group(2), format="%Y%m%d", errors="coerce")
        if pd.isna(meeting):
            continue
        lo, hi = max(0, m.start() - 250), m.end() + 300
        rel = _RELEASED_RE.search(raw[lo:hi])
        if rel is None:
            if strict:
                raise ValueError(
                    f"Khong tim thay ngay cong bo cho minutes {m.group(2)} — "
                    "KHONG duoc lay tam ngay hop (minutes ra sau ~3 tuan, lam "
                    "vay la look-ahead). Kiem lai layout trang muc luc.")
            continue
        published = pd.to_datetime(rel.group(1), errors="coerce")
        if pd.isna(published):
            if strict:
                raise ValueError(f"Ngay cong bo khong parse duoc: {rel.group(1)!r}")
            continue
        href = m.group(1)
        out.append(FomcRelease(
            doc_type="minutes",
            title=f"FOMC minutes, meeting {meeting.date()}",
            url=href if href.startswith("http") else BASE + href,
            published_at=_et(published)))

    # Trang muc luc lap link (PDF/HTML/nhieu khoi) -> khu trung theo (loai, url).
    seen, uniq = set(), []
    for r in sorted(out, key=lambda r: r.published_at, reverse=True):
        key = (r.doc_type, r.url)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq


def list_archive(years: list[int] | None = None, fetcher: Fetcher | None = None,
                 strict: bool = True) -> list[FomcRelease]:
    """Kho van ban that. `years=None` -> trang lich hien tai (2021+ tinh den 2026).

    Nam cu lay qua fomchistorical<YYYY>.htm. Fed cong khai minutes tu rat lau,
    nhung URL statement doi dang theo thoi ky nen bao phu se KHONG deu — ham nay
    tra ve nhung gi trang muc luc that su liet ke, khong bia them.
    """
    fetch = fetcher or default_fetcher
    urls = ([CALENDAR_URL] if years is None
            else [ARCHIVE_YEAR_URL.format(year=y) for y in years])
    out: list[FomcRelease] = []
    for u in urls:
        out.extend(parse_index(fetch(u), strict=strict))
    return sorted(out, key=lambda r: r.published_at, reverse=True)


_MINUTES_LINK_RE = re.compile(r'href="([^"]*fomcminutes\d{8}\.htm)"', re.I)


def resolve_minutes_url(html: bytes | str) -> str | None:
    """Trang thong cao minutes -> URL cua BAN MINUTES THAT.

    Link trong RSS cua minutes tro toi mot THONG CAO GIOI THIEU (~760 ky tu:
    "The Federal Reserve on Wednesday released the minutes of..."), KHONG phai
    ban minutes. Ban that nam o /monetarypolicy/fomcminutesYYYYMMDD.htm va dai
    ~36.000 ky tu (do that 2026-08-09).

    Cham nham trang thong cao khong bao loi — no chi lam moi ban minutes ra
    salience ~0 mot cach HE THONG, tuc chuoi do luong sai ma trong nhu that. Do
    la ly do co ca ham nay lan nguong `MIN_CHARS` ben duoi.

    Uu tien ban .htm; ban .pdf co ton tai nhung parse PDF la phu thuoc khac.
    """
    raw = html.decode("utf-8", "ignore") if isinstance(html, bytes) else html
    m = _MINUTES_LINK_RE.search(raw)
    if not m:
        return None
    link = m.group(1)
    return link if link.startswith("http") else BASE + link


# Nguong do dai theo TUNG loai. Minutes ngan hon nguong nay gan nhu chac chan la
# van con dung o trang thong cao — bat o day thay vi de no thanh mot diem 0 im lang.
MIN_CHARS: dict[str, int] = {"statement": 200, "minutes": 5000, "other": 200}


def fetch_document(release: FomcRelease, fetcher: Fetcher | None = None,
                   min_chars: int | None = None) -> FomcDocument:
    """Tai noi dung mot release; voi minutes thi ĐI TIEP toi ban minutes that.

    `min_chars`: mac dinh theo `MIN_CHARS[doc_type]`. Trang doi layout hoac
    resolve hong se cho text ngan bat thuong — raise thay vi tra mau rong roi
    de scorer cham mot chuoi trong (diem se "hop le" ma vo nghia).
    """
    fetch = fetcher or default_fetcher
    page = fetch(release.url)
    url, release_url = release.url, None

    if release.doc_type == "minutes":
        real = resolve_minutes_url(page)
        if real is not None:
            release_url, url = release.url, real
            page = fetch(url)

    text = extract_text(page)
    floor = MIN_CHARS.get(release.doc_type, 200) if min_chars is None else min_chars
    if len(text) < floor:
        raise ValueError(
            f"Van ban chi {len(text)} ky tu (<{floor}) tu {url} — "
            f"voi doc_type={release.doc_type!r} day gan nhu chac chan la resolve "
            "hong hoac trang doi layout, khong phai van ban ngan that.")
    return FomcDocument(doc_type=release.doc_type, title=release.title,
                        url=url, published_at=release.published_at,
                        text=text, release_url=release_url)
