"""Test khoa config/backtest.yaml — enforce bang MAY, khong bang loi hua.

docs/02 §3.6 + docs/10 F4: data split la ky luat chong data-snooping (CLAUDE.md #3).
Ai sua moc split → test do → CI chan. Neu viec sua la CO CHU DICH (hop le, cuc hiem
— nhu lan thay oos_start 2023 bang split 4 tang khi CHUA co backtest nao chay),
nguoi sua phai cap nhat ca LOCKED_* duoi day trong CUNG commit va giai thich ro
trong commit message — dau vet nay chinh la muc dich cua test.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config" / "backtest.yaml"

# Moc KHOA — chot 2026-07-16 theo docs/08 §4.8 / docs/09 §2.7.
LOCKED_SPLIT = {
    "development":   ["2015-01-01", "2020-12-31"],
    "validation":    ["2021-01-01", "2023-12-31"],
    "pseudo_oos":    ["2024-01-01", "2025-12-31"],
    "final_holdout": ["2026-01-01", "2026-06-30"],
}


def _cfg() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_split_dates_locked():
    cfg = _cfg()
    assert cfg["split"] == LOCKED_SPLIT, (
        "Moc split trong backtest.yaml khac ban khoa! Sua moc split sau khi da "
        "chay backtest = data snooping (CLAUDE.md #3). Neu thay doi nay co chu "
        "dich, cap nhat LOCKED_SPLIT trong cung commit + giai thich ly do.")


def test_final_holdout_touch_flag_consistent():
    """final_holdout cham dung 1 lan: touched=true PHAI kem git commit ghi dau."""
    cfg = _cfg()
    touched = cfg["final_holdout_touched"]
    commit = cfg["final_holdout_touched_commit"]
    if touched:
        assert commit, ("final_holdout_touched=true nhung khong ghi commit — "
                        "phai ghi lai commit tai thoi diem cham de audit.")
    else:
        assert commit is None, ("final_holdout_touched=false nhung co commit? "
                                "Trang thai mau thuan.")


def test_walk_forward_has_purge_and_embargo():
    """Purge + embargo bat buoc (docs/08 §4.8) — IC horizon toi 60 ngay."""
    wf = _cfg()["walk_forward"]
    assert wf["purge_days"] >= 1
    assert wf["embargo_days"] >= 1


def test_gates_are_new_style():
    """Gate cu 'ic_min 0.03 don le' da bo (docs/09 §2.7) — khong duoc quay lai."""
    gates = _cfg()["gates"]
    assert "ic_min" not in gates
    for key in ("require_incremental_ic_positive", "require_ci_reported",
                "require_regime_stability", "require_positive_after_costs"):
        assert gates.get(key) is True, f"gate {key} phai bat"
