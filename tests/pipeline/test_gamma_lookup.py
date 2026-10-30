"""Test pipeline.gamma_lookup — doc bang gamma da cong bo, loc theo channel."""
from __future__ import annotations

import pytest

from gpr_engine.pipeline.gamma_lookup import (
    commitment_to_gamma_channel,
    load_published_gamma,
)

CSV_HEADER = ("measure,channel,outcome,family,battery,horizon,beta,se,tstat,"
             "pvalue,ci_low,ci_high,ci_low_supt,ci_high_supt,supt_c,nobs,"
             "converged,rank,threshold,pvalue_adj,reject,family_size")
ROWS = [
    # sống sót: reject=True, battery=b, channel=act
    "LEVEL,act,oil,asset_price,b,1,0.5,0.1,5.0,0.01,0.3,0.7,0.25,0.75,2.8,224,True,1.0,0.01,0.02,True,4.0",
    # sống sót: reject=True, battery=b, channel=threat
    "INNOVATION,threat,vix,asset_price,b,2,-0.2,0.05,-4.0,0.02,-0.3,-0.1,-0.35,-0.05,2.8,224,True,1.0,0.01,0.03,True,4.0",
    # KHONG song sot: reject=False -> loai
    "LEVEL,act,dxy,asset_price,b,1,0.05,0.09,0.5,0.5,-0.1,0.2,-0.2,0.3,2.8,224,True,2.0,0.03,0.9,False,4.0",
    # battery=a (khong phai b) -> loai theo quy uoc run_brief_demo
    "LEVEL,act,us10y,asset_price,a,1,0.9,0.1,9.0,0.001,0.7,1.1,0.6,1.2,2.8,224,True,1.0,0.01,0.001,True,4.0",
    # channel=pooled, sống sót
    "LEVEL_PLUS_JUMP,pooled,ip,real_macro,b,3,-0.4,0.1,-4.0,0.01,-0.6,-0.2,-0.65,-0.15,2.8,224,True,1.0,0.01,0.02,True,4.0",
]


@pytest.fixture
def gamma_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "t2_full_holm_testversion.csv").write_text(
        CSV_HEADER + "\n" + "\n".join(ROWS) + "\n", encoding="utf-8")
    return tmp_path


def test_commitment_mapping():
    assert commitment_to_gamma_channel("announced_action") == "act"
    assert commitment_to_gamma_channel("conditional") == "threat"
    assert commitment_to_gamma_channel("rhetoric") == "threat"
    with pytest.raises(ValueError):
        commitment_to_gamma_channel("bogus")


def test_filters_by_channel_and_survival(gamma_dir):
    cells, fname = load_published_gamma("act", reports_dir=gamma_dir)
    assert fname == "t2_full_holm_testversion.csv"
    # chi 1 hang act song sot (dxy bi loai vi reject=False)
    assert len(cells) == 1
    assert cells[0].outcome.startswith("oil")
    assert cells[0].survived_holm and cells[0].survived_battery


def test_threat_and_pooled_channels_isolated(gamma_dir):
    threat_cells, _ = load_published_gamma("threat", reports_dir=gamma_dir)
    pooled_cells, _ = load_published_gamma("pooled", reports_dir=gamma_dir)
    assert len(threat_cells) == 1 and threat_cells[0].outcome.startswith("vix")
    assert len(pooled_cells) == 1 and pooled_cells[0].outcome.startswith("ip")


def test_outcome_filter(gamma_dir):
    cells, _ = load_published_gamma("act", outcomes={"dxy"}, reports_dir=gamma_dir)
    assert cells == []  # dxy khong song sot -> rong, khong loi


def test_no_panel_means_standardized_equals_beta(gamma_dir):
    cells, _ = load_published_gamma("act", reports_dir=gamma_dir)
    assert cells[0].standardized == cells[0].beta


def test_invalid_channel_raises(gamma_dir):
    with pytest.raises(ValueError, match="không thuộc"):
        load_published_gamma("energy", reports_dir=gamma_dir)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_published_gamma("act", reports_dir=tmp_path)


def _two_tables(tmp_path):
    """Hai bang: file CU co mtime MOI HON (dung kich ban clone/COPY Docker:
    mtime = thu tu checkout, khong phai thoi diem tao bang)."""
    import os

    d = tmp_path / "data"
    d.mkdir()
    pinned = d / "t2_full_holm_aaa_pinned.csv"
    stale = d / "t2_full_holm_zzz_stale.csv"
    pinned.write_text(CSV_HEADER + "\n" + ROWS[0] + "\n", encoding="utf-8")
    stale_row = ROWS[0].replace(",oil,", ",vix,")
    stale.write_text(CSV_HEADER + "\n" + stale_row + "\n", encoding="utf-8")
    os.utime(pinned, (1_000_000_000, 1_000_000_000))
    os.utime(stale, (2_000_000_000, 2_000_000_000))  # stale "moi" hon theo mtime
    return pinned, stale


def test_several_tables_without_pin_raise_instead_of_picking_by_mtime(tmp_path, monkeypatch):
    """Bug da va (pre-deploy 2026-10-30): ban cu chon max(st_mtime). Trong
    git co 3 file t2_full_holm_*.csv; tren clone moi / COPY cua Docker, mtime
    la thu tu checkout -> co the phuc vu bang gamma CU ma khong dau hieu gi.
    Nhieu file + khong ghim = raise, khong doan."""
    monkeypatch.delenv("GPR_GAMMA_FILE", raising=False)
    _two_tables(tmp_path)
    with pytest.raises(RuntimeError, match="GPR_GAMMA_FILE"):
        load_published_gamma("act", reports_dir=tmp_path)


def test_pin_by_env_wins_over_mtime(tmp_path, monkeypatch):
    pinned, _ = _two_tables(tmp_path)
    monkeypatch.setenv("GPR_GAMMA_FILE", pinned.name)
    cells, fname = load_published_gamma("act", reports_dir=tmp_path)
    assert fname == pinned.name
    assert cells[0].outcome.startswith("oil")


def test_pin_by_argument_wins_over_env(tmp_path, monkeypatch):
    pinned, stale = _two_tables(tmp_path)
    monkeypatch.setenv("GPR_GAMMA_FILE", stale.name)
    _, fname = load_published_gamma("act", reports_dir=tmp_path,
                                    gamma_file=pinned.name)
    assert fname == pinned.name


def test_explicit_pin_missing_raises(tmp_path, monkeypatch):
    _two_tables(tmp_path)
    monkeypatch.setenv("GPR_GAMMA_FILE", "t2_full_holm_nope.csv")
    with pytest.raises(FileNotFoundError, match="nope"):
        load_published_gamma("act", reports_dir=tmp_path)


def test_default_pin_exists_in_repo_and_is_served(monkeypatch):
    """Bang gamma ghim mac dinh phai co trong repo — va duoc chon du cac
    bang khac co mtime moi hon."""
    from pathlib import Path

    from gpr_engine.pipeline.gamma_lookup import (
        DEFAULT_GAMMA_FILE,
        DEFAULT_REPORTS_DIR,
    )
    monkeypatch.delenv("GPR_GAMMA_FILE", raising=False)
    root = Path(__file__).resolve().parents[2]
    reports = root / DEFAULT_REPORTS_DIR
    assert (reports / "data" / DEFAULT_GAMMA_FILE).is_file()
    _, fname = load_published_gamma("pooled", reports_dir=reports)
    assert fname == DEFAULT_GAMMA_FILE
