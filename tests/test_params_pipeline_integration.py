"""Tich hop: panel -> tier2 -> artifact -> tra cuu online (docs/18 §6 'integration').

GPR doc FILE THAT trong data/. Macro bi TIEM GIA vi fred.stlouisfed.org bi chan
o egress policy sandbox (403 tren CONNECT).

⚠️ Vi outcome la nhieu ngau nhien, GIA TRI he so o day VO NGHIA. Test nay chi
khoa CAU TRUC duong ong — dung doc bat ky con so nao tu no nhu ket qua kinh te
luong. Ket qua that phai chay qua scripts/publish_params.py voi FRED that.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from gpr_engine.econometrics import data_files as D
from gpr_engine.econometrics.tier2_global_macro import estimate_tier2
from gpr_engine.params.artifact import (
    git_commit,
    load_artifact,
    save_artifact,
    tier2_from_estimate,
)
from gpr_engine.params.schema import ParamsArtifact
from gpr_engine.pipeline.gamma_lookup import gamma_from_artifact

COMPONENT_OF = {"GPR_ANTICIPATED": "ANTICIPATED", "GPR_SURPRISE": "SURPRISE"}


@pytest.fixture
def panel(monkeypatch) -> pd.DataFrame:
    idx = pd.date_range("1985-01-01", "2026-07-01", freq="MS")
    rng = np.random.default_rng(1)
    monkeypatch.setattr(D, "load_macro_monthly", lambda *a, **k: pd.DataFrame(
        {c: rng.normal(0, 1, len(idx)) for c in ("oil", "dxy", "vix", "us10y")},
        index=idx))
    return D.build_monthly_panel(start="1990-01-01", dual_component=True)


def test_duong_ong_day_du(panel, tmp_path):
    irf = estimate_tier2(
        panel, macro_vars=["oil"], shocks=[], shock_groups=[list(COMPONENT_OF)],
        horizons=range(3), macro_lags=0,
        inference="lag_augmented", simultaneous=True)
    cells = tier2_from_estimate(irf, shock_measure="GPRD",
                                inference="lag_augmented",
                                component_of=COMPONENT_OF)
    art = ParamsArtifact(
        version="test-int", data_version="dv1", git_commit=git_commit(),
        fitted_at=dt.datetime.now(dt.UTC),
        sample_start=panel.index.min().date(), sample_end=panel.index.max().date(),
        tier2=cells, claim_ceiling={"tier2": "predictive"})
    save_artifact(art, root=tmp_path)
    back = load_artifact("test-int", root=tmp_path)

    # 3 horizon x 2 thanh phan, khong lan he so lag augmentation.
    assert len(back.tier2) == 6
    assert {c.component for c in back.tier2} == {"ANTICIPATED", "SURPRISE"}
    hit = back.lookup(outcome="oil", horizon=2, shock_measure="GPRD",
                      component="SURPRISE")
    assert hit is not None
    assert hit.ci_kind == "supt"                   # lag_augmented + simultaneous
    assert hit.sd_regressor > 0
    assert np.isclose(hit.beta_standardized, hit.beta * hit.sd_regressor)
    cs, dv = gamma_from_artifact(back, require_holm=False)
    assert len(cs) == 6 and dv == "test-int@dv1"


def test_online_khong_import_statsmodels():
    """Rang buoc kien truc §1 viet thanh code: duong ONLINE khong duoc fit gi.

    `params` va `pipeline.gamma_lookup` la thu online cham vao — chung khong
    duoc keo statsmodels/sklearn vao request path.
    """
    import ast
    import pathlib

    for f in ["src/gpr_engine/params/schema.py",
              "src/gpr_engine/params/artifact.py",
              "src/gpr_engine/pipeline/gamma_lookup.py"]:
        tree = ast.parse(pathlib.Path(f).read_text(encoding="utf-8"))
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        bad = [m for m in mods if m.split(".")[0] in {"statsmodels", "sklearn",
                                                      "linearmodels", "arch"}]
        assert not bad, f"{f} import {bad} — duong online khong duoc fit gi (§1)"
