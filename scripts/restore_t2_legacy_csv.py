"""restore_t2_legacy_csv.py — dung lai CSV cua `T2_full_3e1bd83a02b8.md`. 🔧 one-off

VI SAO CAN: mot lan chay `run_t2_full.py` voi spec MOI tren CUNG file du lieu da
ghi de CSV cua report cu (ten artifact luc do chi ma hoa data_version, khong ma
hoa spec — da va bang `_spec_version()` + kiem va cham TRUOC khi ghi). File .md
cua report cu con nguyen va tu nhat quan, nhung CSV di kem thi mat.

CACH LAM — va vi sao khong sua truc tiep `run_t2_full.py`:
    `BATTERY_VERSIONS` gio NAM TRONG chu ky `DEC-2026-08-09-policy-shock-control`.
    Sua hang so do trong file, du chi de chay mot lan, se lam
    `test_policy_shock_control_decision_matches_code` do — dung nhu thiet ke.
    Nen script nay OVERRIDE LUC CHAY (gan thuoc tinh tren module da import) va
    KHONG cham file nao. Chu ky nguyen ven, test van xanh.

Spec cua report cu (truoc khi them cu soc chinh sach):
    - ban battery a/b, KHONG co ban c;
    - panel KHONG co cot `mp_surprise` -> 315 thang (2000-02 → 2026-06).
Moi thu khac (INFERENCE, LAGS, HORIZONS, FOCAL, TAUS, SEED, BATTERY_MODE) giu
nguyen, nen ket qua phai TAI LAP CHINH XAC. Script tu doi chieu voi cac con so
in trong file .md cu; lech la BAO, khong ghi.

CHAY:
    python scripts/restore_t2_legacy_csv.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import run_t2_full as t2  # noqa: E402

LEGACY_TAG = "3e1bd83a02b8"
LEGACY_REPORT = t2.REPORTS / f"T2_full_{LEGACY_TAG}.md"

# Con so in trong file .md cu — dung lam cong doi chieu. Lech nghia la spec tai
# lap KHONG phai spec da sinh ra report do, luc do ghi CSV ra la lam gia.
EXPECTED = {
    "n_obs": 315,
    "n_focal_tests": 432,
    "n_raw_sig": 51,
    "n_survive_holm": 22,
    "n_survive_holm_battery": 9,
}


def main() -> None:
    if not LEGACY_REPORT.exists():
        raise SystemExit(f"Khong thay {LEGACY_REPORT} — khong co gi de khoi phuc.")

    out = {k: t2.DATADIR / f"t2_full_{k}_{LEGACY_TAG}.csv"
           for k in ("gamma", "holm", "quantile")}
    exists = [str(p) for p in out.values() if p.exists()]
    if exists:
        raise SystemExit(f"CSV da co, KHONG ghi de: {exists}")

    # --- Override LUC CHAY, khong sua file (xem docstring) -------------------
    t2.BATTERY_VERSIONS = ("a", "b")
    t2.build_policy_shock_monthly = lambda refresh=False: None   # bo cot mp_*

    print("[1/4] Panel tháng (spec CŨ: không có cú sốc chính sách)...")
    panel = t2.build_panel("1990-01-01", None, False)
    families = t2.outcomes_present(panel)
    print(f"      {panel.shape[0]} tháng, {panel.index.min().date()} → "
          f"{panel.index.max().date()}")
    if panel.shape[0] != EXPECTED["n_obs"]:
        raise SystemExit(
            f"Mẫu {panel.shape[0]} tháng ≠ {EXPECTED['n_obs']} của report cũ — "
            "spec không tái lập, DỪNG (ghi ra sẽ là số giả).")

    print("[2/4] Ước lượng γ...")
    gamma = t2.estimate_gamma(panel, families)
    print(f"      {len(gamma)} hàng γ")

    print("[3/4] Holm + phân vị...")
    holm = t2.apply_holm(gamma, families)
    quant = t2.estimate_quantiles(panel, families)

    stats = t2.compute_stats(panel, gamma, holm, quant, families, elapsed=0.0)
    bad = {k: (stats[k], v) for k, v in EXPECTED.items() if stats[k] != v}
    if bad:
        raise SystemExit(
            "Số tái lập KHÔNG khớp report cũ (được / mong đợi): "
            f"{bad}. DỪNG — ghi ra sẽ là CSV không thuộc về report đó.")
    print("      ✅ khớp toàn bộ số của report cũ:")
    for k, v in EXPECTED.items():
        print(f"         {k} = {v}")

    print("[4/4] Ghi CSV...")
    t2.DATADIR.mkdir(parents=True, exist_ok=True)
    gamma.to_csv(out["gamma"], index=False)
    holm.to_csv(out["holm"], index=False)
    quant.to_csv(out["quantile"], index=False)
    for p in out.values():
        print(f"      → {p}")
    print(f"\nDONE. `{LEGACY_REPORT.name}` tái lập được trở lại.")


if __name__ == "__main__":
    main()
