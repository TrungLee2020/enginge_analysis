"""artifact.py — doc/ghi/dung ParamsArtifact tu dia.

Dinh dang: `tier2.csv` + `meta.json` trong mot thu muc `<root>/<version>/`.
`docs/18_build_spec.md` §5 ghi Parquet; doi sang CSV+JSON vi (a) parquet can
`pyarrow`/`fastparquet`, khong co trong `pyproject.toml` va khong dang them chi
de luu vai nghin hang; (b) CSV dong bo voi `docs/reports/data/*.csv` da co, va
diff duoc trong review — mot bo tham so doi gia tri thi nhin thay ngay tren PR.
Doi sang parquet sau khong pha API: caller chi dung `save_artifact`/`load_artifact`.

QUY UOC KHONG GHI DE (giong report versioned trong `docs/reports/`):
`save_artifact` raise `FileExistsError` neu thu muc version da ton tai. Artifact
la IMMUTABLE — sua tai cho thi hai nhan dinh cung tro ve mot `version` ma so lai
khac nhau, dung lop loi ma §1 sinh ra de vá.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import fields
from pathlib import Path

import pandas as pd

from .schema import (
    ArtifactValidationError,
    ParamsArtifact,
    Tier2Params,
    Tier3Params,
)

DEFAULT_PARAMS_ROOT = Path("params")
TIER2_FILE = "tier2.csv"
META_FILE = "meta.json"


def git_commit(short: bool = True) -> str:
    """Commit HEAD hien tai, hoac 'unknown' neu khong o trong git repo.

    KHONG raise: publish artifact tu mot ban giai nen (khong co .git) van hop le,
    chi la truy nguoc yeu hon — va `validate()` van bat truong rong.
    """
    cmd = ["git", "rev-parse", "--short", "HEAD"] if short else ["git", "rev-parse", "HEAD"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def tier2_from_estimate(
    irf: pd.DataFrame,
    *,
    shock_measure: str,
    inference: str,
    shock_variant: str | None = None,
    transmission_channel: str | None = None,
    tau: float | None = None,
    component_of: dict[str, str] | None = None,
    family_of: dict[str, str] | None = None,
) -> list[Tier2Params]:
    """Bang ra cua `estimate_tier2` -> list[Tier2Params].

    `component_of`: anh xa ten regressor -> thanh phan spec kep, vi du
    ``{"GPR_ANTICIPATED": "ANTICIPATED", "GPR_SURPRISE": "SURPRISE"}``. Khong
    doan tu ten cot: mot chuoi ten `..._SURPRISE` van co the la thu khac, va
    doan sai o day la gan nham nhan cho he so (#9).

    Doi hoi `irf` co `sd_regressor`/`beta_standardized` — tuc phai chay
    `estimate_tier2(..., shock_groups=...)`. Bang tu nhanh `shocks` mot regressor
    khong co hai cot do; ep chuan hoa ho o day se phai tinh lai sd tu panel, ma
    panel khong con o day nua.
    """
    need = {"outcome", "horizon", "beta", "se", "ci_low", "ci_high", "nobs"}
    alias = {"macro_var": "outcome"}
    df = irf.rename(columns=alias)
    missing = need - set(df.columns)
    if missing:
        raise KeyError(f"irf thieu cot {sorted(missing)}. Co: {list(df.columns)}")
    if "beta_standardized" not in df.columns or "sd_regressor" not in df.columns:
        raise KeyError(
            "irf thieu sd_regressor/beta_standardized — chay estimate_tier2 voi "
            "`shock_groups=` (nhanh do moi tinh chuan hoa). Bat buoc co vi online "
            "doc truong chuan hoa, khong dung lai panel de tu tinh.")

    has_supt = "ci_low_supt" in df.columns and df["ci_low_supt"].notna().any()
    out: list[Tier2Params] = []
    for _, r in df.iterrows():
        name = str(r.get("shock", shock_measure))
        use_supt = has_supt and pd.notna(r.get("ci_low_supt"))
        out.append(Tier2Params(
            outcome=str(r["outcome"]),
            horizon=int(r["horizon"]),
            beta=float(r["beta"]),
            se=float(r["se"]),
            ci_low=float(r["ci_low_supt"] if use_supt else r["ci_low"]),
            ci_high=float(r["ci_high_supt"] if use_supt else r["ci_high"]),
            ci_kind="supt" if use_supt else "pointwise",
            sd_regressor=float(r["sd_regressor"]),
            beta_standardized=float(r["beta_standardized"]),
            nobs=int(r["nobs"]),
            converged=bool(r.get("converged", True)),
            inference=inference,
            shock_measure=shock_measure,
            shock_variant=shock_variant,
            component=(component_of or {}).get(name),
            transmission_channel=transmission_channel,
            tau=tau,
            p_holm=_opt_float(r.get("pvalue_adj")),
            family=(family_of or {}).get(str(r["outcome"])) or _opt_str(r.get("family")),
            pvalue=_opt_float(r.get("pvalue")),
        ))
    return out


def save_artifact(art: ParamsArtifact, root: Path | str = DEFAULT_PARAMS_ROOT) -> Path:
    """Ghi `<root>/<version>/`. Raise `FileExistsError` neu da co (immutable)."""
    art.validate()
    d = Path(root) / art.version
    if d.exists():
        raise FileExistsError(
            f"{d} da ton tai. Artifact la IMMUTABLE: sua tai cho lam hai nhan dinh "
            "cung tro ve mot version ma so lai khac nhau. Dung version moi.")
    d.mkdir(parents=True)
    _tier2_frame(art.tier2).to_csv(d / TIER2_FILE, index=False)
    (d / META_FILE).write_text(json.dumps(art.to_dict(), indent=2, ensure_ascii=False),
                               encoding="utf-8")
    return d


def load_artifact(version: str, root: Path | str = DEFAULT_PARAMS_ROOT) -> ParamsArtifact:
    """Doc lai artifact va `validate()` NGAY — khong de online gap loi hop dong."""
    d = Path(root) / version
    meta_path, tier2_path = d / META_FILE, d / TIER2_FILE
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Khong thay {meta_path}. Publish bang scripts/publish_params.py truoc.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    tier2: list[Tier2Params] = []
    if tier2_path.exists():
        df = pd.read_csv(tier2_path)
        names = {f.name for f in fields(Tier2Params)}
        for _, r in df.iterrows():
            kw = {k: (None if pd.isna(v) else v) for k, v in r.items() if k in names}
            tier2.append(Tier2Params(
                **{**kw,
                   "horizon": int(kw["horizon"]), "nobs": int(kw["nobs"]),
                   "converged": bool(kw["converged"])}))

    art = ParamsArtifact(
        version=meta["version"],
        data_version=meta["data_version"],
        git_commit=meta["git_commit"],
        fitted_at=dt.datetime.fromisoformat(meta["fitted_at"]),
        sample_start=dt.date.fromisoformat(meta["sample_start"]),
        sample_end=dt.date.fromisoformat(meta["sample_end"]),
        tier2=tier2,
        tier3={k: Tier3Params(**v) for k, v in meta.get("tier3", {}).items()},
        percentiles=meta.get("percentiles", {}),
        claim_ceiling=meta.get("claim_ceiling", {}),
        notes=meta.get("notes", {}),
    )
    return art.validate()


def _tier2_frame(cells: list[Tier2Params]) -> pd.DataFrame:
    cols = [f.name for f in fields(Tier2Params)]
    if not cells:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([{c: getattr(p, c) for c in cols} for p in cells])


def _opt_float(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _opt_str(v) -> str | None:
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


__all__ = [
    "ArtifactValidationError",
    "git_commit",
    "load_artifact",
    "save_artifact",
    "tier2_from_estimate",
]
