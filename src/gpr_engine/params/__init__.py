"""params/ — ARTIFACT tham so, cau noi offline (research) <-> online (serving).

Quyet dinh kien truc goc, `docs/18_build_spec.md` §1:

    San pham KHONG chay hoi quy luc nhan request. No nap mot artifact tham so
    da fit, co version.

Vi sao can (khong phai rui ro gia dinh — hai khop noi long CO THAT trong repo):

1. `pipeline/gamma_lookup.py::load_published_gamma()` doc FILE MOI NHAT khop
   glob trong `docs/reports/data/t2_full_holm_*.csv`. Hai nhan dinh sinh cach
   nhau mot tuan KHONG truy duoc ve cung mot bo tham so neu ai do chay lai
   `run_t2_full.py` o giua. `version` immutable xoa han lop loi nay.
2. Cung ham do, voi `panel=None` (mac dinh cua pipeline theo tung tin, vi
   `build_monthly_panel` keo FRED — qua nang cho mot request) tra
   `standardized = beta`, tuc KHONG chuan hoa. Nhung
   `DEC-2026-08-03-dual-component` BAT BUOC bao cao chuan hoa. Artifact mang
   san `sd_regressor`/`beta_standardized` nen online noi dung ma khong phai
   dung lai panel.

Rang buoc: online KHONG BAO GIO fit gi. Neu online can mot so khong co trong
artifact -> do la bug thiet ke, khong phai ly do goi `.fit()`.
"""
from .artifact import load_artifact, save_artifact
from .schema import ARTIFACT_CLAIM_TIERS, ParamsArtifact, Tier2Params, Tier3Params

__all__ = [
    "ARTIFACT_CLAIM_TIERS",
    "ParamsArtifact",
    "Tier2Params",
    "Tier3Params",
    "load_artifact",
    "save_artifact",
]
