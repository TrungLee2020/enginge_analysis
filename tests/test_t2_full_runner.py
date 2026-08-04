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


def _payload(families: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    gamma = _fake_gamma(families)
    holm = t2.apply_holm(gamma, families)
    panel = pd.DataFrame(np.zeros((231, 3)),
                         index=pd.date_range("2007-02-01", periods=231, freq="MS"))
    stats = t2.compute_stats(panel, gamma, holm, None, families, elapsed=12.3)
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
