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
LOCKED_MONTHLY_FOCAL_HORIZONS = [1, 2, 6]
LOCKED_DAILY_FOCAL_HORIZONS = [5, 20, 30]
LOCKED_WEEKEND_AGGREGATION = {
    "LEVEL": "mean",
    "INNOVATION": "mean",
    "JUMP": "max",
    "LEVEL_PLUS_JUMP": "mean(LEVEL)+max(JUMP)",
}

REQUIRED_HYP_FIELDS = {
    "id", "statement", "source", "data", "shock", "method",
    "outcome", "decides_gate", "registered", "status",
}
VALID_STATUS = {"registered", "tested", "superseded"}

# Quyết định governance đã ký 2026-08-02 (g0 §7.1/§7.2, docs/14 §6.4/§6.6/§6.1/§6.3).
# Khóa bằng máy vì mỗi cái đổi nghĩa một nguyên tắc đã khóa: đảo quyết định mà
# không cập nhật đây trong CÙNG COMMIT → test đỏ. Đó là tính năng, không phải lỗi.
LOCKED_DECISION_IDS = {
    "DEC-2026-08-02-shock-axis",
    "DEC-2026-08-02-holm-family",
    "DEC-2026-08-02-chanb-window",
    "DEC-2026-08-02-sources-trading",
    "DEC-2026-08-03-dual-component",   # docs/16 §2.2, amend shock-axis (§9.1)
}
REQUIRED_DECISION_FIELDS = {"id", "decided", "by", "what"}

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
    """Shock hồi quy phải là innovation/surprise — không level thô (nguyên tắc #9).

    NGOẠI LỆ measurement: KĐ có claim_ceiling bắt đầu 'measurement' chỉ ĐO thuộc
    tính thước đo (AUC phát hiện, KHÔNG hồi quy outcome) — LEVEL hợp lệ ở đó
    (docs/13 §2.4). #9 áp cho shock ĐƯA VÀO HỒI QUY, không cho diagnostic mô tả.
    """
    for h in _cfg()["hypotheses"]:
        if str(h.get("claim_ceiling", "")).startswith("measurement"):
            continue
        shocks = h["shock"] if isinstance(h["shock"], list) else [h["shock"]]
        for s in shocks:
            # LEVEL+JUMP là thước đo composite HỢP LỆ (docs/12 §2.1): level CỘNG jump
            # để bắt sốc dai dẳng — khác "đưa level trần vào hồi quy". Bỏ qua.
            if "LEVEL+JUMP" in s:
                continue
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


def test_sca_timing_contract_locked():
    """Horizon va weekend reducer la bac tu do pre-registered, khong duoc drift."""
    sca = next(x for x in _cfg()["specification_curves"] if x["id"] == "SCA-01")
    primary = sca["primary_cell"]
    assert primary["focal_horizons"] == LOCKED_MONTHLY_FOCAL_HORIZONS
    assert primary["daily_focal_horizons"] == LOCKED_DAILY_FOCAL_HORIZONS
    assert primary["weekend_aggregation"] == LOCKED_WEEKEND_AGGREGATION
    assert "E0_aligned_diagnostic" not in sca["blockers"]


# ---------------------------------------------------------------------------
# Quyết định governance đã ký (2026-08-02)
# ---------------------------------------------------------------------------
def test_signed_decisions_locked():
    """Bốn quyết định đã ký phải còn nguyên trong registry.

    Đảo một quyết định đã ký mà không cập nhật LOCKED_DECISION_IDS trong cùng
    commit → test đỏ. Cùng cơ chế với AR order: chữ ký chỉ có nghĩa khi việc rút
    lại nó cũng phải đi qua một commit có chủ đích.
    """
    decisions = {d["id"]: d for d in _cfg().get("decisions", [])}
    missing = LOCKED_DECISION_IDS - set(decisions)
    assert not missing, (
        f"Quyết định đã ký biến mất khỏi registry: {sorted(missing)}. Rút lại một "
        "chữ ký là hành động CÓ CHỦ ĐÍCH — cập nhật LOCKED_DECISION_IDS cùng commit.")
    for did, d in decisions.items():
        gaps = REQUIRED_DECISION_FIELDS - set(d)
        assert not gaps, f"quyết định {did} thiếu trường: {gaps}"
        assert str(d["what"]).strip(), f"{did}: 'what' rỗng"


def test_shock_axis_gate_matches_signed_decision():
    """Cổng máy phải khớp điều kiện đã ghi trong DEC-2026-08-02-shock-axis.

    Quyết định A cho phép LEVEL/LEVEL+JUMP vào bảng γ, nhưng CHỈ với
    inference='lag_augmented'. Nếu ai đó nới cổng cho 'hac', LEVEL quay lại là vi
    phạm CLAUDE.md #9 và test này là chỗ duy nhất bắt được.
    """
    from gpr_engine.econometrics.shock_axis import (
        SHOCK_MEASURES,
        eligible_measures,
        gate_shock_eligibility,
    )

    assert set(eligible_measures("lag_augmented")) == set(SHOCK_MEASURES), (
        "Điều kiện của quyết định A: cả ba thước đo eligible dưới lag_augmented.")
    assert set(eligible_measures("hac")) == {"INNOVATION"}, (
        "Dưới 'hac' chỉ INNOVATION được đọc là phản ứng với cú sốc (#9) — "
        "nới cổng ở đây là rút lại điều kiện kèm của DEC-2026-08-02-shock-axis.")
    for m in ("LEVEL", "LEVEL_PLUS_JUMP"):
        assert not gate_shock_eligibility(m, "hac").eligible
        assert gate_shock_eligibility(m, "lag_augmented").eligible


def test_amending_decision_names_what_it_amends():
    """Quyết định sửa quyết định khác phải nói RÕ sửa gì và giữ gì.

    docs/16 §9.1: v1.0 của doc đó viết "không đổi ba chữ ký" trong khi §2.2 có
    sửa một cái. Test này chặn kiểu amend ngầm — `amends` mà không có
    `amends_detail` thì không ai truy được điều gì còn hiệu lực.
    """
    decisions = {d["id"]: d for d in _cfg().get("decisions", [])}
    for did, d in decisions.items():
        if "amends" not in d:
            continue
        assert d["amends"] in decisions, (
            f"{did} amend {d['amends']!r} nhưng id đó không có trong registry.")
        assert str(d.get("amends_detail", "")).strip(), (
            f"{did} có `amends` nhưng thiếu `amends_detail` — phải ghi rõ SỬA gì "
            "và GIỮ NGUYÊN gì, nếu không thì không truy được hiệu lực còn lại.")


def test_dual_component_keeps_primary_cell_unresolved():
    """Spec kép KHÔNG được âm thầm chốt ô chính.

    docs/16 §2.2 đề xuất chuyển primary_cell.shock sang spec kép. Làm thế là chốt
    bằng THIẾT KẾ chứ không bằng E1c-exo — đúng thứ mà UNRESOLVED sinh ra để
    tránh. Chốt ô chính phải là chữ ký RIÊNG; tới lúc đó test này giữ hiện trạng.
    """
    cfg = _cfg()
    sca = next(x for x in cfg["specification_curves"] if x["id"] == "SCA-01")
    assert sca["primary_cell"]["shock"] == "UNRESOLVED", (
        "primary_cell.shock đã đổi khỏi UNRESOLVED — đó là quyết định governance "
        "riêng (docs/16 §9.1), cần chữ ký mới + cập nhật test này cùng commit.")
    dec = next(d for d in cfg["decisions"]
               if d["id"] == "DEC-2026-08-03-dual-component")
    assert "UNRESOLVED" in dec["not_yet_decided"]


def test_holm_families_match_report_axis():
    """Họ Holm trong code phải TRÙNG KHÍT SCA-01.report_axis_outcome.

    Đó chính là nội dung quyết định B: dùng lại ranh giới đã pre-register TRƯỚC
    khi nhìn kết quả. Nếu code tự chia họ khác đi thì chữ ký mất nghĩa.
    """
    from gpr_engine.econometrics.multiplicity import PREREGISTERED_OUTCOME_FAMILIES

    sca = next(x for x in _cfg()["specification_curves"] if x["id"] == "SCA-01")
    axis = sca["report_axis_outcome"]
    assert set(axis) == set(PREREGISTERED_OUTCOME_FAMILIES), (
        f"Tên họ lệch: registry={sorted(axis)} vs "
        f"code={sorted(PREREGISTERED_OUTCOME_FAMILIES)}")
    for fam, members in axis.items():
        # registry viết IP/CPI/infl_expectation; code dùng tên CỘT panel.
        assert len(members) == len(PREREGISTERED_OUTCOME_FAMILIES[fam]), (
            f"Họ {fam}: registry có {len(members)} outcome, code có "
            f"{len(PREREGISTERED_OUTCOME_FAMILIES[fam])} — cỡ họ đổi thì ngưỡng "
            "Holm đổi theo, phải đồng bộ trong cùng commit.")
