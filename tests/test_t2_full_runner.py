"""Test runner Phase 1a (`scripts/run_t2_full.py`) — bảng γ tầng 2 track tháng.

Không chạy pipeline thật (mất ~5 phút + cần FRED): test các BẤT BIẾN của runner
trên payload nhỏ tự dựng.

  - Guard P1: mọi số trong narrative truy về `stats` (docs/12 §5.4);
  - spec khóa khớp registry (focal horizons, họ Holm, inference);
  - Holm áp TRONG họ và CHỈ tại focal horizons (không quét 25 horizon — sup-t đã
    lo chiều đó, phạt lại là mất hết power);
  - ô phân vị không hội tụ KHÔNG được in số.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_t2_full as t2  # noqa: E402

from gpr_engine.econometrics.multiplicity import (  # noqa: E402
    PREREGISTERED_OUTCOME_FAMILIES,
)

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Hằng số cấu hình được phép có mặt trong narrative (ngưỡng/mốc/nhãn mô tả).
CONFIG_NUMBERS = {
    0.10, 0.90, 1.0, 2.0, 6.0, 100.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0,
    0.25, 0.50, 0.75, 25.0, 24.0, 0.05, 1997.0,
}


@pytest.fixture
def families() -> dict:
    return {k: tuple(v) for k, v in PREREGISTERED_OUTCOME_FAMILIES.items()}


def _fake_gamma(families: dict) -> pd.DataFrame:
    """Bảng γ giả: đủ chiều, giá trị đánh dấu, p-value tăng dần để Holm có việc."""
    rows = []
    rng = np.random.default_rng(0)
    for measure in t2.SHOCK_MEASURES:
        for chan in t2.CHANNELS:
            for battery in ("a", "b"):
                for fam, outs in families.items():
                    for out in outs:
                        for h in t2.HORIZONS:
                            p = float(np.clip(rng.uniform(0.001, 0.9), 0, 1))
                            rows.append(dict(
                                measure=measure, channel=chan, outcome=out,
                                family=fam, battery=battery, horizon=h,
                                beta=rng.normal(), se=0.1, tstat=1.0, pvalue=p,
                                ci_low=-0.1, ci_high=0.1,
                                ci_low_supt=-0.2, ci_high_supt=0.2,
                                supt_c=2.7, nobs=231, converged=True))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Spec khóa — phải khớp registry
# ---------------------------------------------------------------------------
def test_focal_horizons_match_locked_registry():
    """Focal horizons của runner = SCA-01.primary_cell.focal_horizons đã khóa."""
    from tests.test_registry_locked import LOCKED_MONTHLY_FOCAL_HORIZONS
    assert list(t2.FOCAL_HORIZONS) == LOCKED_MONTHLY_FOCAL_HORIZONS


def test_runner_uses_lag_augmented_per_signed_decision():
    """LEVEL/LEVEL+JUMP chỉ eligible với lag_augmented — runner phải dùng nó.

    Nếu ai đổi INFERENCE về 'hac', hai phần ba trục SHOCK thành INELIGIBLE và
    bảng γ không còn là cái mà quyết định A mô tả.
    """
    from gpr_engine.econometrics.shock_axis import eligible_measures
    assert t2.INFERENCE == "lag_augmented"
    assert set(eligible_measures(t2.INFERENCE)) == set(t2.SHOCK_MEASURES)


def test_families_come_from_registry_not_invented(families):
    assert set(families) == set(PREREGISTERED_OUTCOME_FAMILIES)


# ---------------------------------------------------------------------------
# Holm: trong họ, chỉ focal horizons
# ---------------------------------------------------------------------------
def test_holm_only_at_focal_horizons(families):
    gamma = _fake_gamma(families)
    holm = t2.apply_holm(gamma, families)
    assert set(holm["horizon"]) == set(t2.FOCAL_HORIZONS), (
        "Holm quét ngoài focal horizons — chiều horizon đã do sup-t xử lý, "
        "phạt lại là mất hết power (docs/14 §1.3).")
    n_outcomes = sum(len(v) for v in families.values())
    expected = (len(t2.SHOCK_MEASURES) * len(t2.CHANNELS) * 2
                * len(t2.FOCAL_HORIZONS) * n_outcomes)
    assert len(holm) == expected


def test_holm_family_sizes_are_4_3_1(families):
    """Cỡ họ 4/3/1 — đúng bảng B của docs/14 §6.6."""
    gamma = _fake_gamma(families)
    holm = t2.apply_holm(gamma, families)
    sizes = holm.groupby("family")["family_size"].first().to_dict()
    assert sizes == {"asset_price": 4.0, "real_macro": 3.0, "physical_channel": 1.0}


def test_holm_is_conservative_relative_to_raw(families):
    """Số sống sót Holm không bao giờ vượt số p thô < α."""
    gamma = _fake_gamma(families)
    holm = t2.apply_holm(gamma, families)
    assert int(holm["reject"].sum()) <= int((holm["pvalue"] < t2.ALPHA).sum())


# ---------------------------------------------------------------------------
# Guard P1 — mọi số trong narrative từ payload
# ---------------------------------------------------------------------------
def _allowed_values(stats: dict) -> set[float]:
    vals = set(CONFIG_NUMBERS)
    for v in stats.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            x = float(v)
            vals.add(round(x, 4))
            vals.add(round(x * 100, 4))
            vals.add(float(int(x)) if x == int(x) else x)
    return vals


def _tokens(parts: list[str]) -> list[str]:
    """Token số trong narrative, bỏ phần KHÔNG phải số kết quả."""
    # Bảng γ/phân vị là dữ liệu in ra từ DataFrame — guard soi phần văn xuôi.
    text = "\n".join(p for p in parts if not p.lstrip().startswith("|"))
    text = re.sub(r"`[0-9a-f]{6,}`", "", text)              # hash
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T0-9:]*", "", text)    # ngày ISO
    text = re.sub(r"docs/\d+", "", text)
    text = re.sub(r"§\s*[\d.]+", "", text)
    text = re.sub(r"DEC-\d{4}-\d{2}-\d{2}[\w-]*", "", text)  # id quyết định
    text = re.sub(r"[A-Za-zĐ]+-?\d[\w-]*", "", text)         # SCA-01, MO-PM 2021, US10Y
    text = re.sub(r"(?<![.\d])\d{4}(?![.\d])", "", text)     # mốc năm
    return NUM_RE.findall(text)


def _fake_raw_panel() -> pd.DataFrame:
    """Panel CHUA complete-case: mot cot bat dau muon hon -> rang buoc dau mau."""
    idx = pd.date_range("1990-01-01", periods=300, freq="MS")
    out = pd.DataFrame({"oil": np.arange(300, dtype=float),
                        "GPR_LEVEL": np.arange(300, dtype=float),
                        "epu_global_LEVEL": np.arange(300, dtype=float)},
                       index=idx)
    out.loc[out.index < "1997-01-01", "epu_global_LEVEL"] = np.nan
    out.loc[out.index < "1990-06-01", "GPR_LEVEL"] = np.nan
    return out


def _payload(families: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    gamma = _fake_gamma(families)
    holm = t2.apply_holm(gamma, families)
    panel = pd.DataFrame(np.zeros((231, 3)),
                         index=pd.date_range("2007-02-01", periods=231, freq="MS"))
    cost = t2.sample_cost(_fake_raw_panel(), "1990-01-01")
    stats = t2.compute_stats(panel, gamma, holm, None, families, elapsed=12.3,
                             cost=cost)
    return stats, holm, gamma


def test_every_number_in_narrative_comes_from_payload(families):
    stats, holm, gamma = _payload(families)
    meta = {"data_version": "deadbeefcafe", "git_commit": "abc1234",
            "generated_at": "2026-08-02T10:00:00", "panel_start": "2007-02-01",
            "panel_end": "2026-06-01", "real_macro_vintage": "aaa111bbb222",
            "freight_vintage": "ccc333ddd444", "benchmark_vintage": "eee555fff666"}
    parts = t2.build_report(stats, holm, gamma, None, families, meta)
    allowed = _allowed_values(stats)
    bad = [t for t in _tokens(parts)
           if round(float(t), 4) not in allowed
           and float(int(float(t))) not in allowed]
    assert not bad, (
        f"Số trong narrative KHÔNG khớp payload (Guard P1 vi phạm): {bad}. "
        "Thêm số vào report thì thêm trường vào `stats` rồi tham chiếu.")


def test_guard_catches_hardcoded_number(families):
    """Chứng minh guard bắt được số bịa — nếu không thì test trên vô nghĩa."""
    stats, holm, gamma = _payload(families)
    meta = {"data_version": "deadbeefcafe", "git_commit": "abc1234",
            "generated_at": "2026-08-02T10:00:00", "panel_start": "2007-02-01",
            "panel_end": "2026-06-01", "real_macro_vintage": "a", "freight_vintage": "b",
            "benchmark_vintage": "c"}
    parts = t2.build_report(stats, holm, gamma, None, families, meta)
    parts.append("Hệ số mạnh gấp 37.42 lần baseline.")   # số bịa
    allowed = _allowed_values(stats)
    bad = [t for t in _tokens(parts)
           if round(float(t), 4) not in allowed
           and float(int(float(t))) not in allowed]
    assert "37.42" in bad


# ---------------------------------------------------------------------------
# Hội tụ: ô không hội tụ không được in số
# ---------------------------------------------------------------------------
def _quant_rows(converged_at: set[float]) -> pd.DataFrame:
    return pd.DataFrame([
        dict(measure="LEVEL", channel="pooled", outcome="freight",
             family="physical_channel", battery="b", tau=tau, horizon=1,
             beta=999.0, se=1.0, pvalue=0.001, ci_low=0.0, ci_high=1.0,
             nobs=231, converged=(tau in converged_at))
        for tau in t2.TAUS])


def test_non_converged_quantile_cell_is_blanked():
    """QuantReg không hội tụ -> statsmodels trả hệ số vòng lặp cuối. Không in."""
    md = t2.quantile_table_md(_quant_rows(converged_at=set()), "LEVEL")
    assert "‡" in md, "ô không hội tụ phải được đánh dấu ‡"
    assert "999" not in md, "hệ số của fit không hội tụ KHÔNG được in ra bảng"


def test_converged_quantile_cell_still_prints():
    """Mặt còn lại: ô hội tụ VẪN in số — nếu không thì bảng trống trơn vô dụng."""
    md = t2.quantile_table_md(_quant_rows(converged_at=set(t2.TAUS)), "LEVEL")
    assert "‡" not in md
    assert md.count("+999.000") == len(t2.TAUS)


# ---------------------------------------------------------------------------
# Chi phi mau + dang control battery
# ---------------------------------------------------------------------------
def test_sample_binding_report_finds_the_late_column():
    """Cot bat dau muon nhat phai dung dau — do la cot cat mau cua MOI o."""
    rep = t2.sample_binding_report(_fake_raw_panel(), top=3)
    assert rep.iloc[0]["column"] == "epu_global_LEVEL"
    assert rep.iloc[0]["first_valid"] == "1997-01-01"


def test_sample_cost_measures_months_lost():
    cost = t2.sample_cost(_fake_raw_panel(), "1990-01-01")
    assert cost["actual_start"] == "1997-01-01"
    assert cost["months_lost"] == 7 * 12
    assert cost["binding_column"] == "epu_global_LEVEL"


def test_sample_binding_report_useless_on_complete_case_panel():
    """Chan doan PHAI chay tren ban chua dropna.

    Tren ban da complete-case moi cot cung mot first_valid — bang khong noi
    duoc cot nao rang buoc. Test nay khoa ly do `dropna=False` ton tai.
    """
    rep = t2.sample_binding_report(_fake_raw_panel().dropna(), top=3)
    assert rep["first_valid"].nunique() == 1


def test_battery_control_names_version_a_has_no_controls():
    assert t2.battery_control_names("LEVEL", "a") == []
    assert t2.battery_control_names("LEVEL", "a", "same_measure") == []


def test_battery_c_adds_policy_shock_on_top_of_b():
    """Ban c = ban b + CU SOC chinh sach. Phai la SIEU TAP cua b, neu khong thi
    chenh lech giua hai ban khong con doc duoc la 'do them control nay'."""
    b = t2.battery_control_names("LEVEL", "b")
    c = t2.battery_control_names("LEVEL", "c")
    assert set(b) < set(c)
    extra = set(c) - set(b)
    assert t2.POLICY_SHOCK_COL in extra
    assert len(extra) == 1 + t2.BATTERY_CONTROL_LAGS      # duong + lag cung do sau


def test_unknown_battery_version_raises():
    with pytest.raises(ValueError, match="battery="):
        t2.battery_control_names("LEVEL", "z")


def test_version_c_dropped_when_policy_shock_column_absent():
    """Khong dung duoc cu soc chinh sach (mat mang/FRED) -> BO ban c, khong im
    lang chay no voi control rong roi bao cao nhu da kiem soat."""
    panel = pd.DataFrame({"oil": [1.0], "GPR_LEVEL": [1.0]})
    assert t2.available_versions(panel) == ("a", "b")
    with_mp = panel.assign(**{t2.POLICY_SHOCK_COL: [0.0]})
    assert t2.available_versions(with_mp) == ("a", "b", "c")


def test_battery_control_names_same_measure_matches_shock_measure():
    """Che do cu: control di theo dung thuoc do cua shock (docs/14 §2 1a)."""
    for m in t2.SHOCK_MEASURES:
        names = t2.battery_control_names(m, "b", "same_measure")
        assert names == [f"{c}_{m}" for c in t2.BATTERY_CONTROLS]


def test_battery_control_names_level_lags_does_not_depend_on_measure():
    """Che do mac dinh: LEVEL + p lag, GIONG NHAU o ca ba thuoc do.

    Do la diem mau chot — control khong con doi theo thuoc do nen khong an
    warm-up cua truc shock, va ba thuoc do van dung dung mot tap control.
    """
    per_measure = {m: t2.battery_control_names(m, "b", "level_lags")
                   for m in t2.SHOCK_MEASURES}
    first = per_measure[t2.SHOCK_MEASURES[0]]
    assert all(v == first for v in per_measure.values())
    expected = len(t2.BATTERY_CONTROLS) * (1 + t2.BATTERY_CONTROL_LAGS)
    assert len(first) == expected == len(set(first))


def test_battery_control_lags_match_lp_lags():
    """Control va shock cung do sau lag — khong phai tham so tu do de do."""
    assert t2.BATTERY_CONTROL_LAGS == t2.LAGS


def test_build_panel_rejects_unknown_battery_mode():
    with pytest.raises(ValueError, match="battery_mode"):
        t2.build_panel("1990-01-01", None, False, battery_mode="whatever")


@pytest.mark.parametrize("mode", ["level_lags", "same_measure"])
def test_build_panel_emits_exactly_the_control_columns_requested(monkeypatch, mode):
    """Ten control phai KHOP cot panel that sinh ra.

    Lech ten thi loi no ra o sau ~5 phut uoc luong, khong phai luc dung panel —
    nen khoa bang test thay vi bang doc ky.
    """
    n = 420                                   # 1990-01..2024-12: phu dev window
    idx = pd.date_range("1990-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(0)
    raw = pd.DataFrame({c: 100 + rng.standard_normal(n).cumsum()
                        for c in t2.BATTERY_CONTROLS}, index=idx)
    captured = {}

    monkeypatch.setattr(t2, "load_benchmark_monthly", lambda *a, **k: raw)
    monkeypatch.setattr(t2, "build_monthly_panel",
                        lambda **kw: captured.setdefault("extra", kw["extra_monthly"]))
    t2.build_panel("1990-01-01", None, False, battery_mode=mode)

    cols = set(captured["extra"].columns)
    for measure in t2.SHOCK_MEASURES:
        want = t2.battery_control_names(measure, "b", mode)
        assert set(want) <= cols, f"{mode}/{measure}: thiếu {set(want) - cols}"


# ---------------------------------------------------------------------------
# Doi chieu muc luoi — phai dung TREN bang Holm
# ---------------------------------------------------------------------------
def test_grid_null_section_comes_before_holm_table(families):
    """Doc '15 o song sot' truoc roi moi doc '34 < 43.2' thi an tuong da hinh
    thanh. Ket luan muc luoi phai den TRUOC ket luan muc o."""
    stats, holm, gamma = _payload(families)
    meta = {"data_version": "d", "git_commit": "g", "generated_at": "2026-08-09T10:00:00",
            "panel_start": "2007-02-01", "panel_end": "2026-06-01",
            "real_macro_vintage": "a", "freight_vintage": "b", "benchmark_vintage": "c"}
    text = "\n".join(t2.build_report(stats, holm, gamma, None, families, meta))
    i_grid = text.index("Đối chiếu mức lưới")
    i_holm = text.index("số ô sống sót Holm")
    assert i_grid < i_holm


def test_grid_null_stats_match_the_focal_test_count(families):
    """So kiem dinh cua doi chieu luoi = so kiem dinh focal, khong phai mot ho."""
    stats, holm, _ = _payload(families)
    assert stats["grid_n_tests"] == len(holm) == stats["n_focal_tests"]
    assert stats["grid_observed"] == stats["n_raw_sig"]
    assert stats["grid_expected"] == pytest.approx(round(len(holm) * t2.ALPHA, 1))


def test_sample_section_records_battery_mode_tradeoff(families):
    """Danh doi cua `level_lags` (JUMP phi tuyen) phai NAM TRONG report."""
    stats, holm, gamma = _payload(families)
    meta = {"data_version": "d", "git_commit": "g", "generated_at": "2026-08-09T10:00:00",
            "panel_start": "2007-02-01", "panel_end": "2026-06-01",
            "real_macro_vintage": "a", "freight_vintage": "b", "benchmark_vintage": "c"}
    text = "\n".join(t2.build_report(stats, holm, gamma, None, families, meta,
                                     t2.sample_binding_report(_fake_raw_panel())))
    assert "Chi phí mẫu" in text
    assert stats["battery_mode"] in text
    assert "epu_global_LEVEL" in text
    if stats["battery_mode"] == "level_lags":
        assert "LEVEL+JUMP" in text and "ÍT HƠN" in text


def test_converged_flag_survives_lp_to_tier2():
    """`converged` phải đi hết đường LP -> estimate_tier2 -> runner."""
    from gpr_engine.econometrics.tier2_global_macro import estimate_tier2
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame({"oil": rng.normal(size=n), "GPRD": rng.normal(size=n)})
    out = estimate_tier2(df, macro_vars=["oil"], shocks=["GPRD"],
                         horizons=[0, 1], macro_lags=1)
    assert "converged" in out.columns
    assert out["converged"].all(), "OLS luôn hội tụ — cờ phải là True"
