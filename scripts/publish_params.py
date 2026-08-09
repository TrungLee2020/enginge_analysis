"""publish_params.py — chay tang 2 offline roi PUBLISH ra ParamsArtifact.

Day la cai cau cua `docs/18_build_spec.md` §1: research chay o day (cham, dat,
co governance), san pham chi doc artifact (nhanh, khong co bac tu do thong ke).

    python scripts/publish_params.py --version 2026-08-a
    python scripts/publish_params.py --version 2026-08-b --shock-source ai_gpr

Spec chay MAC DINH la spec kep da ky (`DEC-2026-08-03-dual-component`):
ANTICIPATED + SURPRISE trong CUNG mot hoi quy, inference lag_augmented, dai
sup-t. Doi spec o day la doi quyet dinh da ky — phai dong bo registry cung commit.

⚠️ Can mang: `build_monthly_panel` keo macro tu FRED. Trong sandbox Claude Code
`fred.stlouisfed.org` bi CHAN o egress policy (403 tren CONNECT) nen script nay
CHUA chay duoc end-to-end o day; phan khong can mang (dung artifact, validate,
save/load, tra cuu online) co test day du trong tests/test_params_artifact.py.
"""
from __future__ import annotations

import argparse
import datetime as dt

from gpr_engine.econometrics.data_files import (
    DEFAULT_AI_GPR_MONTHLY,
    ai_gpr_vintage,
    build_monthly_panel,
)
from gpr_engine.econometrics.tier2_global_macro import estimate_tier2
from gpr_engine.params.artifact import git_commit, save_artifact, tier2_from_estimate
from gpr_engine.params.schema import ParamsArtifact

# Spec DA KY — sua la sua quyet dinh, khong phai lua chon cua runner.
INFERENCE = "lag_augmented"
SIMULTANEOUS = True
COMPONENT_OF = {"GPR_ANTICIPATED": "ANTICIPATED", "GPR_SURPRISE": "SURPRISE"}
SHOCK_GROUP = list(COMPONENT_OF)
OUTCOMES = ["oil", "dxy", "vix", "us10y"]
# Ho kiem dinh da pre-register (DEC-2026-08-02-holm-family).
FAMILY_OF = {"oil": "asset_price", "dxy": "asset_price",
             "vix": "asset_price", "us10y": "asset_price"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True, help="vd 2026-08-a. IMMUTABLE.")
    ap.add_argument("--shock-source", default="gpr_ci", choices=["gpr_ci", "ai_gpr"])
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--horizons", type=int, default=24)
    ap.add_argument("--root", default="params")
    ap.add_argument("--claim-tier2", default="predictive",
                    choices=["measurement", "association", "predictive"])
    args = ap.parse_args()

    panel = build_monthly_panel(
        start=args.start, dual_component=True, shock_source=args.shock_source,
        real_macro=False)

    irf = estimate_tier2(
        panel, macro_vars=[c for c in OUTCOMES if c in panel.columns],
        shocks=[], shock_groups=[SHOCK_GROUP],
        horizons=range(args.horizons + 1),
        macro_lags=0,                     # lag_augmented tu them lag cua y va shock
        inference=INFERENCE, simultaneous=SIMULTANEOUS)

    measure = "AIGPR" if args.shock_source == "ai_gpr" else "GPRD"
    cells = tier2_from_estimate(
        irf, shock_measure=measure, inference=INFERENCE,
        component_of=COMPONENT_OF, family_of=FAMILY_OF)

    # Nguong phan vi de ONLINE khong phai tinh lai tren toan lich su (docs/18 §1).
    pct = {}
    for col in SHOCK_GROUP:
        s = panel[col].dropna()
        pct[col] = {"q95": float(s.quantile(0.95)), "q99": float(s.quantile(0.99)),
                    "sd": float(s.std())}

    art = ParamsArtifact(
        version=args.version,
        data_version=(ai_gpr_vintage(DEFAULT_AI_GPR_MONTHLY) or "unknown")
        if args.shock_source == "ai_gpr" else "gpr_ci",
        git_commit=git_commit(),
        fitted_at=dt.datetime.now(dt.UTC),
        sample_start=panel.index.min().date(),
        sample_end=panel.index.max().date(),
        tier2=cells,
        tier3={},                 # vn.yaml chua co `fitted:` — trang thai HOP LE
        percentiles=pct,
        claim_ceiling={"tier2": args.claim_tier2},
        notes={"shock_source": args.shock_source, "spec": "dual_component",
               "n_obs_panel": len(panel)},
    )
    out = save_artifact(art, root=args.root)
    print(f"Da publish {out} — {len(cells)} o tier2, mau "
          f"{art.sample_start} -> {art.sample_end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
