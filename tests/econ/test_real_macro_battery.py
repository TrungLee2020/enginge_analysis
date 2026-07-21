"""Test outcome vĩ mô thực (IP/CPI/kỳ vọng lạm phát) + benchmark battery (EPU/WUI).

docs/14 §1.2 M1 và §2 mục 1a. Hai thứ này là cái biến sản phẩm từ "chỉ số rủi ro"
thành "đánh giá xu hướng kinh tế vĩ mô": cascade cũ dừng ở oil/dxy/vix/us10y/freight
(KÊNH truyền dẫn), SCA-01 đã đăng ký real_macro=[IP, CPI, infl_expectation] nhưng
chưa có loader.

Test THUẦN (không gọi mạng): monkeypatch loader raw, kiểm transform + tính chất
panel. Quy ước transform phải khớp E0 (100·Δln INDPRO) — nếu lệch thì bảng γ của
Phase 1a không so được với replication đã PASS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as df_mod
from gpr_engine.econometrics.data_files import (
    build_monthly_panel,
    transform_benchmark,
    transform_real_macro,
)


def _midx(n: int = 200) -> pd.DatetimeIndex:
    return pd.date_range("1990-01-01", periods=n, freq="MS")


# ---------------------------------------------------------------------------
# transform_real_macro — quy ước phải khớp E0
# ---------------------------------------------------------------------------
def test_ip_transform_is_100_dlog_like_e0():
    """ip = 100·Δln(INDPRO) — ĐÚNG transform E0 dùng để tái lập C-I 2022.

    E0 PASS với spec này (β=−0.37, h=2). Nếu loader dùng transform khác thì hệ số
    Phase 1a không so được với replication — mất luôn giá trị của cổng E0.
    """
    idx = _midx(5)
    raw = pd.DataFrame({"ip": [100.0, 101.0, 102.0, 101.0, 103.0]}, index=idx)
    out = transform_real_macro(raw)
    expected = 100.0 * np.log(101.0 / 100.0)
    assert out["ip"].iloc[1] == pytest.approx(expected)
    assert np.isnan(out["ip"].iloc[0]), "hàng đầu phải NaN (diff), không được fill 0"


def test_cpi_is_growth_and_infl_exp_is_difference():
    """cpi -> %/tháng (100·Δln); infl_exp -> SAI PHÂN, không phải mức (#9).

    infl_exp là mức khảo sát dai dẳng như us10y. Đưa mức vào hồi quy shock rồi gọi
    hệ số là 'phản ứng' là đúng cái lỗi #9 cấm.
    """
    idx = _midx(4)
    raw = pd.DataFrame({"cpi": [200.0, 202.0, 202.0, 204.0],
                        "infl_exp": [3.0, 3.2, 3.1, 3.5]}, index=idx)
    out = transform_real_macro(raw)
    assert out["cpi"].iloc[1] == pytest.approx(100.0 * np.log(202.0 / 200.0))
    assert out["infl_exp"].iloc[1] == pytest.approx(0.2)
    assert out["infl_exp"].iloc[3] == pytest.approx(0.4)
    # mức 3.0..3.5 KHÔNG được lọt vào cột đã transform
    assert out["infl_exp"].abs().max() < 1.0


def test_real_macro_transform_skips_missing_columns():
    """Thiếu cột nào bỏ cột đó — không bịa, không raise (battery có thể chạy thiếu)."""
    out = transform_real_macro(pd.DataFrame({"ip": [100.0, 101.0]}, index=_midx(2)))
    assert list(out.columns) == ["ip"]


# ---------------------------------------------------------------------------
# transform_benchmark — cùng quy ước log1p của GPR
# ---------------------------------------------------------------------------
def test_benchmark_uses_gpr_log1p_convention():
    """EPU/WUI cùng họ 'chỉ số đếm tin' với GPR -> dùng CHUNG log1p, không quy ước riêng."""
    idx = _midx(3)
    raw = pd.DataFrame({"epu_us": [100.0, 200.0, 50.0]}, index=idx)
    out = transform_benchmark(raw)
    assert out["epu_us"].iloc[0] == pytest.approx(np.log1p(100.0))
    assert list(out.columns) == ["epu_us"], "phải giữ nguyên tên cột"


# ---------------------------------------------------------------------------
# build_monthly_panel — tích hợp, giữ nguyên tắc #10
# ---------------------------------------------------------------------------
@pytest.fixture
def _fake_sources(monkeypatch):
    """Giả lập mọi nguồn ngoài: GPR monthly, macro tài chính, real macro, battery."""
    rng = np.random.default_rng(7)
    # PHẢI phủ dev window chọn AR order (2015-01..2020-12, shocks.DEV_WINDOW) —
    # mẫu ngắn hơn thì select_ar_order raise "0 quan sat".
    idx = _midx(430)                                   # 1990-01 → 2025-10
    n = len(idx)

    # Dựng SẴN mọi frame rồi mới patch. Nếu để lambda gọi rng lúc chạy thì hai lần
    # build_monthly_panel() nhận macro KHÁC NHAU (rng có trạng thái) — test so sánh
    # hai nước sẽ đỏ vì lý do giả.
    gpr = pd.Series(np.abs(rng.normal(100, 30, n)), index=idx)
    vnm = pd.Series(np.abs(0.3 * gpr / 100 + rng.normal(0.05, 0.04, n)), index=idx)
    gpr_frame = pd.DataFrame(
        {"GPR": gpr, "GPRC_VNM": vnm, "GPRC_POL": vnm * 1.7}, index=idx)
    macro_frame = pd.DataFrame(
        {c: rng.normal(0, 1, n) for c in ("oil", "dxy", "vix", "us10y")}, index=idx)
    # raw MỨC — build_monthly_panel phải tự transform, không nhận sẵn Δ
    real_frame = pd.DataFrame(
        {"ip": 100 * np.exp(np.cumsum(rng.normal(0.002, 0.005, n))),
         "cpi": 200 * np.exp(np.cumsum(rng.normal(0.002, 0.003, n))),
         "infl_exp": 3 + np.cumsum(rng.normal(0, 0.05, n))}, index=idx)
    battery_frame = pd.DataFrame(
        {"epu_us": np.abs(rng.normal(120, 40, n)),
         "epu_global": np.abs(rng.normal(150, 50, n))}, index=idx)

    monkeypatch.setattr(df_mod, "load_gpr_monthly", lambda path=None, **kw: gpr_frame)
    monkeypatch.setattr(df_mod, "load_macro_monthly", lambda *a, **k: macro_frame)
    monkeypatch.setattr(df_mod, "load_real_macro_monthly", lambda *a, **k: real_frame)
    monkeypatch.setattr(df_mod, "load_benchmark_monthly", lambda *a, **k: battery_frame)
    return idx


def test_panel_real_macro_adds_outcomes_and_stays_monthly(_fake_sources):
    """real_macro=True thêm ip/cpi/infl_exp, grid VẪN là đầu tháng thật (#10)."""
    panel = build_monthly_panel(real_macro=True)
    for c in ("ip", "cpi", "infl_exp"):
        assert c in panel.columns
    assert (panel.index.day == 1).all(), "grid phải là đầu tháng, không ffill từ daily"
    # giá trị đã transform: tăng trưởng %/tháng nhỏ, không phải mức chỉ số ~100
    assert panel["ip"].abs().max() < 20, "ip phải là 100·Δln, không phải mức INDPRO"
    assert panel["cpi"].abs().max() < 20


def test_panel_battery_adds_controls_at_level(_fake_sources):
    """battery=True thêm epu_* dạng log1p LEVEL (control benchmark, docs/14 1a-b)."""
    panel = build_monthly_panel(battery=True)
    for c in ("epu_us", "epu_global"):
        assert c in panel.columns
    # log1p của chỉ số ~120 => ~4.8; nếu ai đó quên transform thì trị số sẽ ~120
    assert panel["epu_us"].max() < 10, "battery phải qua log1p, không đưa mức thô"


def test_panel_country_switch_changes_only_lambda_column(_fake_sources):
    """Đổi nước chỉ đổi cột λ — tầng 1-2 là ENGINE generic (#8), không đổi theo nước.

    Đây là điều kiện của Phase 1b docs/14 §2: cascade chạy thử trên nước pilot mà
    KHÔNG được đụng vào phần country-agnostic.
    """
    vn = build_monthly_panel(country="VNM")
    pl = build_monthly_panel(country="POL")
    assert "GPRC_VNM_ORTH_INNOV" in vn.columns
    assert "GPRC_POL_ORTH_INNOV" in pl.columns
    assert "GPRC_VNM_ORTH_INNOV" not in pl.columns
    # cột generic phải trùng khít giá trị giữa hai nước
    shared = ["oil", "dxy", "vix", "us10y", "GPR_INNOV"]
    pd.testing.assert_frame_equal(vn[shared], pl[shared])


def test_panel_never_leaks_raw_country_gpr(_fake_sources):
    """GPRC_<c> THÔ không được lọt vào panel với bất kỳ nước nào (#9)."""
    pl = build_monthly_panel(country="POL", real_macro=True, battery=True)
    assert "GPRC_POL" not in pl.columns
    assert "GPR" not in pl.columns


def test_unknown_country_error_lists_available(monkeypatch, tmp_path):
    """Mã nước sai -> báo lỗi CÓ liệt kê mã hợp lệ, không chỉ 'KeyError'."""
    import pandas as _pd
    fake = _pd.DataFrame({"month": _pd.date_range("1990-01-01", periods=3, freq="MS"),
                          "GPR": [1.0, 2.0, 3.0], "GPRC_VNM": [0.1, 0.2, 0.3],
                          "GPRC_POL": [0.4, 0.5, 0.6]})
    monkeypatch.setattr(df_mod.pd, "read_excel", lambda *a, **k: fake)
    with pytest.raises(ValueError, match="GPRC_XXX"):
        df_mod.load_gpr_monthly("dummy.xls", country="XXX")
    try:
        df_mod.load_gpr_monthly("dummy.xls", country="XXX")
    except ValueError as e:
        assert "GPRC_POL" in str(e), "phải liệt kê các mã có sẵn để người dùng sửa được"
