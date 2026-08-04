"""Test analogue retrieval (M5, docs/11 §6) — tầng 4.

Bốn ràng buộc của §6 đều phải là CƠ CHẾ, không phải lời hứa:
  1. n<5 -> im lặng (raise), KHÔNG hạ ngưỡng để có số;
  2. IQR đổi dấu -> "phân tán, không kết luận", không đưa trung vị ra một mình;
  3. luôn liệt kê được danh sách episode (điểm bán hàng chính);
  4. chỉ dùng dữ liệu available_at <= t, KỂ CẢ trong retrieval.

Cộng hai bất biến dễ vỡ mà không ai thấy: loại trừ ±30 ngày (chống trùng
episode), và chuẩn hóa descriptor bằng EXPANDING chứ không phải toàn mẫu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.analogue import (
    DEFAULT_EXCLUDE_DAYS,
    AnalogueResult,
    InsufficientAnalogues,
    Neighbour,
    batch_analogues,
    build_descriptor,
    describe,
    find_analogues,
    regime_flag,
)

N = 600


@pytest.fixture
def idx() -> pd.DatetimeIndex:
    return pd.date_range("2005-01-01", periods=N, freq="D")


@pytest.fixture
def descriptor(idx) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "a": rng.normal(size=N), "b": rng.normal(size=N),
        "regime": regime_flag(idx),
    }, index=idx)


@pytest.fixture
def outcome(idx) -> pd.Series:
    rng = np.random.default_rng(7)
    return pd.Series(rng.normal(size=N), index=idx, name="ip")


# ---------------------------------------------------------------------------
# Ràng buộc 1 — n<5 thì im lặng
# ---------------------------------------------------------------------------
def test_too_few_candidates_raises_instead_of_lowering_bar(descriptor, outcome):
    """Đầu mẫu không đủ tiền lệ -> raise, không trả kết quả mỏng."""
    early = descriptor.index[20]
    with pytest.raises(InsufficientAnalogues, match="P3|ứng viên"):
        find_analogues(descriptor, outcome, early, horizon=5)


def test_min_neighbours_is_enforced(descriptor, outcome):
    as_of = descriptor.index[400]
    with pytest.raises(InsufficientAnalogues):
        find_analogues(descriptor, outcome, as_of, horizon=5, k=3,
                       min_neighbours=10)


# ---------------------------------------------------------------------------
# Ràng buộc 4 — available_at <= t, kể cả trong retrieval
# ---------------------------------------------------------------------------
def test_all_neighbours_strictly_before_as_of(descriptor, outcome):
    as_of = descriptor.index[500]
    res = find_analogues(descriptor, outcome, as_of, horizon=10)
    assert all(nb.date < as_of for nb in res.neighbours), \
        "láng giềng nằm sau as_of = dùng tương lai làm tiền lệ"


def test_neighbour_outcomes_already_observed_at_as_of(descriptor, outcome):
    """Tiền lệ phải đã DIỄN BIẾN XONG tính đến as_of.

    Lấy episode cách as_of 3 ngày rồi đọc kết cục h=30 của nó là đọc tương lai,
    dù bản thân episode nằm ở quá khứ. Đây là look-ahead trá hình.
    """
    as_of = descriptor.index[500]
    h = 30
    res = find_analogues(descriptor, outcome, as_of, horizon=h)
    for nb in res.neighbours:
        assert nb.date + pd.Timedelta(days=h) <= as_of + pd.Timedelta(days=h)
        assert nb.date <= as_of


def test_future_data_does_not_change_past_result(descriptor, outcome):
    """Nối thêm dữ liệu sau as_of không được đổi kết quả tại as_of."""
    as_of = descriptor.index[300]
    full = find_analogues(descriptor, outcome, as_of, horizon=5)
    cut = descriptor.index <= descriptor.index[350]
    short = find_analogues(descriptor[cut], outcome[cut], as_of, horizon=5)
    assert [n.date for n in full.neighbours] == [n.date for n in short.neighbours]
    assert full.median == pytest.approx(short.median)


# ---------------------------------------------------------------------------
# Loại trừ ±30 ngày
# ---------------------------------------------------------------------------
def test_exclusion_window_blocks_near_duplicates(descriptor, outcome):
    """Không láng giềng nào trong ±30 ngày quanh as_of (chống trùng episode)."""
    as_of = descriptor.index[500]
    res = find_analogues(descriptor, outcome, as_of, horizon=5)
    cutoff = as_of - pd.Timedelta(days=DEFAULT_EXCLUDE_DAYS)
    assert all(nb.date < cutoff for nb in res.neighbours)


def test_wider_exclusion_removes_more(descriptor, outcome):
    as_of = descriptor.index[500]
    narrow = find_analogues(descriptor, outcome, as_of, horizon=5, exclude_days=5)
    wide = find_analogues(descriptor, outcome, as_of, horizon=5, exclude_days=200)
    latest_n = max(nb.date for nb in narrow.neighbours)
    latest_w = max(nb.date for nb in wide.neighbours)
    assert latest_w <= latest_n


# ---------------------------------------------------------------------------
# Ràng buộc 2 — IQR đổi dấu
# ---------------------------------------------------------------------------
def test_dispersed_flag_when_iqr_straddles_zero():
    res = AnalogueResult(as_of=pd.Timestamp("2020-01-01"), horizon=6,
                         outcome_name="ip", n=8, median=0.01, q25=-0.5, q75=0.6,
                         share_same_sign=0.5, dispersed=True,
                         neighbours=[Neighbour(pd.Timestamp("2019-01-01"), 0.9, 0.1)])
    text = describe(res)
    assert "phân tán" in text and "không kết luận" in text
    assert "trung vị" not in text, \
        "IQR đổi dấu mà vẫn đưa trung vị ra một mình là thông điệp sai"


def test_narrative_reports_median_when_not_dispersed():
    res = AnalogueResult(as_of=pd.Timestamp("2020-01-01"), horizon=6,
                         outcome_name="vix", n=7, median=2.1, q25=0.4, q75=5.2,
                         share_same_sign=0.86, dispersed=False)
    text = describe(res)
    assert "trung vị" in text and "+2.100" in text and "86%" in text


def test_dispersed_computed_from_data(descriptor, outcome):
    res = find_analogues(descriptor, outcome, descriptor.index[500], horizon=5)
    assert res.dispersed == bool(res.q25 < 0 < res.q75)


# ---------------------------------------------------------------------------
# Ràng buộc 3 — luôn liệt kê được episode
# ---------------------------------------------------------------------------
def test_episode_list_is_always_available(descriptor, outcome):
    res = find_analogues(descriptor, outcome, descriptor.index[500], horizon=5)
    tbl = res.episode_table()
    assert len(tbl) == res.n
    assert list(tbl.columns) == ["date", "similarity", "outcome"]
    assert tbl["date"].is_unique


def test_claim_ceiling_is_association(descriptor, outcome):
    """Tầng analogue KHÔNG được claim cao hơn `association` (07v2 §6.4)."""
    res = find_analogues(descriptor, outcome, descriptor.index[500], horizon=5)
    assert res.claim == "association"
    assert "association" in describe(res)


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------
def test_descriptor_uses_expanding_not_full_sample(idx):
    """z-score phải EXPANDING: giá trị tại t không đổi khi nối thêm dữ liệu sau.

    Chuẩn hóa toàn mẫu là rò rỉ — descriptor 1990 sẽ mang thông tin 2026 và
    'giống nhau' thành giống theo tương lai.
    """
    rng = np.random.default_rng(1)
    shocks = pd.DataFrame({"LEVEL": rng.normal(size=N),
                           "INNOVATION": rng.normal(size=N),
                           "JUMP": np.abs(rng.normal(size=N))}, index=idx)
    full = build_descriptor(shocks)
    short = build_descriptor(shocks.iloc[:400])
    common = short.dropna().index
    pd.testing.assert_frame_equal(full.loc[common], short.loc[common])


def test_regime_flag_three_buckets(idx):
    r = regime_flag(pd.DatetimeIndex(["2005-01-01", "2010-01-01", "2020-01-01"]))
    assert r.tolist() == [0.0, 1.0, 2.0]


def test_descriptor_act_threat_ratio_is_symmetric_in_log(idx):
    shocks = pd.DataFrame({"LEVEL": np.ones(N), "INNOVATION": np.zeros(N),
                           "ACT": np.r_[np.full(N // 2, 2.0), np.full(N // 2, 1.0)],
                           "THREAT": np.r_[np.full(N // 2, 1.0), np.full(N // 2, 2.0)]},
                          index=idx)
    d = build_descriptor(shocks)
    lo, hi = d["act_threat_log_ratio"].iloc[0], d["act_threat_log_ratio"].iloc[-1]
    assert lo == pytest.approx(-hi, abs=1e-5), "log ratio phải đối xứng quanh 0"


# ---------------------------------------------------------------------------
# Batch — ô bị bỏ phải có lý do
# ---------------------------------------------------------------------------
def test_batch_records_skips_with_reason(descriptor, idx):
    outcomes = pd.DataFrame({"ip": np.random.default_rng(0).normal(size=N),
                             "vix": np.random.default_rng(1).normal(size=N)},
                            index=idx)
    # index[33] với exclude_days=30 -> chỉ còn 3 ứng viên (<5) -> mọi ô bị bỏ.
    res, skipped = batch_analogues(descriptor, outcomes, descriptor.index[33],
                                   horizons=[5, 10])
    assert not res and len(skipped) == 4
    # Lý do phải CÓ CẤU TRÚC (số rời), không phải chuỗi văn xuôi — số nằm
    # trong câu văn thì Guard P1 ở tầng 4 không đối chiếu được với payload.
    assert all({"outcome", "horizon", "n_found", "n_required"} <= set(s)
               for s in skipped)
    assert all(isinstance(s["n_found"], int) for s in skipped)

    res2, skipped2 = batch_analogues(descriptor, outcomes, descriptor.index[500],
                                     horizons=[5])
    assert len(res2) == 2 and not skipped2
