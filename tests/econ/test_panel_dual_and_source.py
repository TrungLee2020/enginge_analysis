"""Panel thang: spec kep (P1.5) + doi nguon shock (P1.3).

docs/17_master_plan.md §6 Phase 1 — hai lo hong chan 1a:
  - `estimate_tier2` khong the chay spec kep neu panel khong co cot
    ANTICIPATED/SURPRISE;
  - khong doi duoc nguon shock thi khong chay duoc "ba ban" (GPR goc / AI-GPR /
    IV) de do attenuation.

⚠️ Macro bi TIEM GIA o day. Khong phai de chay nhanh: `fred.stlouisfed.org` bi
CHAN o egress policy cua sandbox (403 tren CONNECT, cung nhom voi
matteoiacoviello.com). Phan GPR — thu doi tuong dang test — van doc FILE THAT
trong data/.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as D


@pytest.fixture
def fake_macro(monkeypatch):
    """Macro thang gia, deterministic, phu rong hon panel GPR."""
    def _fake(start="1985-01-01", end=None, cache_dir=None, refresh=False, how="last"):
        idx = pd.date_range("1985-01-01", "2026-07-01", freq="MS")
        rng = np.random.default_rng(0)
        return pd.DataFrame(
            {c: rng.normal(0, 1, len(idx)) for c in ("oil", "dxy", "vix", "us10y")},
            index=idx)
    monkeypatch.setattr(D, "load_macro_monthly", _fake)


def test_dual_component_them_dung_hai_cot(fake_macro):
    p = D.build_monthly_panel(dual_component=True, start="1990-01-01")
    assert "GPR_ANTICIPATED" in p.columns
    assert "GPR_SURPRISE" in p.columns
    # Khong bat cot cua ACT/THREAT khi components=False.
    assert "GPR_ACT_SURPRISE" not in p.columns


def test_dual_component_voi_components_du_bon_regressor(fake_macro):
    """Spec 4 regressor threat/act cua §4.1."""
    p = D.build_monthly_panel(dual_component=True, components=True, start="1990-01-01")
    for c in ("GPR_ACT_ANTICIPATED", "GPR_ACT_SURPRISE",
              "GPR_THREAT_ANTICIPATED", "GPR_THREAT_SURPRISE"):
        assert c in p.columns, c


def test_mac_dinh_khong_doi_panel_cu(fake_macro):
    """Them tham so moi KHONG duoc doi ban mac dinh — report cu phai tai lap."""
    base = D.build_monthly_panel(start="1990-01-01")
    assert not any("ANTICIPATED" in c or "SURPRISE" in c for c in base.columns)
    assert "GPR_INNOV" in base.columns


def test_var_anticipated_nho_hon_nhieu_so_voi_surprise(fake_macro):
    """Ly do `standardized_contribution` la BAT BUOC, kiem tren du lieu that.

    Neu ty le nay ~1 thi so sanh he so tho moi vo hai. Tren chuoi that no lech
    han — dung canh bao cua E2 (48.9% o dao chieu sau chuan hoa).
    """
    p = D.build_monthly_panel(dual_component=True, start="1990-01-01")
    ratio = p["GPR_ANTICIPATED"].var() / p["GPR_SURPRISE"].var()
    assert ratio < 0.5, f"Var(ANT)/Var(SUR)={ratio:.3f} — kiem lai E2"


def test_shock_source_ai_gpr_doi_chuoi_giu_nguyen_ten_cot(fake_macro):
    p = D.build_monthly_panel(shock_source="ai_gpr", dual_component=True,
                              start="1990-01-01")
    assert "GPR_SURPRISE" in p.columns          # ten cot KHONG doi theo nguon
    assert "GPRC_VNM_ORTH_INNOV" in p.columns   # cot nuoc van con


def test_hai_nguon_cho_chuoi_KHAC_nhau(fake_macro):
    """Chan loi im lang: neu nhanh ai_gpr bi bo qua, hai panel se giong het."""
    a = D.build_monthly_panel(shock_source="gpr_ci", start="1990-01-01")
    b = D.build_monthly_panel(shock_source="ai_gpr", start="1990-01-01")
    common = a.index.intersection(b.index)
    assert len(common) > 100
    corr = a.loc[common, "GPR_INNOV"].corr(b.loc[common, "GPR_INNOV"])
    assert abs(corr) < 0.99, "hai nguon ra chuoi gan nhu trung nhau — kiem lai"


def test_shock_source_khong_hop_le_thi_raise(fake_macro):
    with pytest.raises(ValueError, match="shock_source"):
        D.build_monthly_panel(shock_source="khong_ton_tai", start="1990-01-01")


def test_dong_nhat_thuc_anticipated_cong_surprise(fake_macro):
    """ANT + SUR = ĐÚNG Δ LEVEL — tinh chat khoa cua delta_decomposition, kiem
    lai o cap PANEL de chac chan align information-time khong pha no."""
    from gpr_engine.econometrics.dataset import log1p_gpr
    from gpr_engine.econometrics.shocks import delta_decomposition

    gpr = D.load_gpr_monthly(country="VNM")["GPR"].loc["1990-01-01":]
    comp = delta_decomposition(gpr.rename("GPR")).dropna()
    dlevel = log1p_gpr(gpr).diff().reindex(comp.index)
    recon = comp["GPR_ANTICIPATED"] + comp["GPR_SURPRISE"]
    assert np.allclose(recon.values, dlevel.values, atol=1e-10)
