"""test_report_guard_p1.py — Guard P1: mọi số trong narrative report phải từ payload.

docs/11 §1 P1 / docs/12 §5.4: LLM/generator KHÔNG được sinh số tự do; mọi con số
trong văn bản phải khớp một trường trong dict tính sẵn. Bug đã xảy ra thật:
run_e1_diagnosis narrate "~1.8×" trong khi payload = 2.77×.

Chiến lược: gọi build_report với stats/table CÓ KIỂM SOÁT (giá trị "đánh dấu" dễ
nhận), trích mọi token số trong narrative, và assert mỗi số khớp một giá trị suy
ra được từ payload (bản thân giá trị, hoặc *100 cho phần trăm, hoặc hằng số cấu
hình đã biết). Số lạc = generator bịa số → test đỏ.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_e1b_shock_ranking as e1b  # noqa: E402
import run_e1c_shock_detection as e1c  # noqa: E402

# Hằng số cấu hình được phép xuất hiện trong narrative (ngưỡng, năm, mốc mô tả).
CONFIG_NUMBERS = {
    2.0,                       # HIT_SD
    0.975, 97.5,               # EVENT_Q và %
    250,                       # ROLL
    10,                        # DEDUP_DAYS
    1990,                      # START year
    100,                       # hệ số phần trăm
    2008, 2007, 2015, 2016,    # mốc sub-sample
    3,                         # "ba mức" / "ba thước đo"
    1, 2,                      # đếm nhỏ trong văn xuôi
}

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _payload_values(stats: dict, table: dict) -> set[float]:
    """Tập giá trị hợp lệ suy ra từ payload: mỗi số + biến thể *100 (phần trăm)."""
    vals: set[float] = set(CONFIG_NUMBERS)
    raw: list[float] = []
    for v in stats.values():
        if isinstance(v, (int, float)):
            raw.append(float(v))
    for name in table:
        for sub in table[name]:
            cell = table[name][sub]
            raw += [float(cell["mean_z"]), float(cell["hit"]), float(cell["n"])]
    for x in raw:
        vals.add(round(x, 4))
        vals.add(round(x * 100, 4))     # hit 0.69 -> "69%"
        vals.add(float(int(round(x * 100))))  # làm tròn phần trăm hiển thị
        vals.add(float(int(x)) if x == int(x) else x)
    return vals


def _tokens(parts: list[str]) -> list[str]:
    text = "\n".join(parts)
    # Bỏ các pattern KHÔNG phải "số kết quả": hash, ngày, và mã tham chiếu tài liệu
    # (docs/11, §10, sha256, E1b, KĐ-E1b...). Guard P1 chỉ soi số định lượng.
    text = re.sub(r"`[0-9a-f]{6,}`", "", text)            # data_version/commit hash
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T0-9:]*", "", text)  # ngày ISO
    text = re.sub(r"docs/\d+", "", text)                  # docs/11, docs/12
    text = re.sub(r"§\s*[\d.]+", "", text)                # §10, §2.2, §5.4
    text = re.sub(r"sha256", "", text)                    # nhãn hash
    text = re.sub(r"\d{4}\s*[-–]\s*\d{4}", "", text)      # range năm sub-sample 2008-2015
    text = re.sub(r"(?<![.\d])\d{4}(?![.\d])", "", text)  # mốc năm đơn (1990, 2015)
    text = re.sub(r"[A-Za-zĐ]+-?\d[\w-]*", "", text)      # E1b, KĐ-E1b, SCA-01, US10Y...
    text = re.sub(r"\d+σ", "", text)                      # 2σ, 4σ (ngưỡng mô tả)
    return NUM_RE.findall(text)


def _fake_payload() -> tuple[dict, dict]:
    """stats/table giả với giá trị đánh dấu — winner = JUMP để có ranking rõ."""
    def cell(mz, hit, n):
        return {"mean_z": round(mz, 2), "hit": round(hit, 3), "n": n}
    table = {
        "INNOVATION": {"full": cell(1.80, 0.33, 166), "pre-2008": cell(1.5, 0.30, 40),
                       "2008-2015": cell(1.7, 0.32, 50), "post-2015": cell(1.9, 0.35, 76)},
        "JUMP":       {"full": cell(2.70, 0.56, 166), "pre-2008": cell(2.5, 0.52, 40),
                       "2008-2015": cell(2.6, 0.55, 50), "post-2015": cell(2.8, 0.58, 76)},
        "LEVEL+JUMP": {"full": cell(2.90, 0.69, 166), "pre-2008": cell(2.7, 0.65, 40),
                       "2008-2015": cell(2.8, 0.68, 50), "post-2015": cell(3.0, 0.71, 76)},
    }
    stats = {
        "ar_order": 5,
        "n_events_full": 166,
        "winner": "LEVEL+JUMP",
        "rank": "LEVEL+JUMP > JUMP > INNOVATION",
        "winner_hit_full": 0.69,
        "winner_meanz_full": 2.90,
        "innov_hit_full": 0.33,
        "jump_hit_full": 0.56,
        "winner_always_top": True,
    }
    return stats, table


def test_every_number_in_narrative_comes_from_payload():
    stats, table = _fake_payload()
    parts = e1b.build_report(stats, table, dv="deadbeef", commit="abc1234",
                             now="2026-07-19T10:00:00")
    allowed = _payload_values(stats, table)
    bad = []
    for tok in _tokens(parts):
        val = float(tok)
        if round(val, 4) not in allowed and float(int(val)) not in allowed \
                and (val != int(val) or float(int(val)) not in allowed):
            bad.append(tok)
    assert not bad, (
        f"Số trong narrative KHÔNG khớp payload (Guard P1 vi phạm): {bad}. "
        "Mọi số phải tính từ stats/table, không hard-code (docs/12 §5.4).")


def test_guard_catches_hardcoded_number():
    """Chứng minh guard thực sự bắt được số bịa — chèn số lạ, phải phát hiện."""
    stats, table = _fake_payload()
    parts = e1b.build_report(stats, table, dv="deadbeef", commit="abc1234",
                             now="2026-07-19T10:00:00")
    parts.append("Cú sốc gấp 42.7× ngày thường.")   # số bịa, KHÔNG có trong payload
    allowed = _payload_values(stats, table)
    nums = [t for t in _tokens(parts) if round(float(t), 4) not in allowed
            and float(int(float(t))) not in allowed]
    assert "42.7" in nums, "guard phải phát hiện 42.7 là số lạ không có trong payload"


# ---------------------------------------------------------------------------
# E1c — cùng guard, payload khác hình (AUC + CI thay mean_z/hit)
# ---------------------------------------------------------------------------
E1C_CONFIG_NUMBERS = {
    e1c.B_BOOT, e1c.SEED, e1c.ROLL, e1c.EVENT_BUFFER, e1c.EVENT_WINDOW,
    0.975, 97.5,               # ngưỡng episode endo
    95,                        # nhãn "CI 95%"
    4,                         # 4 thước đo / Holm trên 4×H
    0.5,                       # AUC ngẫu nhiên
    1990, 2007, 2008, 2015, 2016,
    1, 2, 3, 100,
}


def _e1c_payload_values(stats: dict, table: dict) -> set[float]:
    """Giá trị hợp lệ suy ra từ payload E1c: stats số + auc/n_event/n_control + CI."""
    vals: set[float] = {float(x) for x in E1C_CONFIG_NUMBERS}
    raw: list[float] = [float(v) for v in stats.values()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for name in table:
        for key, cell in table[name].items():
            if key == "ci_full":
                raw += [float(x) for x in cell]
            else:
                raw += [float(cell["auc"]), float(cell["n_event"]),
                        float(cell["n_control"])]
    for x in raw:
        vals.add(round(x, 4))
        vals.add(round(x * 100, 4))
        vals.add(float(int(x)) if x == int(x) else x)
    return vals


def _e1c_unmatched(parts: list[str], allowed: set[float]) -> list[str]:
    """Token số không suy ra được từ payload.

    Khác `_payload_values` của E1b: fallback cắt phần thập phân CHỈ áp cho token
    vốn là số nguyên. Nếu không, payload chứa 0 (n_exo_events khi chưa có gold set)
    sẽ nuốt mọi số bịa dạng 0.xxx và guard mất tác dụng.
    """
    bad = []
    for tok in _tokens(parts):
        val = float(tok)
        if round(val, 4) in allowed:
            continue
        if val == int(val) and float(int(val)) in allowed:
            continue
        bad.append(tok)
    return bad


def _fake_e1c_payload() -> tuple[dict, dict]:
    """Bảng AUC giả, giá trị đánh dấu. Không phản ánh kết quả thật."""
    def cell(a, ne, nc):
        return {"auc": a, "n_event": ne, "n_control": nc}

    def row(base):
        t = {s: cell(round(base + i * 0.01, 3), 120 + i, 9000 + i)
             for i, s in enumerate(e1c.SUBSAMPLES)}
        t["ci_full"] = [round(base - 0.03, 3), round(base + 0.03, 3)]
        return t

    table = {"LEVEL+JUMP": row(0.774), "LEVEL": row(0.740),
             "JUMP": row(0.719), "INNOVATION": row(0.712)}
    ranked = e1c.rank(table)
    stats = {
        "ar_order": 5,
        "n_endo_events": 166,
        "n_exo_events": 0,
        "endo_rank": " > ".join(ranked),
        "endo_winner": ranked[0],
        "exo_available": False,
    }
    return stats, table


def test_e1c_every_number_in_narrative_comes_from_payload():
    """Cùng bất biến P1 cho E1c (docs/13 §2.6) — generator không được bịa số."""
    stats, table = _fake_e1c_payload()
    parts = e1c.build_report(stats, table, None, dv="deadbeef", commit="abc1234",
                             now="2026-07-19T10:00:00")
    bad = _e1c_unmatched(parts, _e1c_payload_values(stats, table))
    assert not bad, (
        f"Số trong narrative E1c KHÔNG khớp payload (Guard P1 vi phạm): {bad}. "
        "Thêm số vào report thì thêm trường vào stats rồi tham chiếu (docs/12 §5.4).")


def test_e1c_guard_catches_hardcoded_number():
    """Guard phải bắt được số bịa trong nhánh EXO (nhánh sẽ dùng khi có gold set)."""
    stats, table = _fake_e1c_payload()
    stats = {**stats, "exo_available": True, "n_exo_events": 52,
             "exo_rank": stats["endo_rank"], "exo_winner": stats["endo_winner"]}
    parts = e1c.build_report(stats, table, table, dv="deadbeef", commit="abc1234",
                             now="2026-07-19T10:00:00")
    parts.append("AUC vượt 0.913 ở mọi sub-sample.")   # số bịa, không có trong payload
    bad = _e1c_unmatched(parts, _e1c_payload_values(stats, table))
    assert "0.913" in bad, "guard phải phát hiện 0.913 là số lạ không có trong payload"


def test_e1c_rank_orders_by_full_auc():
    """rank() phải sắp theo AUC full giảm dần — trụ đỡ của mọi câu 'thắng' trong report."""
    _, table = _fake_e1c_payload()
    ranked = e1c.rank(table)
    aucs = [table[n]["full"]["auc"] for n in ranked]
    assert aucs == sorted(aucs, reverse=True), f"rank không giảm dần: {list(zip(ranked, aucs))}"


def test_compute_returns_consistent_winner():
    """compute() thật: winner phải nằm trong 3 thước đo và rank khớp."""
    stats, table = e1b.compute()
    assert stats["winner"] in {"INNOVATION", "JUMP", "LEVEL+JUMP"}
    assert stats["rank"].split(" > ")[0] == stats["winner"]
    # hit rate hợp lệ [0,1]
    for name in table:
        assert 0.0 <= table[name]["full"]["hit"] <= 1.0
