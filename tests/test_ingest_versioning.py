"""Test co che vintage khi nap lai file nguon (`ingest/versioning.py`).

Hai tang:
  - PURE: nhan vintage, guard tham so — khong can DB.
  - LIVE: chay THAT tren Postgres neu co `GPR_TEST_DSN`, bo qua neu khong.
    Day la test DB that DAU TIEN cua repo (moi `ingest/*.py` truoc gio chi mock).
    Dung series_id rieng `ZZTEST_*` va don sach o cuoi — khong dung series that.

Ca test LIVE bat dung cai da xay ra tren du lieu that: GPR tinh lai hoi to gia
tri cu (do 2026-08-09: 42 ngay, median |Δ| 42.9 diem tren thang do ~300). "Chi
append ngay moi" se giu nguyen gia tri sai; "UPSERT thang" se mat ban cu.
"""
from __future__ import annotations

import datetime as dt
import os
import uuid

import pandas as pd
import pytest

from gpr_engine.ingest.versioning import (
    apply_snapshot,
    archive_label,
    snapshot_label,
)

LIVE_DSN = os.getenv("GPR_TEST_DSN")
live_only = pytest.mark.skipif(
    not LIVE_DSN, reason="can GPR_TEST_DSN tro toi Postgres co schema 001")


# ---------------------------------------------------------------------------
# PURE
# ---------------------------------------------------------------------------
def test_labels_are_deterministic_per_day():
    """Nap hai lan cung ngay -> cung nhan -> UPSERT idempotent, khong sinh rac."""
    d = dt.date(2026, 8, 9)
    assert snapshot_label("gpr_daily", d) == "gpr_daily_20260809"
    assert archive_label("gpr_daily", d) == "gpr_daily_pre_20260809"
    assert snapshot_label("gpr_daily", d) == snapshot_label("gpr_daily", d)


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="mode phai thuoc"):
        apply_snapshot(_frame(), "postgresql://fake", prefix="x", mode="append")


def test_missing_columns_raise_before_touching_db():
    """Thieu cot -> bao ngay, khong mo ket noi roi hong giua chung."""
    bad = _frame().drop(columns=["available_at"])
    with pytest.raises(ValueError, match="thieu cot"):
        apply_snapshot(bad, "postgresql://fake", prefix="x")


def test_empty_frame_is_noop_without_db():
    rep = apply_snapshot(_frame().iloc[:0], "postgresql://fake", prefix="x")
    assert rep.n_incoming == 0 and rep.n_changed == 0


def _frame(values=(1.0, 2.0), series="ZZTEST_A", dates=("2026-01-01", "2026-01-02"),
           source_version="sv1") -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [series] * len(values),
        "date": [pd.Timestamp(d).date() for d in dates],
        "value": list(values),
        "freq": ["daily"] * len(values),
        "source": ["zztest"] * len(values),
        "available_at": [pd.Timestamp(d, tz="UTC") for d in dates],
        "source_version": [source_version] * len(values),
    })


# ---------------------------------------------------------------------------
# LIVE — Postgres that
# ---------------------------------------------------------------------------
@pytest.fixture
def live():
    """Engine + tag rieng cho moi test, don sach o cuoi.

    ⚠️ Test KHONG duoc dung `RUNNING_VERSION` that: `apply_snapshot` ghi mo ta
    vao `data_versions` cho chinh nhan do, nen dung "v1" se de lai mo ta test
    tren nhan THAT cua DB (da xay ra mot lan, phai don tay). Nhan chay rieng
    `zztest_run_<tag>` cung bi xoa o cuoi.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(LIVE_DSN)
    tag = f"ZZTEST_{uuid.uuid4().hex[:8]}"
    yield engine, tag, f"zztest_run_{tag}"
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ext_series WHERE series_id = :s"), {"s": tag})
        conn.execute(text("DELETE FROM data_versions WHERE label LIKE :p"),
                     {"p": f"zztest_%{tag}%"})


def _rows(engine, tag: str, version: str) -> dict:
    from sqlalchemy import text

    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT date, value FROM ext_series
            WHERE series_id = :s AND data_version = :v ORDER BY date
        """), {"s": tag, "v": version}).all()
    return {str(d): v for d, v in r}


@live_only
def test_revised_value_is_archived_not_lost(live):
    """Cot loi: gia tri cu bi ghi de phai CON o nhan archive.

    Day la ca that cua GPR (42 ngay bi tinh lai) thu nho lai: ngay 2026-01-02
    doi 2.0 -> 9.9, va ngay 2026-01-03 la ngay moi.
    """
    engine, tag, run = live
    pre = f"zztest_{tag}"
    day1, day2 = dt.date(2026, 8, 1), dt.date(2026, 8, 2)

    r1 = apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre, when=day1,
                        running_version=run)
    assert (r1.n_new, r1.n_changed, r1.n_archived) == (2, 0, 0)
    assert _rows(engine, tag, run) == {"2026-01-01": 1.0, "2026-01-02": 2.0}

    r2 = apply_snapshot(
        _frame(values=(1.0, 9.9, 3.0),
               dates=("2026-01-01", "2026-01-02", "2026-01-03"), series=tag),
        LIVE_DSN, prefix=pre, when=day2, running_version=run)

    # 1 ngay moi, 1 gia tri revise, 1 khong doi — dung ba nhom.
    assert (r2.n_new, r2.n_changed, r2.n_unchanged) == (1, 1, 1)
    assert r2.n_archived == 1
    # Ban chay = moi nhat.
    assert _rows(engine, tag, run) == {
        "2026-01-01": 1.0, "2026-01-02": 9.9, "2026-01-03": 3.0}
    # Ban CU van con -> tai lap duoc "hom truoc ta biet gi".
    assert _rows(engine, tag, archive_label(pre, day2)) == {"2026-01-02": 2.0}


@live_only
def test_reload_same_file_writes_no_archive(live):
    """Nap lai y nguyen file cu -> 0 hang archive. Do la ca thuong gap nhat."""
    engine, tag, run = live
    pre = f"zztest_{tag}"
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre, when=dt.date(2026, 8, 1),
                   running_version=run)
    rep = apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre,
                         when=dt.date(2026, 8, 3), running_version=run)
    assert (rep.n_new, rep.n_changed, rep.n_archived) == (0, 0, 0)
    assert rep.n_unchanged == 2


@live_only
def test_revised_at_stamped_only_on_changed_row(live):
    """`revised_at` la dau hieu duy nhat trong ban chay noi 'hang nay tung khac'."""
    from sqlalchemy import text

    engine, tag, run = live
    pre = f"zztest_{tag}"
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre, when=dt.date(2026, 8, 1),
                   running_version=run)
    apply_snapshot(_frame(values=(1.0, 9.9), series=tag), LIVE_DSN, prefix=pre,
                   when=dt.date(2026, 8, 2), running_version=run)
    with engine.connect() as conn:
        got = dict(conn.execute(text("""
            SELECT date, revised_at IS NOT NULL FROM ext_series
            WHERE series_id = :s AND data_version = :v
        """), {"s": tag, "v": run}).all())
    assert got == {dt.date(2026, 1, 1): False, dt.date(2026, 1, 2): True}


@live_only
def test_full_mode_keeps_complete_snapshot(live):
    """`--snapshot full`: them ban sao TOAN BO, ban chay van duoc cap nhat."""
    engine, tag, run = live
    pre = f"zztest_{tag}"
    day = dt.date(2026, 8, 4)
    rep = apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre, mode="full",
                         when=day, running_version=run)
    assert rep.n_snapshot == 2
    assert _rows(engine, tag, snapshot_label(pre, day)) == _rows(engine, tag, run)


@live_only
def test_data_versions_ledger_gets_written(live):
    """So `data_versions` truoc day CHET (0 dong) — moi lan nap phai ghi vao."""
    from sqlalchemy import text

    engine, tag, run = live
    pre = f"zztest_{tag}"
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre, when=dt.date(2026, 8, 1),
                   description="test ledger", running_version=run)
    apply_snapshot(_frame(values=(1.0, 9.9), series=tag), LIVE_DSN, prefix=pre,
                   when=dt.date(2026, 8, 2), description="test ledger",
                   running_version=run)
    with engine.connect() as conn:
        labels = [r[0] for r in conn.execute(text(
            "SELECT label FROM data_versions WHERE label LIKE :p"),
            {"p": f"zztest_%{tag}%"}).all()]
    assert archive_label(pre, dt.date(2026, 8, 2)) in labels
    assert run in labels, "nhan cua ban CHAY cung phai vao so"


@live_only
def test_same_series_id_at_two_frequencies_is_refused(live):
    """Chot chan cho bug AI-GPR 2026-08-09 — bat o MOI nguon, khong rieng AI-GPR.

    PK khong chua `freq`, nen mot series_id mang hai tan suat se tu ghi de chinh
    no o moi ngay trung. Phai bao, khong duoc nap.
    """
    _, tag, run = live
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=f"zztest_{tag}",
                   when=dt.date(2026, 8, 1), running_version=run)
    monthly = _frame(series=tag).assign(freq="monthly")
    with pytest.raises(ValueError, match="TAN SUAT KHAC"):
        apply_snapshot(monthly, LIVE_DSN, prefix=f"zztest_{tag}",
                       when=dt.date(2026, 8, 2), running_version=run)


@live_only
def test_revision_aware_read_returns_the_value_in_force_then(live):
    """Replay qua khu phai ra gia tri DA CONG BO luc do, khong phai ban da sua.

    Ca that tren du lieu song (2026-08-09): GPRD_ACT 2026-06-24 hom nay la
    163.08, nhung dung ngay 2026-06-30 no la 293.83 — chenh 80%. Backtest doc
    ban hom nay la dung thong tin chua ton tai.
    """
    from sqlalchemy import text

    from gpr_engine.econometrics.dataset import load_series

    engine, tag, run = live
    pre = f"zztest_{tag}"
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=pre,
                   when=dt.date(2026, 8, 1), running_version=run)
    apply_snapshot(_frame(values=(1.0, 9.9), series=tag), LIVE_DSN, prefix=pre,
                   when=dt.date(2026, 8, 2), running_version=run)
    # `revised_at` do apply_snapshot dat = now(); day lui de "as_of" nam TRUOC no.
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ext_series SET revised_at = TIMESTAMPTZ '2026-08-02 00:00Z'
            WHERE series_id = :s AND data_version = :a
        """), {"s": tag, "a": archive_label(pre, dt.date(2026, 8, 2))})

    before = pd.Timestamp("2026-08-01T12:00", tz="UTC")
    after = pd.Timestamp("2026-08-03T12:00", tz="UTC")
    key = "2026-01-02"

    got_before = load_series(LIVE_DSN, [tag], as_of=before, data_version=run)
    got_after = load_series(LIVE_DSN, [tag], as_of=after, data_version=run)
    assert float(got_before.loc[key, tag]) == 2.0, "phai ra gia tri CU (con hieu luc)"
    assert float(got_after.loc[key, tag]) == 9.9, "sau khi revise phai ra gia tri MOI"

    # Tat co che -> quay ve loi cu: doc ban hom nay cho moi thoi diem.
    naive = load_series(LIVE_DSN, [tag], as_of=before, data_version=run,
                        revision_aware=False)
    assert float(naive.loc[key, tag]) == 9.9

    # Hang khong bi revise van ra dung o ca hai goc nhin.
    assert float(got_before.loc["2026-01-01", tag]) == 1.0
    assert float(got_after.loc["2026-01-01", tag]) == 1.0


@live_only
def test_as_of_does_not_filter_on_load_time(live):
    """Loi da mac mot lan: loc `loaded_at <= as_of` lam moi as_of truoc hom nay
    tra VE RONG (toan bo DB nap hom nay). `as_of` la dong ho NOI DUNG."""
    from gpr_engine.econometrics.dataset import load_series

    _, tag, run = live
    apply_snapshot(_frame(series=tag), LIVE_DSN, prefix=f"zztest_{tag}",
                   when=dt.date(2026, 8, 1), running_version=run)
    # du lieu co available_at 2026-01-01/02, nap HOM NAY -> van phai doc duoc
    got = load_series(LIVE_DSN, [tag], as_of="2026-06-30", data_version=run)
    assert len(got) == 2, "as_of truoc ngay nap ma tra rong -> nham hai dong ho"
