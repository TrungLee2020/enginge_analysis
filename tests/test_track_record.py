"""Test track record harness (M7, docs/11 §0 R2 + §11).

Ba quy tắc làm cho track record có nghĩa — nếu thiếu thì nó là marketing:
  1. GHI TRƯỚC, CHẤM SAU (target_date > issued_at);
  2. KHÔNG XÓA, KHÔNG SỬA (append-only, resolve một lần);
  3. LUÔN CÓ BASELINE (CRPS một mình không đọc được).

Cộng phần toán: CRPS phải thưởng dự báo sắc và đúng, phạt dự báo lệch; PIT phải
phẳng khi phân phối đúng và lệch khi model quá tự tin.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.scoring.track_record import (
    Forecast,
    TrackRecord,
    TrackRecordViolation,
    brier,
    crps_ensemble,
    pit_value,
    skill_score,
    unconditional_baseline,
)

Q = {"0.10": -1.28, "0.25": -0.67, "0.50": 0.0, "0.75": 0.67, "0.90": 1.28}
BL = {"0.10": -2.56, "0.25": -1.35, "0.50": 0.0, "0.75": 1.35, "0.90": 2.56}


def make(fid="f1", issued="2026-01-01", target="2026-03-01", **kw) -> Forecast:
    base = dict(forecast_id=fid, issued_at=pd.Timestamp(issued),
                target_date=pd.Timestamp(target), outcome_name="ip",
                quantiles=dict(Q), baseline_quantiles=dict(BL))
    base.update(kw)
    return Forecast(**base)


# ---------------------------------------------------------------------------
# Quy tắc 1 — ghi trước, chấm sau
# ---------------------------------------------------------------------------
def test_target_must_be_after_issue():
    with pytest.raises(TrackRecordViolation, match="TRƯỚC khi kết cục"):
        make(issued="2026-03-01", target="2026-01-01")
    with pytest.raises(TrackRecordViolation):
        make(issued="2026-01-01", target="2026-01-01")   # cùng thời điểm cũng cấm


def test_cannot_score_before_resolution():
    with pytest.raises(TrackRecordViolation, match="chưa có kết cục"):
        make().score()


# ---------------------------------------------------------------------------
# Quy tắc 2 — append-only
# ---------------------------------------------------------------------------
def test_duplicate_id_rejected():
    tr = TrackRecord()
    tr.record(make("a"))
    with pytest.raises(TrackRecordViolation, match="APPEND-ONLY"):
        tr.record(make("a"))


def test_cannot_overwrite_outcome():
    tr = TrackRecord()
    tr.record(make("a"))
    tr.resolve("a", 0.3)
    with pytest.raises(TrackRecordViolation, match="sửa lịch sử"):
        tr.resolve("a", 0.9)


def test_pending_is_visible():
    """Dự báo chưa resolve phải đếm được — bỏ quên là cách track record đẹp giả."""
    tr = TrackRecord()
    tr.record(make("a"))
    tr.record(make("b"))
    tr.resolve("a", 0.1)
    assert len(tr.pending) == 1
    assert tr.summary()["n_pending"] == 1 and tr.summary()["n_resolved"] == 1


# ---------------------------------------------------------------------------
# Quy tắc 3 — luôn có baseline
# ---------------------------------------------------------------------------
def test_forecast_without_baseline_rejected():
    with pytest.raises(TrackRecordViolation, match="baseline"):
        make(baseline_quantiles={})


def test_skill_score_direction():
    assert skill_score(0.5, 1.0) == pytest.approx(0.5)     # tốt hơn baseline
    assert skill_score(1.0, 1.0) == pytest.approx(0.0)     # ngang
    assert skill_score(2.0, 1.0) == pytest.approx(-1.0)    # tệ hơn


def test_perfect_baseline_is_rejected_as_suspicious():
    """CRPS baseline = 0 nghĩa là baseline biết trước — gần như chắc chắn dùng
    dữ liệu tương lai. Raise thay vì trả skill = -inf."""
    with pytest.raises(ValueError, match="dữ liệu tương lai"):
        skill_score(0.5, 0.0)


def test_baseline_is_cut_at_as_of():
    """Baseline vô điều kiện phải cắt theo as_of — nếu không nó chứa tương lai."""
    idx = pd.date_range("2020-01-01", periods=200, freq="D")
    hist = pd.Series(np.r_[np.zeros(100), np.full(100, 50.0)], index=idx)
    early = unconditional_baseline(hist, as_of=idx[99])
    full = unconditional_baseline(hist)
    assert early["0.90"] == pytest.approx(0.0)
    assert full["0.90"] > 0.0, "không cắt as_of thì baseline nuốt cả tương lai"


def test_baseline_needs_enough_history():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    with pytest.raises(ValueError, match="không đủ|Chỉ"):
        unconditional_baseline(pd.Series(range(10), index=idx))


# ---------------------------------------------------------------------------
# Toán: CRPS / Brier / PIT
# ---------------------------------------------------------------------------
def test_crps_rewards_accuracy():
    sharp_right = crps_ensemble([0.0, 0.0, 0.1, -0.1], 0.0)
    sharp_wrong = crps_ensemble([5.0, 5.0, 5.1, 4.9], 0.0)
    assert sharp_right < sharp_wrong


def test_crps_rewards_sharpness_when_both_centred():
    """Cùng đúng tâm thì phân phối SẮC hơn phải được điểm tốt hơn."""
    sharp = crps_ensemble(list(np.linspace(-0.2, 0.2, 21)), 0.0)
    wide = crps_ensemble(list(np.linspace(-5.0, 5.0, 21)), 0.0)
    assert sharp < wide


def test_crps_zero_for_point_mass_on_truth():
    assert crps_ensemble([2.0] * 5, 2.0) == pytest.approx(0.0)


def test_brier_bounds_and_direction():
    assert brier(1.0, True) == pytest.approx(0.0)
    assert brier(0.0, True) == pytest.approx(1.0)
    assert brier(0.5, True) == pytest.approx(0.25)
    with pytest.raises(ValueError):
        brier(1.4, True)


def test_pit_uniform_when_distribution_correct():
    """Phân phối đúng -> PIT xấp xỉ đều. Đây là kiểm HIỆU CHUẨN."""
    rng = np.random.default_rng(0)
    draws = rng.normal(size=400)
    pits = [pit_value(list(rng.normal(size=200)), float(y)) for y in draws]
    assert 0.42 < float(np.mean(pits)) < 0.58


def test_pit_detects_overconfidence():
    """Model quá hẹp -> quan sát hay rơi ngoài -> PIT dồn về hai biên."""
    rng = np.random.default_rng(1)
    truth = rng.normal(0, 3.0, 300)          # thực tế rộng
    pits = [pit_value(list(rng.normal(0, 0.3, 200)), float(y)) for y in truth]
    extreme = float(np.mean([(p < 0.1) or (p > 0.9) for p in pits]))
    assert extreme > 0.5, f"chỉ {extreme:.2f} ở hai biên — PIT không bắt được"


# ---------------------------------------------------------------------------
# Bảng điểm + lưu trữ
# ---------------------------------------------------------------------------
def test_scoreboard_has_baseline_columns():
    tr = TrackRecord()
    tr.record(make("a"))
    tr.resolve("a", 0.2)
    sb = tr.scoreboard()
    assert len(sb) == 1
    for col in ("crps", "crps_baseline", "skill_score", "pit"):
        assert col in sb.columns and sb[col].notna().all()


def test_brier_only_when_threshold_given():
    tr = TrackRecord()
    tr.record(make("a"))
    tr.record(make("b", threshold=-0.5, prob_threshold=0.3, baseline_prob=0.1))
    tr.resolve("a", 0.2)
    tr.resolve("b", -1.0)          # xảy ra (< -0.5)
    sb = tr.scoreboard().set_index("forecast_id")
    assert pd.isna(sb.loc["a", "brier"])
    assert sb.loc["b", "brier"] == pytest.approx(brier(0.3, True))
    assert sb.loc["b", "brier_baseline"] == pytest.approx(brier(0.1, True))


def test_summary_empty_when_nothing_resolved():
    tr = TrackRecord()
    tr.record(make("a"))
    s = tr.summary()
    assert s["n_resolved"] == 0 and s["n_pending"] == 1
    assert "skill_mean" not in s, "chưa resolve mà đã có điểm là bịa"


def test_pit_histogram_shape():
    tr = TrackRecord()
    for i in range(20):
        tr.record(make(f"f{i}"))
        tr.resolve(f"f{i}", float(np.random.default_rng(i).normal()))
    h = tr.pit_histogram(bins=5)
    assert len(h) == 5
    assert h["count"].sum() == 20
    assert h["expected"].iloc[0] == pytest.approx(4.0)


def test_roundtrip_jsonl_preserves_scores(tmp_path):
    """Lịch sử công khai phải đọc được và tái lập điểm y hệt."""
    tr = TrackRecord()
    tr.record(make("a", model_version="m1", data_version="d1"))
    tr.record(make("b", threshold=0.0, prob_threshold=0.4, baseline_prob=0.5))
    tr.resolve("a", 0.42)
    tr.resolve("b", -0.3)
    p = tr.save(tmp_path / "tr.jsonl")
    assert p.read_text(encoding="utf-8").count("\n") == 2   # JSONL, người đọc được

    back = TrackRecord.load(p)
    assert len(back) == 2
    pd.testing.assert_frame_equal(
        tr.scoreboard().drop(columns=["issued_at", "target_date"]),
        back.scoreboard().drop(columns=["issued_at", "target_date"]))


def test_load_missing_file_gives_empty_record(tmp_path):
    assert len(TrackRecord.load(tmp_path / "chua-co.jsonl")) == 0


def test_claim_ceiling_unchanged_by_track_record():
    """Có track record KHÔNG nâng trần claim — track tháng vẫn chưa có holdout."""
    assert "chưa xác nhận holdout" in make().claim
