"""Test loader AI-GPR (docs/16 §1) — file TẢI TAY, ghim vintage.

Không có dữ liệu thật trong repo, nên test dùng file tạm. Kiểm các bất biến:
  - thiếu file -> lỗi có HƯỚNG DẪN, không phải FileNotFoundError trần;
  - thiếu cột -> raise, KHÔNG lặng lẽ bỏ qua (thiếu threats/acts thì mọi phân
    tách ACT/THREAT sau đó chạy trên dữ liệu rỗng mà không ai thấy);
  - vintage = hash file, đổi file thì đổi vintage (nguyên tắc #4);
  - `describe_ai_gpr_file` dùng được để đối chiếu schema trước khi tin mapping.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gpr_engine.econometrics.data_files import (
    AI_GPR_COLUMNS,
    ai_gpr_vintage,
    describe_ai_gpr_file,
    load_ai_gpr_daily,
)


def _write(path, cols: dict, n: int = 50) -> None:
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    pd.DataFrame({"date": idx, **{c: range(n) for c in cols}}).to_csv(path, index=False)


@pytest.fixture
def good_file(tmp_path):
    p = tmp_path / "ai_gpr_daily.csv"
    _write(p, dict.fromkeys(AI_GPR_COLUMNS))
    return str(p)


def test_missing_file_gives_actionable_instructions(tmp_path):
    """Lỗi phải nói TẢI Ở ĐÂU và vì sao không tự tải — không để người đọc đoán."""
    with pytest.raises(FileNotFoundError) as e:
        load_ai_gpr_daily(str(tmp_path / "nope.csv"))
    msg = str(e.value)
    assert "ai_gpr.html" in msg
    assert "describe_ai_gpr_file" in msg
    assert "tái lập" in msg          # lý do không tự fetch (nguyên tắc #4)


def test_loads_and_renames(good_file):
    df = load_ai_gpr_daily(good_file)
    assert list(df.columns) == list(AI_GPR_COLUMNS.values())
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing
    assert df.attrs["vintage"] == ai_gpr_vintage(good_file)


def test_missing_column_raises_not_silently_dropped(tmp_path):
    """Thiếu threats/acts phải NỔ — nếu bỏ qua thì tách ACT/THREAT sau đó rỗng."""
    p = tmp_path / "partial.csv"
    _write(p, {"AIGPR": None})           # thiếu AIGPRT/AIGPRA
    with pytest.raises(ValueError, match="thiếu cột"):
        load_ai_gpr_daily(str(p))


def test_missing_date_column_raises(tmp_path):
    p = tmp_path / "nodate.csv"
    pd.DataFrame({c: [1, 2] for c in AI_GPR_COLUMNS}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="cột ngày"):
        load_ai_gpr_daily(str(p))


def test_vintage_changes_with_file_content(tmp_path):
    """Trang cập nhật định kỳ -> hai bản tải là hai dữ liệu. Vintage phải phân biệt."""
    p = tmp_path / "v.csv"
    _write(p, dict.fromkeys(AI_GPR_COLUMNS), n=50)
    v1 = ai_gpr_vintage(str(p))
    _write(p, dict.fromkeys(AI_GPR_COLUMNS), n=60)   # bản cập nhật sau
    assert ai_gpr_vintage(str(p)) != v1
    assert ai_gpr_vintage(str(tmp_path / "khong-ton-tai.csv")) is None


def test_describe_reports_actual_columns(tmp_path):
    """Công cụ đối chiếu schema: phải trả tên cột THẬT, không phải tên giả định."""
    p = tmp_path / "other_schema.csv"
    pd.DataFrame({"day": ["2020-01-01"], "ai_gpr": [1.0]}).to_csv(p, index=False)
    info = describe_ai_gpr_file(str(p))
    assert info["columns"] == ["day", "ai_gpr"]
    assert info["date_col_guess"] == ["day"]
    assert info["expected_mapping"] == AI_GPR_COLUMNS   # để so bằng mắt


def test_custom_columns_override(tmp_path):
    """Sửa mapping bằng tham số — đường đi khi file thật khác giả định."""
    p = tmp_path / "custom.csv"
    _write(p, {"ai_gpr": None, "ai_gpr_threat": None})
    df = load_ai_gpr_daily(str(p),
                           columns={"ai_gpr": "AIGPR", "ai_gpr_threat": "AIGPR_THREAT"})
    assert list(df.columns) == ["AIGPR", "AIGPR_THREAT"]
