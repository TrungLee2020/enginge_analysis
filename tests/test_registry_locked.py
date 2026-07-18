"""Test khóa config/hypothesis_registry.yaml — enforce pre-registration bằng MÁY.

docs/10 D1 / docs/g0_governance.md: registry chống HARKing. Nếu chỉ là văn bản
thì không ràng buộc gì — test này biến kỷ luật ghi-trước thành cổng CI.

Khóa 3 thứ:
  1. AR order pre-registered (chống snooping order — docs/10 §5). Ai đổi order đã
     chốt mà không cập nhật LOCKED_AR_ORDERS trong cùng commit → test đỏ.
  2. Cấu trúc mỗi giả thuyết đầy đủ (id/statement/shock/method/decides_gate/status).
  3. Vòng đời status hợp lệ; shock là innovation-based (nguyên tắc #9), không level.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "hypothesis_registry.yaml"

# AR order KHÓA — chốt 2026-07-18 (BIC trong trần parsimony p=5, dev window 2015-2020).
# docs/g0_governance.md §1.1. Đổi = phải cập nhật đây trong cùng commit + giải thích.
LOCKED_AR_ORDERS = {"GPRD": 5, "GPRD_ACT": 5, "GPRD_THREAT": 2}
LOCKED_DEV_WINDOW = ["2015-01-01", "2020-12-31"]
LOCKED_MAX_ORDER = 5

REQUIRED_HYP_FIELDS = {
    "id", "statement", "source", "data", "shock", "method",
    "outcome", "decides_gate", "registered", "status",
}
VALID_STATUS = {"registered", "tested", "superseded"}

# Shock hợp lệ: innovation/surprise/jump-based (CLAUDE.md #9). KHÔNG level thô.
# Cấm rõ các token level để không lẫn LEVEL/zscore vào giả thuyết shock.
FORBIDDEN_SHOCK_TOKENS = {"GPRD_LEVEL", "GPRC_VNM", "zscore", "log1p_level"}


def _cfg() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def test_registry_loads_and_has_version():
    cfg = _cfg()
    assert cfg.get("registry_version"), "registry thiếu registry_version"
    assert "hypotheses" in cfg and cfg["hypotheses"], "registry chưa đăng ký giả thuyết nào"


def test_ar_orders_locked():
    """AR order pre-registered khớp bản khóa — chống snooping order (docs/10 §5)."""
    spec = _cfg()["ar_persistent_spec"]
    assert spec["orders"] == LOCKED_AR_ORDERS, (
        "AR order trong registry khác bản khóa! Đổi order đã pre-register sau khi "
        "nhìn kết quả = snooping (docs/g0 §1.1). Nếu có chủ đích, cập nhật "
        "LOCKED_AR_ORDERS trong cùng commit + giải thích.")
    assert spec["dev_window"] == LOCKED_DEV_WINDOW, "dev_window khác bản khóa"
    assert spec["method"] == "AR", "PERSISTENT phải là AR (quyết định 2026-07-18)"
    assert spec["max_order_searched"] == LOCKED_MAX_ORDER, (
        "Trần parsimony khác bản khóa! Nới trần = đổi spec pre-registered "
        "(docs/g0 §1.1) — cập nhật LOCKED_MAX_ORDER cùng commit + giải thích.")
    assert spec.get("criterion") == "bic", "order_selection phải dùng BIC (chốt 2026-07-18)"


def test_ar_boundary_flag_honest():
    """Order chạm biên max_order phải bật boundary_flag (minh bạch cho human review)."""
    spec = _cfg()["ar_persistent_spec"]
    mx = spec["max_order_searched"]
    at_boundary = any(p >= mx for p in spec["orders"].values())
    if at_boundary:
        assert spec.get("boundary_flag") is True, (
            "Có order chạm biên max_order nhưng boundary_flag không bật — phải cảnh "
            "báo human review rằng AIC có thể muốn p lớn hơn (docs/g0 §1.1).")


def test_every_hypothesis_well_formed():
    for h in _cfg()["hypotheses"]:
        missing = REQUIRED_HYP_FIELDS - set(h)
        assert not missing, f"giả thuyết {h.get('id')} thiếu trường: {missing}"
        assert h["status"] in VALID_STATUS, f"{h['id']}: status {h['status']!r} không hợp lệ"
        assert h["statement"].strip(), f"{h['id']}: statement rỗng"


def test_shocks_are_innovation_based():
    """Mọi shock đăng ký là innovation/surprise — không level thô (nguyên tắc #9)."""
    for h in _cfg()["hypotheses"]:
        shocks = h["shock"] if isinstance(h["shock"], list) else [h["shock"]]
        for s in shocks:
            for bad in FORBIDDEN_SHOCK_TOKENS:
                # GPRC_VNM_ORTH_INNOV hợp lệ (đã orthogonalize + innovation); chỉ
                # cấm GPRC_VNM trần (chưa innovation). Kiểm tra token cô lập.
                if bad == "GPRC_VNM":
                    assert not (s == "GPRC_VNM"), (
                        f"{h['id']}: shock GPRC_VNM trần (monthly, chưa innovation) — "
                        "vi phạm #9/#10. Dùng GPRC_VNM_ORTH_INNOV.")
                else:
                    assert bad not in s, f"{h['id']}: shock {s!r} chứa token level cấm {bad!r} (#9)"


def test_tested_hypotheses_are_immutable_marker():
    """Giả thuyết đã 'tested' phải có report tham chiếu (không tự do sửa nữa).

    Ở bản 1.0 chưa có cái nào tested; test này là cổng cho tương lai: khi một
    giả thuyết chuyển sang tested, phải kèm 'report' trỏ file versioned.
    """
    for h in _cfg()["hypotheses"]:
        if h["status"] == "tested":
            assert h.get("report"), (
                f"{h['id']} status=tested nhưng không có 'report' — giả thuyết đã "
                "chạy phải trỏ report versioned (docs/g0 §1). Đổi ý sau tested = id mới.")


def test_trial_log_present():
    """Multiple-testing: phải có trial_log để đếm số lần thử (Deflated Sharpe)."""
    tl = _cfg()["trial_log"]
    assert "n_trials" in tl and isinstance(tl["n_trials"], int)
    assert tl["n_trials"] >= 0
