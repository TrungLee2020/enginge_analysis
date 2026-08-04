"""Test spec kép docs/16 §2.2: Δ LEVEL = ANTICIPATED + SURPRISE.

Kiểm các bất biến mà nếu vỡ thì bảng γ mới sẽ sai một cách khó thấy:
  - hai thành phần cộng lại bằng ĐÚNG Δ LEVEL (đồng nhất thức, không phải xấp xỉ);
  - SURPRISE ≡ `innovation()` đã có — không có đường ước lượng thứ hai;
  - không nhìn tương lai;
  - phân rã trên SAI PHÂN, không phải trên mức (mức là gần nghiệm đơn vị → #9);
  - so sánh hệ số phải chuẩn hóa (Var hai thành phần lệch cả bậc);
  - cổng NHÃN chặn việc gọi ANTICIPATED là cú sốc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics.shock_axis import (
    check_component_labelling,
    component_claim_label,
)
from gpr_engine.econometrics.shocks import (
    delta_decomposition,
    innovation,
    standardized_contribution,
)
from gpr_engine.econometrics.dataset import log1p_gpr


@pytest.fixture
def gpr() -> pd.Series:
    """Chuỗi GPR giả: dai dẳng + lệch phải, giống đặc tính thật."""
    rng = np.random.default_rng(4)
    n = 400
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = 0.85 * x[t - 1] + rng.normal(0, 1)
    raw = np.exp(x / 2.0) * 40.0            # dương, lệch phải
    return pd.Series(raw, name="GPRD",
                     index=pd.date_range("2000-01-01", periods=n, freq="MS"))


# ---------------------------------------------------------------------------
# Đồng nhất thức
# ---------------------------------------------------------------------------
def test_components_sum_exactly_to_delta_level(gpr):
    """ANTICIPATED + SURPRISE == Δ LEVEL, chính xác chứ không xấp xỉ.

    Đây là lý do lấy ANTICIPATED bằng HIỆU thay vì fit riêng: hai đường ước lượng
    độc lập sẽ lệch nhau vài phần nghìn và không ai thấy, còn ở đây sai là vỡ.
    """
    comp = delta_decomposition(gpr, min_train=60)
    total = comp["GPRD_ANTICIPATED"] + comp["GPRD_SURPRISE"]
    d_level = log1p_gpr(gpr).diff()
    both = pd.concat([total, d_level], axis=1).dropna()
    np.testing.assert_allclose(both.iloc[:, 0], both.iloc[:, 1], rtol=1e-12)


def test_surprise_is_exactly_existing_innovation(gpr):
    """SURPRISE không phải công thức mới — nó LÀ `innovation()`."""
    comp = delta_decomposition(gpr, min_train=60)
    innov = innovation(gpr, min_train=60)
    both = pd.concat([comp["GPRD_SURPRISE"], innov], axis=1).dropna()
    np.testing.assert_allclose(both.iloc[:, 0], both.iloc[:, 1], rtol=1e-12)


def test_decomposition_is_on_difference_not_level(gpr):
    """Phân rã trên Δ LEVEL. ANTICIPATED phải quanh 0, KHÔNG phải quanh mức GPR.

    Nếu ai đó đổi sang `persistent_ar` (= Ê[LEVEL]) thì cột này thành chuỗi gần
    nghiệm đơn vị quanh ~4, và đưa vào hồi quy là quay lại đúng vấn đề #9.
    """
    comp = delta_decomposition(gpr, min_train=60).dropna()
    level_mean = float(log1p_gpr(gpr).mean())
    assert abs(float(comp["GPRD_ANTICIPATED"].mean())) < 0.1 * level_mean
    assert abs(float(comp["GPRD_ANTICIPATED"].mean())) < 0.5


def test_no_lookahead(gpr):
    """Nối thêm dữ liệu tương lai không được đổi giá trị đã tính."""
    short = delta_decomposition(gpr.iloc[:300], min_train=60).dropna()
    full = delta_decomposition(gpr, min_train=60).dropna()
    common = short.index.intersection(full.index)
    assert len(common) > 100
    np.testing.assert_allclose(short.loc[common].to_numpy(),
                               full.loc[common].to_numpy(), rtol=1e-10)


# ---------------------------------------------------------------------------
# Thang đo — bẫy chính của docs/16 §2.1
# ---------------------------------------------------------------------------
def test_anticipated_has_much_smaller_variance(gpr):
    """Var(ANTICIPATED) << Var(SURPRISE) trên chuỗi sai phân.

    Đây là LÝ DO hệ số thô không so được: một hệ số gấp đôi trên regressor biên
    độ 1/3 là đóng góp nhỏ hơn (docs/16 §2.1 đã sửa; E2 đo 48.9% ô đảo chiều).
    """
    comp = delta_decomposition(gpr, min_train=60).dropna()
    ratio = comp["GPRD_ANTICIPATED"].var() / comp["GPRD_SURPRISE"].var()
    assert ratio < 0.5, f"Var ratio {ratio:.3f} — kiểm lại phân rã có đúng trên Δ không"


def test_standardized_contribution_can_reverse_raw_ordering():
    """Đóng góp chuẩn hóa có thể đảo thứ tự của hệ số thô — chứng minh bằng số.

    Nếu test này không đảo được thì cảnh báo trong docs/16 §2.1 là thừa.
    """
    a = pd.Series(np.random.default_rng(0).normal(0, 0.1, 500))   # biên độ nhỏ
    s = pd.Series(np.random.default_rng(1).normal(0, 0.3, 500))   # biên độ lớn
    beta_a, beta_s = -1.2, -0.6          # thô: a gấp đôi s
    assert abs(beta_a) > abs(beta_s)
    assert abs(standardized_contribution(beta_a, a)) < \
        abs(standardized_contribution(beta_s, s)), "chuẩn hóa phải đảo được thứ tự"


# ---------------------------------------------------------------------------
# Cổng NHÃN — điều kiện 2 của §2.2
# ---------------------------------------------------------------------------
def test_component_labels_are_distinct_and_explicit():
    assert "DỰ BÁO ĐƯỢC" in component_claim_label("ANTICIPATED")
    assert "cú sốc" in component_claim_label("SURPRISE")
    with pytest.raises(ValueError):
        component_claim_label("PERSISTENT")


@pytest.mark.parametrize("bad", [
    "Cú sốc địa chính trị đẩy IP giảm 0.5%.",
    "Thành phần này đo phản ứng với shock.",
    "Phần bất ngờ của GPR tác động lên sản lượng.",
])
def test_labelling_gate_rejects_shock_wording_for_anticipated(bad):
    """Gọi ANTICIPATED bằng từ ngữ của cú sốc = vi phạm #9, phải raise."""
    with pytest.raises(ValueError, match="#9|ANTICIPATED"):
        check_component_labelling("ANTICIPATED", bad)


def test_labelling_gate_allows_correct_wording():
    check_component_labelling(
        "ANTICIPATED", "Hệ số đo phản ứng với thành phần đã dự báo được của GPR.")
    # Với SURPRISE thì đúng là được nói "cú sốc" — cổng không cản.
    check_component_labelling("SURPRISE", "Cú sốc đẩy IP giảm.")
