"""schema.py — kieu du lieu cua ParamsArtifact.

Dung `dataclasses`, KHONG dung pydantic nhu `docs/18_build_spec.md` §3 phac:
pydantic chi co mat trong moi truong nay nhu phu thuoc GIAN TIEP cua `openai`,
va repo dang dung dataclass o moi noi khac (`statement_scorer.Statement`,
`composer.GammaCell`, `analogue.AnalogueResult`). Them mot phu thuoc truc tiep
chi de validate la khong dang; `validate()` o day kiem tay dung nhung dieu can
kiem — va kiem duoc CA nhung thu pydantic khong biet (chu ky da ky, tran claim
theo tang, quan he giua tau va ci_kind).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

from ..econometrics.shock_axis import COMPONENT_LABELS

# Bien the GPRD dung lam SHOCK. KHONG PHAI kenh truyen dan — xem
# `TRANSMISSION_CHANNELS`. Gop hai truc nay vao mot truong `channel: str` la loi
# ma `docs/18_build_spec.md` §3 chi ra: bang γ hien tai tach theo truc thu nhat,
# con san pham noi ve truc thu hai, va `commitment_to_gamma_channel` chi la proxy.
SHOCK_VARIANTS = ("pooled", "act", "threat")
TRANSMISSION_CHANNELS = ("energy", "trade", "financial", "military")

# Thanh phan cua spec kep. Lay THANG tu shock_axis.COMPONENT_LABELS — khong dat
# lai ten o day, va TUYET DOI khong dung ("persistent", "shock"):
#   - "persistent" da la ten cua mot object KHAC (`shocks.persistent_ar` =
#     E[LEVEL], gan nghiem don vi), trung ten trong wire format song rat lau;
#   - goi thanh phan kia la "shock" ngam khang dinh ANTICIPATED khong phai cu
#     soc — dung cach doc ma CLAUDE.md #9 cam, va la dieu kien da ky cua
#     DEC-2026-08-03-dual-component (cong may: check_component_labelling).
COMPONENTS = tuple(COMPONENT_LABELS)          # ("ANTICIPATED", "SURPRISE")

CI_KINDS = ("pointwise", "supt")
INFERENCE_MODES = ("hac", "lag_augmented")
CLAIM_LEVELS = ("measurement", "association", "predictive")
# Tran claim khai bao theo TUNG TANG, khong phai mot gia tri cho ca artifact:
# tier2 co the la `predictive` trong khi tier3["VN"] van la `association` cho
# toi khi config/params/vn.yaml co muc `fitted:` (nguyen tac #4).
ARTIFACT_CLAIM_TIERS = ("tier2", "tier3")


class ArtifactValidationError(ValueError):
    """Artifact khong hop le. Raise SOM (luc publish/load), khong de online gap."""


@dataclass(frozen=True)
class Tier2Params:
    """Mot o cua bang γ tang 2, da uoc luong, san sang tra cuu online."""
    outcome: str
    horizon: int
    beta: float
    se: float
    ci_low: float
    ci_high: float
    ci_kind: str                       # pointwise | supt
    sd_regressor: float
    beta_standardized: float
    nobs: int
    converged: bool
    inference: str                     # hac | lag_augmented
    shock_measure: str                 # AIGPR | GPRD | GPRD_ACT ...
    shock_variant: str | None = None   # pooled | act | threat
    component: str | None = None       # ANTICIPATED | SURPRISE (spec kep)
    transmission_channel: str | None = None   # energy | trade | financial | military
    tau: float | None = None           # None = OLS
    p_holm: float | None = None
    family: str | None = None
    pvalue: float | None = None

    def key(self) -> tuple:
        """Khoa dinh danh mot o — dung de bat trung trong `validate()`."""
        return (self.outcome, self.horizon, self.shock_measure, self.shock_variant,
                self.component, self.transmission_channel, self.tau, self.inference)


@dataclass(frozen=True)
class Tier3Params:
    """β/θ/λ cua MOT nuoc. Ba he so TACH RIENG (CLAUDE.md #8) — gop β voi λ la loi.

    β = global-direct (soc toan cau danh thang, khong qua macro)
    θ = indirect (qua kenh vi mo; tinh bang TICH CHAP qua horizon, khong nhan
        hai he so cung horizon)
    λ = domestic-direct (tu GPR^{c,⊥} da orthogonalize khoi global)
    """
    country: str
    horizon: int
    beta_global_direct: float
    theta_indirect: float
    lambda_domestic: float
    se_beta: float | None = None
    se_theta: float | None = None
    se_lambda: float | None = None


@dataclass
class ParamsArtifact:
    """Bo tham so IMMUTABLE, co version — thu duy nhat online duoc phep doc.

    `tier3` RONG la trang thai HOP LE, khong phai loi: `config/params/vn.yaml`
    chua co muc `fitted:`, nen artifact dau tien se co `tier3={}`. Online gap
    rong -> `magnitude=None` -> composer viet dinh tinh (nguyen tac #4).
    """
    version: str
    data_version: str
    git_commit: str
    fitted_at: dt.datetime
    sample_start: dt.date
    sample_end: dt.date
    tier2: list[Tier2Params] = field(default_factory=list)
    tier3: dict[str, Tier3Params] = field(default_factory=dict)
    percentiles: dict[str, dict[str, float]] = field(default_factory=dict)
    claim_ceiling: dict[str, str] = field(default_factory=dict)
    notes: dict[str, Any] = field(default_factory=dict)

    # -- tra cuu ------------------------------------------------------------
    def lookup(
        self,
        *,
        outcome: str,
        horizon: int,
        shock_measure: str,
        shock_variant: str | None = None,
        component: str | None = None,
        transmission_channel: str | None = None,
        tau: float | None = None,
        inference: str | None = None,
    ) -> Tier2Params | None:
        """Khop CHINH XAC. `None` => CHUA uoc luong => assess KHONG noi do lon.

        KHONG noi suy, KHONG lay o gan nhat: horizon 3 khong co thi tra None,
        khong duoc muon horizon 2. Noi suy o day la bia mot uoc luong chua tung
        chay va gan cho no ve ngoai cua so da uoc luong.
        """
        hits = [
            p for p in self.tier2
            if p.outcome == outcome
            and p.horizon == horizon
            and p.shock_measure == shock_measure
            and p.shock_variant == shock_variant
            and p.component == component
            and p.transmission_channel == transmission_channel
            and p.tau == tau
            and (inference is None or p.inference == inference)
        ]
        if not hits:
            return None
        if len(hits) > 1:
            raise ArtifactValidationError(
                f"lookup khop {len(hits)} o cho cung mot khoa — artifact "
                f"{self.version} bi trung. Chay validate() truoc khi publish.")
        return hits[0]

    def claim_for(self, tier: str) -> str:
        if tier not in ARTIFACT_CLAIM_TIERS:
            raise ValueError(f"tier={tier!r} khong thuoc {ARTIFACT_CLAIM_TIERS}")
        return self.claim_ceiling.get(tier, "measurement")

    # -- kiem tra -----------------------------------------------------------
    def validate(self) -> ParamsArtifact:
        """Raise `ArtifactValidationError` neu artifact khong dung hop dong.

        Chay luc PUBLISH va luc LOAD. Moi thu kiem o day deu la mot lop loi da
        gap that hoac mot dieu kien da ky, khong phai kiem cho du.
        """
        errs: list[str] = []
        if not self.version:
            errs.append("version rong — artifact khong co version thi moi nhan "
                        "dinh mat duong truy nguoc (chinh la thu §1 sinh ra de vá).")
        if not self.data_version:
            errs.append("data_version rong (#7: ghim vintage moi nguon).")
        if not self.git_commit:
            errs.append("git_commit rong (#4: ket qua kem git commit).")
        if self.sample_end < self.sample_start:
            errs.append(f"sample nguoc: {self.sample_start} > {self.sample_end}")

        for tier, level in self.claim_ceiling.items():
            if tier not in ARTIFACT_CLAIM_TIERS:
                errs.append(f"claim_ceiling co tang la: {tier!r}")
            if level not in CLAIM_LEVELS:
                errs.append(f"claim_ceiling[{tier!r}]={level!r} khong thuoc "
                            f"{CLAIM_LEVELS}")
        if self.tier2 and "tier2" not in self.claim_ceiling:
            errs.append("co tier2 nhung thieu claim_ceiling['tier2'] — tran claim "
                        "phai di CUNG so, khong de nguoi doc tu suy (#12).")
        if self.tier3 and "tier3" not in self.claim_ceiling:
            errs.append("co tier3 nhung thieu claim_ceiling['tier3'].")

        seen: dict[tuple, int] = {}
        for i, p in enumerate(self.tier2):
            errs.extend(f"tier2[{i}]: {m}" for m in _validate_cell(p))
            k = p.key()
            if k in seen:
                errs.append(f"tier2[{i}] trung khoa voi tier2[{seen[k]}]: {k}")
            seen[k] = i

        for country, t3 in self.tier3.items():
            if t3.country != country:
                errs.append(f"tier3[{country!r}].country={t3.country!r} — lech khoa")

        if errs:
            raise ArtifactValidationError(
                f"Artifact {self.version!r} khong hop le:\n  - "
                + "\n  - ".join(errs))
        return self

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "data_version": self.data_version,
            "git_commit": self.git_commit,
            "fitted_at": self.fitted_at.isoformat(),
            "sample_start": self.sample_start.isoformat(),
            "sample_end": self.sample_end.isoformat(),
            "tier3": {k: asdict(v) for k, v in self.tier3.items()},
            "percentiles": self.percentiles,
            "claim_ceiling": self.claim_ceiling,
            "notes": self.notes,
            "n_tier2": len(self.tier2),
        }


def _validate_cell(p: Tier2Params) -> list[str]:
    errs: list[str] = []
    if p.component is not None and p.component not in COMPONENTS:
        errs.append(
            f"component={p.component!r} khong thuoc {COMPONENTS}. Dac biet: "
            "'persistent'/'shock' BI CAM — 'persistent' trung ten voi "
            "shocks.persistent_ar (object khac), va goi thanh phan kia la "
            "'shock' vi pham CLAUDE.md #9 (dieu kien da ky cua "
            "DEC-2026-08-03-dual-component).")
    if p.shock_variant is not None and p.shock_variant not in SHOCK_VARIANTS:
        errs.append(f"shock_variant={p.shock_variant!r} khong thuoc {SHOCK_VARIANTS}")
    if (p.transmission_channel is not None
            and p.transmission_channel not in TRANSMISSION_CHANNELS):
        errs.append(f"transmission_channel={p.transmission_channel!r} khong thuoc "
                    f"{TRANSMISSION_CHANNELS}")
    if p.ci_kind not in CI_KINDS:
        errs.append(f"ci_kind={p.ci_kind!r} khong thuoc {CI_KINDS}")
    if p.inference not in INFERENCE_MODES:
        errs.append(f"inference={p.inference!r} khong thuoc {INFERENCE_MODES}")
    if p.tau is not None and not (0.0 < p.tau < 1.0):
        errs.append(f"tau={p.tau} phai trong (0,1)")
    if p.tau is not None and p.ci_kind == "supt":
        errs.append(
            f"o tau={p.tau} mang ci_kind='supt': dai sup-t cho hoi quy phan vi "
            "CHUA lam (run_local_projection raise NotImplementedError — ham anh "
            "huong cua QuantReg can bootstrap). Hang phan vi phai la 'pointwise' "
            "va report phai ghi ro khong hieu chinh dong thoi theo horizon.")
    if p.ci_kind == "supt" and p.inference != "lag_augmented":
        errs.append(
            f"ci_kind='supt' voi inference={p.inference!r}: sup-t chi hop le voi "
            "lag_augmented (Ω tu EHW; ghep voi SE HAC la hai bo sai so chuan "
            "trong mot dai).")
    if p.nobs <= 0:
        errs.append(f"nobs={p.nobs}")
    if p.sd_regressor <= 0:
        errs.append(f"sd_regressor={p.sd_regressor} — phai duong de chuan hoa "
                    "co nghia")
    expected = p.beta * p.sd_regressor
    if abs(p.beta_standardized - expected) > 1e-9 * max(1.0, abs(expected)):
        errs.append(
            f"beta_standardized={p.beta_standardized} != beta*sd_regressor="
            f"{expected}. Hai truong nay phai nhat quan: online doc truong chuan "
            "hoa de khoi dung lai panel, lech nhau la san pham noi mot dang con "
            "research noi mot dang.")
    return errs
