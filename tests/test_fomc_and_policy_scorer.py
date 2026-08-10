"""Test thu thap van ban Fed (`ingest/fomc.py`) + rubric do hien dien GPR
(`scoring/policy_gpr_scorer.py`).

KHONG cham mang, KHONG goi LLM that: fetcher va LLM client deu tiem vao.
Fixture RSS/HTML chep theo dung hinh dang tra ve that cua federalreserve.gov
(kiem 2026-08-09).

Cai duoc test la cac BAT BIEN de hong chuoi do luong:
  - `published_at` den PHUT, khong bi ep ve ngay (#5);
  - loai van ban phan biet duoc — khong gop thong cao nhan su vao chuoi;
  - contract JSON STRICT: sai key/mien -> raise, KHONG clip, KHONG sua ho;
  - rang buoc noi tai cua rubric (salience=0 thi khong the co channel/binding);
  - cache phu MOI truc version — doi rubric/model thi diem cu khong duoc dung lai;
  - van ban dai bi CAT phai ghi ro trong prompt, khong cat im lang.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from gpr_engine.ingest.fomc import (
    FomcDocument,
    FomcRelease,
    classify_title,
    extract_text,
    fetch_document,
    fetch_releases,
    parse_feed,
    parse_index,
    resolve_minutes_url,
)
from gpr_engine.scoring.policy_gpr_scorer import (
    CHANNELS,
    PolicyScorerConfig,
    ScoreParseError,
    aggregate_chunks,
    build_messages,
    content_hash,
    parse_score,
    score_document,
    split_document,
)

FEED = b"""<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0"><channel>
  <item>
    <title>Federal Reserve issues FOMC statement</title>
    <link>/newsevents/pressreleases/monetary20260729a.htm</link>
    <pubDate>Wed, 29 Jul 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Minutes of the Federal Open Market Committee, June 16-17, 2026</title>
    <link>/newsevents/pressreleases/monetary20260708a.htm</link>
    <pubDate>Wed, 8 Jul 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Federal Reserve announces the leadership of its task force</title>
    <link>/newsevents/pressreleases/other20260709a.htm</link>
    <pubDate>Thu, 9 Jul 2026 19:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

HTML = (b"<html><head><style>p{color:red}</style></head><body>"
        b'<div id="article"><p>The Committee decided to maintain the target '
        b"range for the federal funds rate. Tensions in the Middle East have "
        b"raised energy prices and the Committee judges risks to the outlook "
        b"to be tilted to the upside.</p><p>Voting against was one member."
        b"</p></div></div></body></html>")


def _doc(text: str = "x" * 500, doc_type: str = "statement") -> FomcDocument:
    return FomcDocument(doc_type=doc_type, title="t", url="u",
                        published_at=pd.Timestamp("2026-07-29T18:00", tz="UTC"),
                        text=text)


# ---------------------------------------------------------------------------
# Thu thap
# ---------------------------------------------------------------------------
def test_feed_timestamp_is_minute_precise_not_a_date():
    """#5: nguon realtime khong bao gio chi luu ngay. 14:00 ET = 18:00 GMT."""
    rel = parse_feed(FEED)[0]
    assert rel.published_at == pd.Timestamp("2026-07-29T18:00", tz="UTC")
    assert rel.published_at != rel.published_at.normalize()


def test_classify_separates_statement_minutes_and_noise():
    """Feed tien te con chua thong cao nhan su/ky thuat — gop het la lam loang."""
    assert classify_title("Federal Reserve issues FOMC statement") == "statement"
    assert classify_title(
        "Minutes of the Federal Open Market Committee, June 16-17, 2026") == "minutes"
    assert classify_title(
        "Minutes of the Board's discount rate meetings on June 8") == "other"
    assert classify_title("Federal Reserve announces leadership") == "other"


def test_fetch_releases_filters_to_policy_documents_only():
    got = fetch_releases(fetcher=lambda url: FEED)
    assert [r.doc_type for r in got] == ["statement", "minutes"]
    assert all(r.url.startswith("https://www.federalreserve.gov") for r in got)


def test_relative_links_become_absolute():
    assert parse_feed(FEED)[0].url == (
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm")


def test_feed_items_missing_fields_are_skipped_not_guessed():
    bad = b"""<rss><channel><item><title>Federal Reserve issues FOMC statement</title>
    </item></channel></rss>"""
    assert parse_feed(bad) == []


def test_extract_text_strips_markup_and_style():
    text = extract_text(HTML)
    assert "color:red" not in text and "<p>" not in text
    assert "Tensions in the Middle East" in text
    assert "  " not in text


def test_short_page_raises_instead_of_scoring_empty_text():
    """Trang doi layout -> text ngan bat thuong. Cham chuoi rong se ra diem
    'hop le' ma vo nghia, nen phai bao o day."""
    rel = parse_feed(FEED)[0]
    with pytest.raises(ValueError, match="ky tu"):
        fetch_document(rel, fetcher=lambda url: b"<html><body>hi</body></html>")


# --- minutes: link trong feed KHONG phai ban minutes ------------------------
ANNOUNCE = (b'<html><body><div id="article"><p>The Federal Reserve on Wednesday '
            b"released the minutes of the Federal Open Market Committee meeting "
            b"held on June 16-17, 2026. The minutes for each regularly scheduled "
            b"meeting are published three weeks after the decision.</p>"
            b'<a href="/monetarypolicy/fomcminutes20260617.htm">HTML</a>'
            b'<a href="/monetarypolicy/files/fomcminutes20260617.pdf">PDF</a>'
            b"</div></body></html>")
REAL_MINUTES = (b'<html><body><div id="article"><p>'
                + b"Participants discussed geopolitical tensions in the Middle "
                  b"East and the associated rise in energy prices. " * 120
                + b"</p></div></body></html>")


def test_minutes_resolves_to_the_real_document_not_the_announcement():
    """Link RSS cua minutes tro toi THONG CAO (~760 ky tu), ban that ~36k ky tu.

    Cham nham thong cao khong bao loi — no chi lam moi ban minutes ra salience
    ~0 mot cach HE THONG. Do la kieu hong nguy hiem nhat: chuoi trong nhu that.
    """
    rel = [r for r in parse_feed(FEED) if r.doc_type == "minutes"][0]
    pages = {rel.url: ANNOUNCE,
             "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260617.htm":
                 REAL_MINUTES}
    doc = fetch_document(rel, fetcher=lambda u: pages[u])
    assert doc.url.endswith("fomcminutes20260617.htm")
    assert doc.release_url == rel.url
    assert len(doc.text) > 5000
    assert "geopolitical tensions" in doc.text


def test_minutes_prefer_html_over_pdf():
    assert resolve_minutes_url(ANNOUNCE).endswith(".htm")


def test_minutes_falling_back_to_announcement_raises():
    """Resolve hong -> van con o trang thong cao -> nguong rieng cua minutes bat."""
    rel = [r for r in parse_feed(FEED) if r.doc_type == "minutes"][0]
    no_link = ANNOUNCE.replace(b'href="/monetarypolicy/fomcminutes20260617.htm"',
                               b'href="/somewhere-else.htm"')
    with pytest.raises(ValueError, match="resolve hong|ky tu"):
        fetch_document(rel, fetcher=lambda u: no_link)


def test_statement_threshold_is_not_the_minutes_threshold():
    """Statement that chi ~1.250 ky tu — ap nguong cua minutes se bac ca bo."""
    from gpr_engine.ingest.fomc import MIN_CHARS

    assert MIN_CHARS["statement"] < 1250 < MIN_CHARS["minutes"]


# ---------------------------------------------------------------------------
# Backfill lich su — doc van ban that, KHONG hoi LLM "nho lai"
# ---------------------------------------------------------------------------
# Hai dang trang muc luc that (chep theo federalreserve.gov, kiem 2026-08-09).
INDEX_NEW = (b'<a href="/newsevents/pressreleases/monetary20260729a.htm">HTML</a>'
             b'<a href="/monetarypolicy/fomcprojtabl20260617.htm">HTML</a>'
             b' Minutes: <a href="/monetarypolicy/fomcminutes20260617.htm">HTML</a>'
             b" (Released July 08, 2026)")
INDEX_OLD = (b"2015 Memos Minutes (Released February 18, 2015): "
             b'<a href="/monetarypolicy/fomcminutes20150128.htm">HTML</a>'
             b'<a href="/newsevents/press/monetary/20150128a.htm">Statement</a>')


def test_minutes_published_at_is_release_date_not_meeting_date():
    """Bay ba tuan: URL minutes mang ngay HOP, cong bo ~3 TUAN SAU.

    Lay ngay hop lam published_at la gan cho van ban mot moc som hon ba tuan so
    voi luc no ton tai — look-ahead thang (CLAUDE.md #5, #11).
    """
    rel = [r for r in parse_index(INDEX_NEW) if r.doc_type == "minutes"][0]
    assert "20260617" in rel.url                       # ngay HOP trong URL
    assert rel.published_at.date() == dt.date(2026, 7, 8)   # ngay CONG BO
    assert (rel.published_at.date() - dt.date(2026, 6, 17)).days > 14


def test_index_timestamp_reproduces_the_rss_timestamp():
    """Kiem cheo hai duong: 14:00 ET quy doi phai TRUNG timestamp RSS.

    RSS cho moc chinh xac; archive suy ra tu gio cong bo. Hai duong lech nhau la
    mot trong hai sai — va chuoi backfill se khong noi duoc voi chuoi cap nhat.
    """
    from_feed = {(r.doc_type, r.published_at) for r in parse_feed(FEED)
                 if r.doc_type in ("statement", "minutes")}
    from_index = {(r.doc_type, r.published_at) for r in parse_index(INDEX_NEW)}
    assert from_index <= from_feed, f"lech: {from_index - from_feed}"


def test_old_index_layout_is_parsed_too():
    """Trang lich su dat '(Released ...)' TRUOC link, trang moi dat SAU."""
    got = {r.doc_type: r for r in parse_index(INDEX_OLD)}
    assert got["minutes"].published_at.date() == dt.date(2015, 2, 18)
    assert got["statement"].published_at.date() == dt.date(2015, 1, 28)


def test_minutes_without_release_date_raises_instead_of_guessing():
    """Khong ro ngay cong bo -> raise. Lay tam ngay hop la look-ahead im lang."""
    no_date = INDEX_NEW.replace(b" (Released July 08, 2026)", b"")
    with pytest.raises(ValueError, match="ngay cong bo"):
        parse_index(no_date)
    assert [r.doc_type for r in parse_index(no_date, strict=False)] == ["statement"]


def test_statement_release_time_is_dst_aware():
    """14:00 ET = 18:00 UTC mua he, 19:00 UTC mua dong. Ep cung mot offset la
    sai mot tieng nua nam."""
    summer = parse_index(INDEX_NEW)[0].published_at
    winter = [r for r in parse_index(INDEX_OLD) if r.doc_type == "statement"][0]
    assert summer.hour == 18 and winter.published_at.hour == 19


def test_pre_2009_minutes_url_layout_is_parsed():
    """Minutes truoc 2009 dung /fomc/minutes/YYYYMMDD.htm, khong phai
    fomcminutesYYYYMMDD.htm. Thieu dang nay thi mat SACH minutes 2003-2008 mà
    bang coverage van trong 'day du' vi statement con nguyen (do that: 0/8 nam).
    Ngay cong bo o trang cu viet tat thang: 'Released Feb 23, 2005'."""
    old = (b"Statement Minutes (Released Feb 23, 2005) Transcript "
           b'<a href="/fomc/minutes/20050202.htm">HTML</a>')
    rel = [r for r in parse_index(old) if r.doc_type == "minutes"]
    assert len(rel) == 1
    assert rel[0].published_at.date() == dt.date(2005, 2, 23)


def test_index_deduplicates_repeated_links():
    """Trang muc luc lap link (PDF/HTML/nhieu khoi) — khong khu trung thi mot
    van ban vao chuoi nhieu lan."""
    assert len(parse_index(INDEX_NEW + INDEX_NEW)) == len(parse_index(INDEX_NEW))


def test_fetch_document_keeps_release_metadata():
    rel = parse_feed(FEED)[0]
    doc = fetch_document(rel, fetcher=lambda url: HTML)
    assert doc.doc_type == "statement"
    assert doc.published_at == rel.published_at
    assert doc.doc_id == "fomc_statement_20260729T1800"


def test_release_rejects_unknown_doc_type():
    with pytest.raises(ValueError, match="doc_type"):
        FomcRelease(doc_type="speech", title="t", url="u",
                    published_at=pd.Timestamp("2026-01-01T12:00", tz="UTC"))


# ---------------------------------------------------------------------------
# Rubric — contract STRICT
# ---------------------------------------------------------------------------
def _ok(**over) -> str:
    base = {"gpr_salience": 0.6, "channel": "energy", "direction": "risk_up",
            "binding": True, "evidence": "Tensions in the Middle East",
            "rationale": "energy channel discussed"}
    base.update(over)
    return json.dumps(base)


def test_parse_accepts_wellformed_score():
    got = parse_score(_ok())
    assert got["gpr_salience"] == 0.6 and got["channel"] == "energy"
    assert got["binding"] is True


@pytest.mark.parametrize("bad", [
    _ok(gpr_salience=1.4),                 # ngoai mien
    _ok(gpr_salience="high"),              # sai kieu
    _ok(channel="sanction"),               # ngoai 4 kenh truyen dan
    _ok(direction="up"),                   # ngoai tap
    _ok(binding="yes"),                    # khong phai bool
    "{}",                                  # thieu key
    "not json",
])
def test_parse_rejects_bad_output_without_fixing(bad):
    with pytest.raises(ScoreParseError):
        parse_score(bad)


def test_out_of_range_is_not_clipped_into_valid():
    """Clip = hop thuc hoa so LLM sinh ngoai rubric. Phai raise."""
    with pytest.raises(ScoreParseError, match=r"ngoai \[0, 1\]"):
        parse_score(_ok(gpr_salience=2.0))


def test_rubric_internal_contradictions_are_rejected():
    """salience=0 ma van co kenh/binding = LLM dang doan chu khong doc."""
    with pytest.raises(ScoreParseError, match="tu mau thuan"):
        parse_score(_ok(gpr_salience=0.0, channel="energy", binding=False))
    with pytest.raises(ScoreParseError, match="tu mau thuan"):
        parse_score(_ok(gpr_salience=0.0, channel=None, binding=True))
    with pytest.raises(ScoreParseError, match="tu mau thuan"):
        parse_score(_ok(gpr_salience=0.05, channel=None, binding=True))


def test_zero_salience_with_null_fields_is_valid():
    """Mat con lai: van ban khong co noi dung dia chinh tri la ket qua HOP LE."""
    got = parse_score(_ok(gpr_salience=0.0, channel=None, binding=False,
                          direction="neutral", evidence=""))
    assert got["gpr_salience"] == 0.0 and got["channel"] is None


def test_channels_are_the_gamma_table_transmission_channels():
    """Dung 4 kenh truyen dan, KHONG phai 6 kenh cham diem cua docs/00 —
    dau ra module nay de doi chieu voi bang γ."""
    from gpr_engine.scoring.statement_scorer import TRANSMISSION_CHANNELS

    assert set(CHANNELS) == set(TRANSMISSION_CHANNELS)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------
def _cfg(**over) -> PolicyScorerConfig:
    kw = {"model_version": "m1", "training_cutoff": dt.date(2026, 1, 1)}
    kw.update(over)
    return PolicyScorerConfig(**kw)


def test_score_document_returns_versioned_row():
    row = score_document(_doc(), lambda m, t: _ok(), _cfg())
    assert row["doc_id"] == "fomc_statement_20260729T1800"
    for k in ("model_version", "rubric_version", "prompt_version",
              "temperature", "training_cutoff"):
        assert k in row, f"thieu truc version {k} (CLAUDE.md #4)"


def test_bad_output_is_retried_then_raises():
    calls = {"n": 0}

    def flaky(messages, temp):
        calls["n"] += 1
        return "garbage" if calls["n"] == 1 else _ok()

    assert score_document(_doc(), flaky, _cfg())["gpr_salience"] == 0.6
    assert calls["n"] == 2

    with pytest.raises(ScoreParseError):
        score_document(_doc(), lambda m, t: "garbage", _cfg())


def test_failure_is_not_silently_turned_into_zero():
    """0 la GIA TRI CO NGHIA cua rubric ("khong co noi dung dia chinh tri") —
    dung no lam gia tri that bai la lam hong chinh chuoi do."""
    with pytest.raises(ScoreParseError):
        score_document(_doc(), lambda m, t: "{}", _cfg(), max_retries=0)


def test_cache_hit_avoids_second_llm_call():
    calls = {"n": 0}

    def llm(messages, temp):
        calls["n"] += 1
        return _ok()

    cache: dict = {}
    score_document(_doc(), llm, _cfg(), cache=cache)
    score_document(_doc(), llm, _cfg(), cache=cache)
    assert calls["n"] == 1


def test_cache_key_covers_every_version_axis():
    """Doi rubric/model/temperature -> diem cu VO HIEU, khong duoc doc nham."""
    doc = _doc()
    base = content_hash(doc, "m1", 0.1)
    assert content_hash(doc, "m2", 0.1) != base
    assert content_hash(doc, "m1", 0.7) != base
    assert content_hash(_doc(text="y" * 500), "m1", 0.1) != base


def test_long_document_is_split_not_truncated():
    """Minutes 36k-46k ky tu. Cat lay 12k dau la bo ~2/3, va phan bo KHONG ngau
    nhien (muc ban ve rui ro nam giua/cuoi) -> salience minutes tut xuong mot
    cach HE THONG. Phai chia doan va cham het."""
    text = ". ".join(f"sentence {i}" for i in range(2000))
    parts = split_document(text, max_chars=1000)
    assert len(parts) > 10
    assert all(len(p) <= 1000 for p in parts)
    # khong mat chu nao
    assert sum(len(p) for p in parts) >= len(text) - 2 * len(parts)
    assert "sentence 1999" in parts[-1]


def test_split_keeps_short_document_whole():
    assert split_document("a. b. c.", max_chars=1000) == ["a. b. c."]


def test_every_chunk_is_scored():
    calls = {"n": 0}

    def llm(messages, temp):
        calls["n"] += 1
        return _ok()

    doc = _doc(text=". ".join(f"s{i}" for i in range(4000)))
    n_parts = len(split_document(doc.text, 1000))
    row = score_document(doc, llm, _cfg(), max_chars=1000)
    assert calls["n"] == n_parts == row["n_chunks"] > 1


def test_aggregate_uses_length_weighted_mean_and_keeps_max():
    """mean = do hien dien tren TOAN van ban; max = doan dam dac nhat. Giu ca
    hai vi mot van ban nhac dam mot doan roi thoi co mean thap ma max cao — do
    la thong tin that."""
    scores = [
        {"gpr_salience": 0.0, "channel": None, "direction": "neutral",
         "binding": False, "evidence": "", "rationale": ""},
        {"gpr_salience": 0.8, "channel": "energy", "direction": "risk_up",
         "binding": True, "evidence": "quote", "rationale": "why"},
    ]
    agg = aggregate_chunks(scores, [3000, 1000])
    assert agg["gpr_salience"] == pytest.approx(0.8 * 1000 / 4000)
    assert agg["gpr_salience_max"] == 0.8
    assert agg["binding"] is True            # BAT KY doan nao binding
    assert agg["channel"] == "energy"        # tu doan salience cao nhat
    assert agg["evidence"] == "quote"


def test_binding_is_not_averaged_away():
    """Mot doan noi GPR anh huong trien vong la du. Trung binh cua bool vo nghia."""
    scores = [{"gpr_salience": 0.1, "channel": None, "direction": "neutral",
               "binding": False, "evidence": "", "rationale": ""} for _ in range(9)]
    scores.append({"gpr_salience": 0.9, "channel": "military",
                   "direction": "risk_up", "binding": True,
                   "evidence": "q", "rationale": "r"})
    assert aggregate_chunks(scores, [100] * 10)["binding"] is True


def test_chunk_metadata_tells_the_model_which_part_it_is():
    msgs = build_messages(_doc(), chunk="abc", chunk_index=2, n_chunks=5)
    meta = json.loads(msgs[1]["content"].split("\n", 1)[0].removeprefix("metadata: "))
    assert meta["chunk"] == "3/5"


def test_cache_key_differs_per_chunk():
    doc = _doc()
    assert content_hash(doc, "m1", 0.1, "chunk A") != content_hash(doc, "m1", 0.1, "chunk B")


def test_prompt_forbids_using_later_knowledge():
    """Cong contamination (docs/14 §3.1.1) phai nam TRONG prompt."""
    sys_msg = build_messages(_doc())[0]["content"]
    assert "after the document's date" in sys_msg
    assert "verbatim" in sys_msg.lower()


def test_prompt_excludes_natural_disasters():
    """Lech DA DO tren ket qua that pg1: 2/134 van ban co salience>0 la thien tai
    bi cham thanh dia chinh tri (Hurricane Rita sal=0.39, hurricanes sal=0.40).
    Model neo vao 'gian doan nguon cung nang luong' roi suy ra dia chinh tri.
    pg2 loai tru tuong minh — bo dong nay la tai lap lai dung lech do."""
    sys_msg = build_messages(_doc())[0]["content"]
    low = sys_msg.lower()
    for word in ("hurricane", "earthquake", "pandemic"):
        assert word in low, f"prompt khong loai tru {word}"
    assert "state, an armed group, or a political decision" in sys_msg


def test_rubric_version_bump_invalidates_old_cache():
    """Diem cham bang prompt KHAC khong duoc tron vao cung mot chuoi.

    `content_hash` phu ca rubric lan prompt version, nen bump la cache cu vo
    hieu — day la co che, khong phai tac dung phu."""
    import gpr_engine.scoring.policy_gpr_scorer as m

    doc = _doc()
    before = content_hash(doc, "m1", 0.1)
    old_rubric, m.RUBRIC_VERSION = m.RUBRIC_VERSION, "pg_other"
    try:
        assert content_hash(doc, "m1", 0.1) != before
    finally:
        m.RUBRIC_VERSION = old_rubric


def test_training_cutoff_is_required():
    """Thieu cutoff thi bang diem khong phan biet duoc backfill nhiem hindsight."""
    with pytest.raises(TypeError):
        PolicyScorerConfig(model_version="m1")
