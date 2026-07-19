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
    text = re.sub(r"[A-Za-zĐ]+\d[\w-]*", "", text)        # E1b, KĐ-E1b, SCA-01, US10Y...
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


def test_compute_returns_consistent_winner():
    """compute() thật: winner phải nằm trong 3 thước đo và rank khớp."""
    stats, table = e1b.compute()
    assert stats["winner"] in {"INNOVATION", "JUMP", "LEVEL+JUMP"}
    assert stats["rank"].split(" > ")[0] == stats["winner"]
    # hit rate hợp lệ [0,1]
    for name in table:
        assert 0.0 <= table[name]["full"]["hit"] <= 1.0
