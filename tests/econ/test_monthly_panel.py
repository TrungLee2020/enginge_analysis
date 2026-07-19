"""Test build_monthly_panel — track MONTHLY (docs/10 F3, #10 no-forward-fill).

Kiem chung cot loi (nguyen tac #10): panel monthly KHONG duoc forward-fill xuong
daily — moi hang la 1 THANG that. GPRC_VNM (monthly) chi vao track nay, KHONG vao
daily. GPRC_VNM di qua orthogonalize (bo phan GPR global) roi innovation -> λ.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as df_mod
from gpr_engine.econometrics.data_files import (
    align_monthly_gpr_to_information_time,
    build_monthly_panel,
)


def _fake_monthly(n: int = 200, seed: int = 0) -> pd.DataFrame:
    """GPR global + GPRC_VNM monthly gia, index dau thang."""
    idx = pd.date_range("2005-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(seed)
    gpr = 100 + rng.standard_normal(n).cumsum() * 3        # global, thang ~100
    # GPRC_VNM tuong quan mot phan voi GPR global + phan rieng
    vnm = 0.02 + 0.0003 * (gpr - 100) + np.abs(rng.standard_normal(n)) * 0.03
    return pd.DataFrame({"GPR": gpr, "GPRC_VNM": vnm}, index=idx)


def _fake_macro_monthly(n: int = 200) -> pd.DataFrame:
    idx = pd.date_range("2005-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "oil": rng.standard_normal(n) * 0.05,
        "vix": 20 + rng.standard_normal(n),
    }, index=idx)


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(df_mod, "load_gpr_monthly", lambda path=None: _fake_monthly())
    monkeypatch.setattr(df_mod, "load_macro_monthly", lambda *a, **k: _fake_macro_monthly())


def test_monthly_grid_not_daily(patched):
    """Index la dau thang lien tuc — KHONG no thanh daily (nguyen tac #10)."""
    panel = build_monthly_panel()
    # moi buoc cach nhau ~1 thang (28-31 ngay), khong phai 1 ngay
    deltas = panel.index.to_series().diff().dropna().dt.days
    assert deltas.min() >= 28, "co khoang cach < 28 ngay -> da bi no xuong daily (#10 vi pham)"
    assert deltas.max() <= 31
    # tat ca la ngay dau thang
    assert (panel.index.day == 1).all()


def test_no_forward_fill_no_duplicate_values(patched):
    """Khong forward-fill: khong co gia tri thang lap lai o nhieu hang lien tiep giả."""
    panel = build_monthly_panel()
    # so hang = so thang duy nhat (khong nhan ban)
    assert panel.index.is_unique
    assert len(panel) == panel.index.nunique()


def test_gprc_vnm_orthogonalized(patched):
    """GPRC_VNM vao panel la phan RIENG (⊥ GPR global) da innovation, khong phai tho."""
    panel = build_monthly_panel()
    assert "GPRC_VNM_ORTH_INNOV" in panel.columns
    # phan orthogonal khong con tuong quan manh voi GPR global innovation
    if "GPR_INNOV" in panel.columns:
        both = panel[["GPR_INNOV", "GPRC_VNM_ORTH_INNOV"]].dropna()
        if len(both) > 10:
            corr = np.corrcoef(both.iloc[:, 0], both.iloc[:, 1])[0, 1]
            assert abs(corr) < 0.5, f"GPRC_VNM_ORTH van tuong quan {corr:.2f} voi GPR global"


def test_has_global_shock_and_macro(patched):
    panel = build_monthly_panel()
    assert "GPR_INNOV" in panel.columns          # β global-direct monthly
    for m in ["oil", "vix"]:
        assert m in panel.columns


def test_complete_case_no_nan(patched):
    """Panel tra ve complete-case (khong NaN) de moi horizon dung cung mau."""
    panel = build_monthly_panel()
    assert not panel.isna().any().any()


def test_no_gprc_vnm_raw_column(patched):
    """GPRC_VNM THO khong duoc lo ra panel (chi ban orthogonalized+innovation)."""
    panel = build_monthly_panel()
    assert "GPRC_VNM" not in panel.columns, "GPRC_VNM tho khong duoc vao panel (#9: phai innovation)"


def test_monthly_gpr_is_used_in_next_month_bucket():
    """GPR tong hop thang M khong duoc coi la da biet tu dau thang M."""
    source = pd.Series(
        [1.0, 2.0],
        index=pd.DatetimeIndex(["2020-01-01", "2020-02-01"]),
        name="GPR_INNOV",
    )
    out = align_monthly_gpr_to_information_time(source)
    expected = pd.DatetimeIndex(["2020-02-01", "2020-03-01"])
    pd.testing.assert_index_equal(out.index, expected)
    assert out.loc["2020-02-01"] == 1.0
