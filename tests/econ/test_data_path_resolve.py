"""Test `data_files.resolve_data_path` — P1.0 cua docs/17_master_plan.md §6.

Ly do co module nay: layout THAT trong data/ khac DEFAULT_* (nguoi van hanh tha
file tai tay theo cach cua ho — thuc te co `data/AI-GPRs/` va `data/GPR index/`
voi ban sao trinh duyet ` (1)`). Truoc khi co resolver,
tests/test_report_guard_p1.py fail vi khong mo duoc file.

Toan bo test dung tmp_path — KHONG phu thuoc noi dung data/ cua may dang chay.
"""
from __future__ import annotations

import pytest

from gpr_engine.econometrics.data_files import _stems_match, resolve_data_path


def test_duong_dan_dung_thi_tra_ve_nguyen_ban(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x")
    assert resolve_data_path(f) == f


def test_tim_trong_thu_muc_con(tmp_path):
    (tmp_path / "AI-GPRs").mkdir()
    real = tmp_path / "AI-GPRs" / "ai_gpr_data_daily.csv"
    real.write_text("x")
    got = resolve_data_path(tmp_path / "ai_gpr_data_daily.csv", search_root=tmp_path)
    assert got == real


def test_khop_ban_sao_trinh_duyet_co_canh_bao(tmp_path):
    """`data_gpr_daily_recent (1).xls` — ung vien DAI hon ten mac dinh."""
    (tmp_path / "GPR index").mkdir()
    real = tmp_path / "GPR index" / "data_gpr_daily_recent (1).xls"
    real.write_text("x")
    with pytest.warns(UserWarning, match="khop tien to"):
        got = resolve_data_path(tmp_path / "data_gpr_daily_recent.xls",
                                search_root=tmp_path)
    assert got == real


def test_khop_khi_ten_mac_dinh_co_hau_to_vintage(tmp_path):
    """`data_gpr_export (1).xls` vs DEFAULT `data_gpr_export_202607.xls`.

    Ung vien NGAN hon ten mac dinh — huong nguoc voi test tren. Truong hop nay
    ton tai that trong repo va la ly do quy tac khop phai DOI XUNG.
    """
    (tmp_path / "GPR index").mkdir()
    real = tmp_path / "GPR index" / "data_gpr_export (1).xls"
    real.write_text("x")
    with pytest.warns(UserWarning):
        got = resolve_data_path(tmp_path / "data_gpr_export_202607.xls",
                                search_root=tmp_path)
    assert got == real


def test_bo_qua_thu_muc_cache(tmp_path):
    """cache/ la thu muc GHI — do vao do se lay nham file cache lam nguon."""
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "ai_gpr_data_daily.csv").write_text("x")
    got = resolve_data_path(tmp_path / "ai_gpr_data_daily.csv", search_root=tmp_path)
    assert not got.exists()          # khong tim thay -> tra ve nguyen ban
    assert got.name == "ai_gpr_data_daily.csv"


def test_khong_tim_thay_thi_tra_ve_nguyen_ban(tmp_path):
    """Guard `.exists()` san co phai duoc chay, vi thong bao cua chung huong
    dan tai file — de resolver raise se nuot mat huong dan do."""
    p = tmp_path / "wui_global.csv"
    assert resolve_data_path(p, search_root=tmp_path) == p


def test_nhieu_file_cung_ten_thi_raise(tmp_path):
    """Tu chon mot ban = chon vintage ho nguoi dung (#7 ghim vintage)."""
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "ai_gpr_data_daily.csv").write_text("x")
    with pytest.raises(FileNotFoundError, match="cung ten"):
        resolve_data_path(tmp_path / "ai_gpr_data_daily.csv", search_root=tmp_path)


def test_nhieu_file_khop_tien_to_thi_raise(tmp_path):
    (tmp_path / "gpr (1).xls").write_text("x")
    (tmp_path / "gpr (2).xls").write_text("x")
    with pytest.raises(FileNotFoundError, match="khop tien"):
        resolve_data_path(tmp_path / "gpr.xls", search_root=tmp_path)


def test_khong_khop_khac_phan_mo_rong(tmp_path):
    (tmp_path / "data_gpr_export (1).csv").write_text("x")
    got = resolve_data_path(tmp_path / "data_gpr_export_202607.xls",
                            search_root=tmp_path)
    assert not got.exists()


@pytest.mark.parametrize("candidate,target,expected", [
    ("data_gpr_daily_recent (1)", "data_gpr_daily_recent", True),   # ban sao
    ("data_gpr_export (1)", "data_gpr_export_202607", True),        # hau to vintage
    ("x", "x", True),
    ("ai_gpr_country_monthly", "ai_gpr_data_monthly", False),       # KHAC nguon
    ("data_gpr_exp", "data_gpr_export", False),                     # cat giua token
])
def test_quy_tac_khop_ten(candidate, target, expected):
    assert _stems_match(candidate, target) is expected
    assert _stems_match(target, candidate) is expected      # doi xung
