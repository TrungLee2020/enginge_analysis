"""gamma_lookup.py — doc bang gamma TANG 2 (da cong bo) loc theo mot tin don le.

🏭 production-path. Tong quat hoa `load_gamma_cells` dang nam rieng trong
`scripts/run_brief_demo.py` (khong sua script do — no van la demo doc lap) de
`pipeline/news_pipeline.py` dung lai duoc cho tung tin mot, khong phai chi cho
lan chay batch toan lich su.

⚠️ GIOI HAN THAT (ghi ro, khong che): bang gamma hien co
(`docs/reports/data/t2_full_holm_*.csv`) tach theo `channel ∈ {pooled, act,
threat}` — day la BA BIEN THE GPRD dung lam shock (GPRD gop / GPRD_ACT /
GPRD_THREAT), KHONG PHAI 4 kenh truyen dan energy/trade/financial/military ma
`transmission-formulas.md` mo ta. Hoi quy tach theo kenh truyen dan (nhu
`tier2_global_macro.py` docstring dang noi "chay rieng shock kenh energy vs
trade") CHUA duoc uoc luong. `commitment_to_gamma_channel` la MOT PROXY co chu
dich (khong phai cung mot truc du lieu) — announced_action doc gan voi GPRD_ACT
(hanh dong da xay ra), rhetoric/conditional doc gan voi GPRD_THREAT (de doa
chua thanh hien thuc); xem transmission-formulas.md §1 "Threat tac dong qua
thanh phan dai dang; Act chi tac dong khi bat ngo".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..scoring.statement_scorer import COMMITMENTS
from ..reporting.composer import GammaCell

DEFAULT_REPORTS_DIR = Path("docs/reports")
DEFAULT_GAMMA_GLOB = "data/t2_full_holm_*.csv"
GAMMA_CHANNELS = ("pooled", "act", "threat")

_COMMITMENT_TO_CHANNEL = {
    "announced_action": "act",
    "conditional": "threat",
    "rhetoric": "threat",
}


def commitment_to_gamma_channel(commitment: str) -> str:
    """Proxy: commitment cua MOT tin -> channel cua bang gamma (pooled/act/threat).

    KHONG doan gia tri la ngoai COMMITMENTS — raise, giong quy uoc "sai la
    raise, khong sua ho" cua `statement_scorer.parse_score`.
    """
    if commitment not in COMMITMENTS:
        raise ValueError(f"commitment={commitment!r} không thuộc {COMMITMENTS}")
    return _COMMITMENT_TO_CHANNEL[commitment]


def _latest_gamma_file(reports_dir: Path, glob_pattern: str) -> Path:
    files = list(reports_dir.glob(glob_pattern))
    if not files:
        raise FileNotFoundError(
            f"Không thấy {glob_pattern} trong {reports_dir}. Chạy "
            "`python scripts/run_t2_full.py` trước — pipeline đọc từ bảng γ đã "
            "công bố, không tự ước lượng lại (docs/14 §8).")
    # Bug đã vá (audit production-readiness 2026-08-05): tên file là
    # `t2_full_holm_<content-hash>.csv` (docs/g0 quy ước versioned report,
    # không GHI ĐÈ mỗi lần chạy lại `run_t2_full.py`) — hash KHÔNG mang thứ
    # tự thời gian. `sorted(files)[-1]` cũ sắp xếp theo CHUỖI TÊN FILE (tức
    # theo hash), không phải theo thời điểm tạo — khi có ≥2 file khớp
    # glob_pattern, "file cuối cùng theo alphabet" có thể là file CŨ HƠN,
    # chọn sai γ mà không có dấu hiệu nào (không raise, không log). Rủi ro
    # thật khi `run_t2_full.py` được chạy lại nhiều lần theo thời gian (đúng
    # kịch bản dữ liệu GPR mới về định kỳ) — sắp theo `st_mtime` (thời điểm
    # sửa file gần nhất) mới đúng nghĩa "mới nhất".
    return max(files, key=lambda p: p.stat().st_mtime)


def load_published_gamma(
    channel: str,
    outcomes: set[str] | None = None,
    reports_dir: Path | str = DEFAULT_REPORTS_DIR,
    glob_pattern: str = DEFAULT_GAMMA_GLOB,
    panel: pd.DataFrame | None = None,
) -> tuple[list[GammaCell], str]:
    """O gamma DA SONG SOT (Holm + battery b) cho MOT channel cua bang gamma.

    channel: 'pooled'|'act'|'threat' — dung `commitment_to_gamma_channel` de
        suy tu commitment cua tin, hoac 'pooled' neu muon lay khong phan biet.
    outcomes: loc theo ten outcome (vd {'oil','dxy','vix','us10y'} cho macro
        tuc thoi, hoac None de lay het 8 outcome co trong bang).
    panel: neu co (DataFrame tu `data_files.build_monthly_panel`), tinh
        `standardized` = beta * sd(shock) dung cong thuc cua
        `run_brief_demo.load_gamma_cells`. KHONG co san trong pipeline theo
        tung tin (build_monthly_panel keo FRED, qua nang cho 1 request) —
        mac dinh None thi `standardized = beta` (KHONG chuan hoa, ghi ro trong
        docstring nay chu khong bia so). Day la gioi han co chu dich cua V1,
        khong phai loi — xem "Ngoai pham vi V1" trong ke hoach da duyet.

    Returns: (danh sach GammaCell, ten file da doc — vao meta.data_version).
    """
    if channel not in GAMMA_CHANNELS:
        raise ValueError(f"channel={channel!r} không thuộc {GAMMA_CHANNELS}")

    path = _latest_gamma_file(Path(reports_dir), glob_pattern)
    df = pd.read_csv(path)
    sub = df[(df["reject"]) & (df["battery"] == "b") & (df["channel"] == channel)]
    if outcomes:
        sub = sub[sub["outcome"].isin(outcomes)]

    prefix = {"pooled": "GPR", "act": "GPR_ACT", "threat": "GPR_THREAT"}
    cells = []
    for _, r in sub.iterrows():
        if panel is not None and "beta_std" in sub.columns and pd.notna(r.get("beta_std")):
            std = float(r["beta_std"])
        elif panel is not None:
            col = f"{prefix[r['channel']]}_{r['measure']}"
            std = float(r["beta"]) * float(panel[col].std())
        else:
            std = float(r["beta"])  # KHONG chuan hoa — xem docstring o tren.
        cells.append(GammaCell(
            outcome=f"{r['outcome']} ({r['measure']}·{r['channel']})",
            horizon=int(r["horizon"]), beta=float(r["beta"]),
            pvalue=float(r["pvalue"]), standardized=std,
            survived_holm=True, survived_battery=True))
    return cells, path.name
