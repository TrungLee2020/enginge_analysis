"""Test cước vận tải biển (docs/11 §5.3) — biến tầng 2 monthly, transform Δln.

Freight PPI (deep sea freight, FRED PCU483111483111) là CHỈ SỐ GIÁ monthly → Δln
(như oil/dxy). Nguồn monthly nên vào track THÁNG (build_monthly_panel), KHÔNG daily
(tránh forward-fill #10). Test phần PURE (transform) + panel có cột freight.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpr_engine.econometrics import data_files as df_mod
from gpr_engine.econometrics.data_files import build_monthly_panel, transform_freight


def test_transform_freight_dln():
    """Freight (mức giá) -> Δln. Kiểm giá trị + không NaN giữa chuỗi."""
    idx = pd.date_range("2010-01-01", periods=5, freq="MS")
    raw = pd.Series([100.0, 110, 121, 121, 100], index=idx, name="freight")
    out = transform_freight(raw)
    assert out.name == "freight"
    assert np.isnan(out.iloc[0])                              # kỳ đầu không có return
    assert abs(out.iloc[1] - np.log(110 / 100)) < 1e-9        # Δln kỳ 2
    assert abs(out.iloc[2] - np.log(121 / 110)) < 1e-9


def test_freight_in_monthly_panel(monkeypatch):
    """build_monthly_panel(freight=True) có cột 'freight', vẫn monthly grid (#10)."""
    n = 200
    midx = pd.date_range("2005-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(0)
    gpr = 100 + rng.standard_normal(n).cumsum() * 3
    vnm = 0.02 + 0.0003 * (gpr - 100) + np.abs(rng.standard_normal(n)) * 0.03
    fake_gpr = pd.DataFrame({"GPR": gpr, "GPRC_VNM": vnm}, index=midx)
    fake_macro = pd.DataFrame({
        "oil": rng.standard_normal(n) * 0.05,
        "vix": 20 + rng.standard_normal(n),
    }, index=midx)
    # freight raw (mức giá) — loader trả về mức, build_monthly_panel transform
    fake_freight = pd.Series(500 + rng.standard_normal(n).cumsum(), index=midx, name="freight")

    monkeypatch.setattr(df_mod, "load_gpr_monthly", lambda path=None, **kw: fake_gpr)
    monkeypatch.setattr(df_mod, "load_macro_monthly", lambda *a, **k: fake_macro)
    monkeypatch.setattr(df_mod, "load_freight_monthly", lambda *a, **k: fake_freight)

    panel = build_monthly_panel(freight=True)
    assert "freight" in panel.columns
    # vẫn monthly grid
    deltas = panel.index.to_series().diff().dropna().dt.days
    assert deltas.min() >= 28 and deltas.max() <= 31
    assert not panel.isna().any().any()


def test_monthly_panel_without_freight_unchanged(monkeypatch):
    """freight=False (mặc định) -> panel KHÔNG có cột freight (không phá bản cũ)."""
    n = 200                                   # đủ phủ dev window 2015-2020 cho select_ar_order
    midx = pd.date_range("2005-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(1)
    gpr = 100 + rng.standard_normal(n).cumsum() * 3
    vnm = 0.02 + np.abs(rng.standard_normal(n)) * 0.03
    monkeypatch.setattr(df_mod, "load_gpr_monthly",
                        lambda path=None, **kw: pd.DataFrame({"GPR": gpr, "GPRC_VNM": vnm}, index=midx))
    monkeypatch.setattr(df_mod, "load_macro_monthly",
                        lambda *a, **k: pd.DataFrame({"oil": rng.standard_normal(n) * 0.05,
                                                      "vix": 20 + rng.standard_normal(n)}, index=midx))
    panel = build_monthly_panel()
    assert "freight" not in panel.columns
