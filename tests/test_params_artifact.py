"""ParamsArtifact — cau noi offline<->online (docs/18_build_spec.md §1, §3).

Moi test o day khoa MOT dieu kien da ky hoac mot lop loi da gap that, khong phai
kiem cho du. Khong doc file du lieu, khong mang.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from gpr_engine.params import ParamsArtifact, Tier2Params, Tier3Params
from gpr_engine.params.artifact import (
    load_artifact,
    save_artifact,
    tier2_from_estimate,
)
from gpr_engine.params.schema import ArtifactValidationError


def _cell(**kw) -> Tier2Params:
    base = {
        "outcome": "oil", "horizon": 2, "beta": -0.4, "se": 0.1,
        "ci_low": -0.6, "ci_high": -0.2, "ci_kind": "pointwise",
        "sd_regressor": 0.25, "beta_standardized": -0.1, "nobs": 300,
        "converged": True, "inference": "hac", "shock_measure": "GPRD",
    }
    base.update(kw)
    return Tier2Params(**base)


def _art(**kw) -> ParamsArtifact:
    base = {
        "version": "2026-08-a", "data_version": "abc123", "git_commit": "deadbee",
        "fitted_at": dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.UTC),
        "sample_start": dt.date(1990, 1, 1), "sample_end": dt.date(2026, 7, 1),
        "tier2": [_cell()], "claim_ceiling": {"tier2": "predictive"},
    }
    base.update(kw)
    return ParamsArtifact(**base)


# --- lookup ---------------------------------------------------------------
def test_lookup_khop_chinh_xac():
    got = _art().lookup(outcome="oil", horizon=2, shock_measure="GPRD")
    assert got is not None and got.beta == -0.4


def test_lookup_khong_co_thi_None_chu_khong_noi_suy():
    """Horizon 3 khong co thi tra None — KHONG duoc muon horizon 2.

    Noi suy o day la bia mot uoc luong chua tung chay roi gan cho no ve ngoai
    cua so da uoc luong. None -> assess tra magnitude=None -> composer viet
    'chua uoc luong' (nguyen tac #4).
    """
    assert _art().lookup(outcome="oil", horizon=3, shock_measure="GPRD") is None
    assert _art().lookup(outcome="vix", horizon=2, shock_measure="GPRD") is None


def test_lookup_phan_biet_thanh_phan_spec_kep():
    a = _art(tier2=[
        _cell(component="ANTICIPATED", beta=-1.2, beta_standardized=-0.3),
        _cell(component="SURPRISE", beta=-0.4, beta_standardized=-0.1),
    ])
    ant = a.lookup(outcome="oil", horizon=2, shock_measure="GPRD",
                   component="ANTICIPATED")
    sur = a.lookup(outcome="oil", horizon=2, shock_measure="GPRD",
                   component="SURPRISE")
    assert ant.beta < sur.beta                             # tho: ANT lon hon
    assert ant.beta_standardized < sur.beta_standardized   # chuan hoa: van khac


# --- nhan thanh phan: dieu kien DA KY -------------------------------------
def test_component_persistent_shock_bi_cam():
    """`docs/18_build_spec.md` §3 phac Literal["persistent","shock"] — vi pham
    DEC-2026-08-03-dual-component va trung ten voi shocks.persistent_ar."""
    for bad in ("persistent", "shock", "anticipated"):
        with pytest.raises(ArtifactValidationError, match="component"):
            _art(tier2=[_cell(component=bad)]).validate()


def test_component_hop_le_dung_hang_so_cua_shock_axis():
    from gpr_engine.econometrics.shock_axis import COMPONENT_LABELS
    for ok in COMPONENT_LABELS:
        _art(tier2=[_cell(component=ok)]).validate()


# --- hai truc channel KHONG duoc gop --------------------------------------
def test_shock_variant_va_transmission_channel_la_hai_truc():
    _art(tier2=[_cell(shock_variant="act", transmission_channel="energy")]).validate()
    with pytest.raises(ArtifactValidationError, match="shock_variant"):
        _art(tier2=[_cell(shock_variant="energy")]).validate()      # nham truc
    with pytest.raises(ArtifactValidationError, match="transmission_channel"):
        _art(tier2=[_cell(transmission_channel="act")]).validate()  # nham truc


# --- sup-t / quantile loai tru nhau ---------------------------------------
def test_hang_phan_vi_khong_duoc_mang_supt():
    """run_local_projection raise NotImplementedError cho sup-t + quantile."""
    with pytest.raises(ArtifactValidationError, match="sup-t"):
        _art(tier2=[_cell(tau=0.1, ci_kind="supt",
                          inference="lag_augmented")]).validate()


def test_supt_chi_hop_le_voi_lag_augmented():
    with pytest.raises(ArtifactValidationError, match="lag_augmented"):
        _art(tier2=[_cell(ci_kind="supt", inference="hac")]).validate()
    _art(tier2=[_cell(ci_kind="supt", inference="lag_augmented")]).validate()


# --- chuan hoa phai nhat quan ---------------------------------------------
def test_beta_standardized_lech_thi_raise():
    with pytest.raises(ArtifactValidationError, match="beta_standardized"):
        _art(tier2=[_cell(beta_standardized=999.0)]).validate()


# --- tran claim theo tung tang --------------------------------------------
def test_tran_claim_theo_tang_khong_phai_mot_gia_tri():
    a = _art(
        tier3={"VN": Tier3Params(country="VN", horizon=1, beta_global_direct=0.0,
                                 theta_indirect=0.0, lambda_domestic=0.0)},
        claim_ceiling={"tier2": "predictive", "tier3": "association"})
    a.validate()
    assert a.claim_for("tier2") == "predictive"
    assert a.claim_for("tier3") == "association"


def test_thieu_tran_claim_cho_tang_co_so_thi_raise():
    with pytest.raises(ArtifactValidationError, match="claim_ceiling"):
        _art(claim_ceiling={}).validate()


def test_tier3_rong_la_hop_le():
    """vn.yaml chua co `fitted:` -> artifact dau tien co tier3={}. Do la trang
    thai dung, khong phai loi validate."""
    a = _art(tier3={}).validate()
    assert a.tier3 == {}


# --- trung khoa ------------------------------------------------------------
def test_trung_khoa_thi_raise():
    with pytest.raises(ArtifactValidationError, match="trung khoa"):
        _art(tier2=[_cell(), _cell()]).validate()


# --- ghi/doc ---------------------------------------------------------------
def test_save_load_khu_hoi(tmp_path):
    a = _art(percentiles={"AIGPR": {"q95": 192.4, "q99": 274.1}},
             notes={"shock_source": "ai_gpr"})
    save_artifact(a, root=tmp_path)
    b = load_artifact("2026-08-a", root=tmp_path)
    assert b.version == a.version
    assert b.percentiles["AIGPR"]["q95"] == 192.4
    assert b.notes["shock_source"] == "ai_gpr"
    assert len(b.tier2) == 1 and b.tier2[0].beta == -0.4
    assert b.tier2[0].component is None      # NaN -> None, khong thanh "nan"


def test_khong_ghi_de_artifact_da_co(tmp_path):
    a = _art()
    save_artifact(a, root=tmp_path)
    with pytest.raises(FileExistsError, match="IMMUTABLE"):
        save_artifact(a, root=tmp_path)


def test_load_chay_validate(tmp_path):
    """Artifact hong tren dia phai bi bat luc LOAD, khong de online gap."""
    save_artifact(_art(), root=tmp_path)
    p = tmp_path / "2026-08-a" / "tier2.csv"
    df = pd.read_csv(p)
    # cot rong doc lai thanh float64; ep object truoc khi ghi chuoi (pandas 3).
    df["component"] = df["component"].astype(object)
    df.loc[0, "component"] = "persistent"        # nhan bi cam
    df.to_csv(p, index=False)
    with pytest.raises(ArtifactValidationError, match="component"):
        load_artifact("2026-08-a", root=tmp_path)


# --- tu bang estimate_tier2 ------------------------------------------------
def test_tier2_from_estimate_can_cot_chuan_hoa():
    irf = pd.DataFrame({"macro_var": ["oil"], "shock": ["GPR_SURPRISE"],
                        "horizon": [2], "beta": [-0.4], "se": [0.1],
                        "ci_low": [-0.6], "ci_high": [-0.2], "nobs": [300]})
    with pytest.raises(KeyError, match="sd_regressor"):
        tier2_from_estimate(irf, shock_measure="AIGPR", inference="hac")


def test_tier2_from_estimate_khong_doan_thanh_phan_tu_ten_cot():
    """Ten cot `..._SURPRISE` van co the la thu khac — doan sai la gan nham nhan
    cho he so (#9). Phai khai bao tuong minh qua `component_of`."""
    irf = pd.DataFrame({"macro_var": ["oil"], "shock": ["GPR_SURPRISE"],
                        "horizon": [2], "beta": [-0.4], "se": [0.1],
                        "ci_low": [-0.6], "ci_high": [-0.2], "nobs": [300],
                        "sd_regressor": [0.25], "beta_standardized": [-0.1]})
    cells = tier2_from_estimate(irf, shock_measure="AIGPR", inference="hac")
    assert cells[0].component is None
    cells = tier2_from_estimate(irf, shock_measure="AIGPR", inference="hac",
                                component_of={"GPR_SURPRISE": "SURPRISE"})
    assert cells[0].component == "SURPRISE"


def test_tier2_from_estimate_uu_tien_dai_supt_va_ghi_dung_ci_kind():
    irf = pd.DataFrame({"macro_var": ["oil"], "shock": ["GPR_SURPRISE"],
                        "horizon": [2], "beta": [-0.4], "se": [0.1],
                        "ci_low": [-0.6], "ci_high": [-0.2],
                        "ci_low_supt": [-0.8], "ci_high_supt": [0.0],
                        "nobs": [300], "sd_regressor": [0.25],
                        "beta_standardized": [-0.1]})
    c = tier2_from_estimate(irf, shock_measure="AIGPR",
                            inference="lag_augmented")[0]
    assert c.ci_kind == "supt" and c.ci_low == -0.8


# --- noi vao duong online --------------------------------------------------
def test_gamma_from_artifact_dung_beta_chuan_hoa_va_version():
    """Hai khac biet la LY DO ton tai cua artifact (docs/18 §1)."""
    from gpr_engine.pipeline.gamma_lookup import gamma_from_artifact

    a = _art(tier2=[_cell(p_holm=0.01, pvalue=0.005,
                          component="SURPRISE", shock_variant="act")])
    cells, dv = gamma_from_artifact(a)
    assert dv == "2026-08-a@abc123"            # version, khong phai ten file glob
    assert cells[0].standardized == -0.1       # CHUAN HOA, khong phai beta tho
    assert cells[0].standardized != cells[0].beta
    assert cells[0].component == "SURPRISE"


def test_gamma_from_artifact_loc_holm():
    from gpr_engine.pipeline.gamma_lookup import gamma_from_artifact

    a = _art(tier2=[_cell(p_holm=0.5, pvalue=0.4)])       # khong song sot
    assert gamma_from_artifact(a)[0] == []
    assert len(gamma_from_artifact(a, require_holm=False)[0]) == 1
