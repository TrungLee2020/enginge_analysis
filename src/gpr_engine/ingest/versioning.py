"""versioning.py — nap lai file nguon MA KHONG mat ban cu. Dung chung moi ingest.

VAN DE THAT (do 2026-08-09 tren DB song, khong phai gia dinh):
    File GPR duoc tai lai dinh ky. So sanh vintage cu trong DB (het 2026-06-29)
    voi file moi (het 2026-08-03), phan CHONG LAP 45.465 hang:

        truoc 2025-03 : 0/44.007 hang doi     -> lich su sau DONG BANG that
        2025-03 tro di:   126/1.458 doi (8.6%)
        rieng 2026    :   108/540   doi (20%)

    42 NGAY bi tinh lai, giong het nhau o ca 3 series (GPRD/GPRD_ACT/GPRD_THREAT)
    -> Caldara-Iacoviello tinh lai tron ngay, KHONG phai sai so lam tron.
    Do lon: median |delta| = 42.9 diem tren gia tri ~300, max 130.7
    (GPRD_ACT 2026-06-24: 293.8 -> 163.1). Monthly: 520 gia tri doi, cung cua so.

HAI CACH SAI, va vi sao:
    "chi append ngay moi"   -> giu nguyen gia tri CU SAI o dung 15 thang gan nhat,
                              tuc cua so ma san pham quan tam nhat.
    "snapshot day du/lan"   -> chep 45.570 hang de giu 126 hang that su khac
                              (0,28%), va bat duong doc phai biet nhan moi nhat —
                              `load_series(data_version="v1")` mac dinh se doc
                              ban CU trong im lang.

CACH DUNG O DAY (mac dinh `mode="delta"`):
    - ban CHAY `running_version` (mac dinh "v1") luon la ban MOI NHAT: ngay moi
      append, gia tri bi revise duoc cap nhat + dong dau `revised_at`.
      => moi duong doc hien co (load_series mac dinh v1, service/store.py) van
         dung, KHONG doi default nao.
    - gia tri CU bi ghi de duoc CHEP sang mot nhan vintage rieng truoc khi ghi de
      => tai lap duoc "hom do ta biet gi", ton dung so hang that su doi.
    - moi lan nap ghi mot dong vao so `data_versions` (bang do truoc day CHUA co
      script nao ghi vao — sổ chết).

`mode="full"` giu them mot ban sao TOAN BO duoi nhan snapshot, cho ai muon vintage
tuyet doi. Ban chay van duoc cap nhat nhu tren nen duong doc khong doi.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import create_engine, text

RUNNING_VERSION = "v1"          # ban "moi nhat", trung default cua load_series
SNAPSHOT_MODES = ("delta", "full")

# Nguong coi hai gia tri la KHAC nhau. double precision di qua Postgres roi quay
# lai la bit-exact, nhung file nguon co the doi dinh dang so; 1e-9 tren thang do
# GPR (~0..600) la nhieu tuyet doi, khong che duoc revise that (median 42.9).
VALUE_EPS = 1e-9

_COLS = ["series_id", "date", "value", "freq", "source", "available_at",
         "source_version"]


@dataclass
class IngestReport:
    """Ket qua mot lan nap. In ra de NHIN THAY revise, thay vi de no chay ngam."""

    running_version: str
    archive_label: str
    snapshot_label: str | None
    n_incoming: int
    n_new: int = 0
    n_changed: int = 0
    n_unchanged: int = 0
    n_archived: int = 0
    n_snapshot: int = 0
    changed_range: tuple[str, str] | None = None
    changed_examples: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"data_version chay : {self.running_version}",
            f"  hang trong file : {self.n_incoming}",
            f"  ngay/series MOI : {self.n_new}",
            f"  gia tri BI REVISE: {self.n_changed}"
            + (f"  (tu {self.changed_range[0]} den {self.changed_range[1]})"
               if self.changed_range else ""),
            f"  khong doi       : {self.n_unchanged}",
            f"  archive ban cu  : {self.n_archived} hang -> `{self.archive_label}`"
            if self.n_archived else "  archive ban cu  : (khong co gi bi ghi de)",
        ]
        if self.snapshot_label:
            lines.append(f"  snapshot day du : {self.n_snapshot} hang -> "
                         f"`{self.snapshot_label}`")
        for ex in self.changed_examples:
            lines.append(f"    {ex['series_id']} {ex['date']}: "
                         f"{ex['old']:.4f} -> {ex['new']:.4f}")
        return "\n".join(lines)


def git_commit_short() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return None


def snapshot_label(prefix: str, when: dt.date | None = None) -> str:
    """Nhan vintage cua mot lan nap: `<prefix>_<YYYYMMDD>`.

    Cung ngay nap hai lan -> cung nhan -> UPSERT idempotent, khong sinh rac.
    """
    return f"{prefix}_{(when or dt.date.today()):%Y%m%d}"


def archive_label(prefix: str, when: dt.date | None = None) -> str:
    """Nhan chua ban CU bi ghi de trong lan nap do (`<prefix>_pre_<YYYYMMDD>`)."""
    return f"{prefix}_pre_{(when or dt.date.today()):%Y%m%d}"


def _register(conn, label: str, description: str) -> None:
    conn.execute(text("""
        INSERT INTO data_versions (label, description, git_commit)
        VALUES (:label, :description, :git_commit)
        ON CONFLICT (label) DO UPDATE
        SET description = EXCLUDED.description, git_commit = EXCLUDED.git_commit
    """), {"label": label, "description": description,
           "git_commit": git_commit_short()})


def apply_snapshot(long: pd.DataFrame, dsn: str, *, prefix: str,
                   description: str = "", mode: str = "delta",
                   running_version: str = RUNNING_VERSION,
                   when: dt.date | None = None,
                   n_examples: int = 5) -> IngestReport:
    """Nap `long` vao ext_series theo che do vintage. Xem docstring module.

    `long` phai co dung cac cot ma cac script ingest dang tao ra
    (series_id/date/value/freq/source/available_at/source_version); cot
    `data_version` neu co se bi BO QUA — nhan do ham nay quyet dinh.
    """
    if mode not in SNAPSHOT_MODES:
        raise ValueError(f"mode phai thuoc {SNAPSHOT_MODES}, nhan {mode!r}")
    missing = [c for c in _COLS if c not in long.columns]
    if missing:
        raise ValueError(f"`long` thieu cot: {missing}. Co: {list(long.columns)}")

    arch = archive_label(prefix, when)
    snap = snapshot_label(prefix, when) if mode == "full" else None
    rep = IngestReport(running_version=running_version, archive_label=arch,
                       snapshot_label=snap, n_incoming=len(long))
    if long.empty:
        return rep

    rows = long[_COLS].to_dict(orient="records")
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TEMP TABLE _incoming (
                series_id TEXT, date DATE, value DOUBLE PRECISION,
                freq VARCHAR(10), source TEXT, available_at TIMESTAMPTZ,
                source_version TEXT
            ) ON COMMIT DROP
        """))
        conn.execute(text("""
            INSERT INTO _incoming VALUES (:series_id, :date, :value, :freq,
                                          :source, :available_at, :source_version)
        """), rows)

        # --- Chot chan: mot series_id KHONG duoc mang hai tan suat ---------------
        # PK cua ext_series la (series_id, date, data_version), KHONG co `freq`.
        # Hai nguon khac tan suat ma dung chung series_id se ghi de lan nhau o moi
        # ngay trung (vd ngay dau thang) — AM THAM, vi gia tri thang thuong cung
        # thang do voi gia tri ngay. Da xay ra that voi AI-GPR (2026-08-09,
        # 11.186 hang). Bat o day de moi nguon TUONG LAI khong lap lai.
        clash = conn.execute(text("""
            SELECT DISTINCT i.series_id, e.freq AS freq_db, i.freq AS freq_moi
            FROM _incoming i
            JOIN ext_series e ON e.series_id = i.series_id
                             AND e.data_version = :rv
            WHERE e.freq IS DISTINCT FROM i.freq
            LIMIT 5
        """), {"rv": running_version}).mappings().all()
        if clash:
            detail = ", ".join(f"{c['series_id']} (DB={c['freq_db']}, "
                               f"moi={c['freq_moi']})" for c in clash)
            raise ValueError(
                f"series_id da ton tai voi TAN SUAT KHAC trong `{running_version}`: "
                f"{detail}. PK khong chua `freq` nen hai ban se ghi de lan nhau o "
                "moi ngay trung — dat ten series RIENG cho tung tan suat (quy uoc "
                "cua repo: GPRD daily vs GPR monthly).")

        # --- Phan loai TRUOC khi ghi (sau khi ghi thi khong con phan biet duoc) ---
        cls = conn.execute(text("""
            SELECT
              count(*) FILTER (WHERE e.series_id IS NULL)                     AS n_new,
              count(*) FILTER (WHERE e.series_id IS NOT NULL
                               AND abs(e.value - i.value) > :eps)             AS n_changed,
              count(*) FILTER (WHERE e.series_id IS NOT NULL
                               AND abs(e.value - i.value) <= :eps)            AS n_unchanged,
              min(i.date) FILTER (WHERE e.series_id IS NOT NULL
                                  AND abs(e.value - i.value) > :eps)          AS d0,
              max(i.date) FILTER (WHERE e.series_id IS NOT NULL
                                  AND abs(e.value - i.value) > :eps)          AS d1
            FROM _incoming i
            LEFT JOIN ext_series e
              ON e.series_id = i.series_id AND e.date = i.date
             AND e.data_version = :rv
        """), {"eps": VALUE_EPS, "rv": running_version}).mappings().one()
        rep.n_new, rep.n_changed = int(cls["n_new"]), int(cls["n_changed"])
        rep.n_unchanged = int(cls["n_unchanged"])
        if cls["d0"] is not None:
            rep.changed_range = (str(cls["d0"]), str(cls["d1"]))

        if rep.n_changed:
            ex = conn.execute(text("""
                SELECT i.series_id, i.date, e.value AS old, i.value AS new
                FROM _incoming i
                JOIN ext_series e ON e.series_id = i.series_id AND e.date = i.date
                                 AND e.data_version = :rv
                WHERE abs(e.value - i.value) > :eps
                ORDER BY abs(e.value - i.value) DESC
                LIMIT :lim
            """), {"rv": running_version, "eps": VALUE_EPS,
                   "lim": n_examples}).mappings().all()
            rep.changed_examples = [dict(r) for r in ex]

            # Ban CU sang nhan archive TRUOC khi UPSERT ghi de len no.
            rep.n_archived = conn.execute(text("""
                INSERT INTO ext_series (series_id, date, value, freq, source,
                                        available_at, revised_at, source_version,
                                        data_version)
                SELECT e.series_id, e.date, e.value, e.freq, e.source,
                       e.available_at, now(), e.source_version, :arch
                FROM ext_series e
                JOIN _incoming i ON i.series_id = e.series_id AND i.date = e.date
                WHERE e.data_version = :rv AND abs(e.value - i.value) > :eps
                ON CONFLICT (series_id, date, data_version) DO NOTHING
            """), {"arch": arch, "rv": running_version, "eps": VALUE_EPS}).rowcount
            _register(conn, arch,
                      f"{description} — ban CU bi ghi de khi nap "
                      f"{(when or dt.date.today()).isoformat()} "
                      f"({rep.n_changed} gia tri revise)")

        # --- Ban chay: ngay moi append, gia tri revise duoc cap nhat ---
        conn.execute(text("""
            INSERT INTO ext_series (series_id, date, value, freq, source,
                                    available_at, source_version, data_version)
            SELECT i.series_id, i.date, i.value, i.freq, i.source,
                   i.available_at, i.source_version, :rv
            FROM _incoming i
            ON CONFLICT (series_id, date, data_version) DO UPDATE
            SET value = EXCLUDED.value,
                available_at = EXCLUDED.available_at,
                -- freq/source cung phai cap nhat: ban cu de nguyen chung, mot
                -- hang bi ghi de boi nguon khac se NOI DOI ve tan suat cua chinh
                -- no (da thay o AI-GPR: value thang nam trong hang freq='daily').
                freq = EXCLUDED.freq,
                source = EXCLUDED.source,
                source_version = EXCLUDED.source_version,
                loaded_at = now(),
                revised_at = CASE
                    WHEN abs(ext_series.value - EXCLUDED.value) > :eps THEN now()
                    ELSE ext_series.revised_at END
        """), {"rv": running_version, "eps": VALUE_EPS})
        _register(conn, running_version,
                  f"{description} — ban CHAY (luon moi nhat). Cap nhat lan cuoi: "
                  f"{(when or dt.date.today()).isoformat()}")

        if snap:
            rep.n_snapshot = conn.execute(text("""
                INSERT INTO ext_series (series_id, date, value, freq, source,
                                        available_at, source_version, data_version)
                SELECT i.series_id, i.date, i.value, i.freq, i.source,
                       i.available_at, i.source_version, :snap
                FROM _incoming i
                ON CONFLICT (series_id, date, data_version) DO UPDATE
                SET value = EXCLUDED.value, loaded_at = now()
            """), {"snap": snap}).rowcount
            _register(conn, snap,
                      f"{description} — snapshot DAY DU luc nap "
                      f"{(when or dt.date.today()).isoformat()}")
    return rep


def add_version_args(ap) -> None:
    """Cac tham so vintage dung chung cho moi script ingest."""
    ap.add_argument("--snapshot", choices=list(SNAPSHOT_MODES), default="delta",
                    help="delta (mac dinh): chi archive gia tri CU bi ghi de. "
                         "full: giu them ban sao toan bo duoi nhan snapshot.")
    ap.add_argument("--running-version", default=RUNNING_VERSION,
                    help="nhan cua ban 'moi nhat' (mac dinh v1 — trung default "
                         "cua load_series)")
