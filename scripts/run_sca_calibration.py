"""run_sca_calibration.py — hiệu chỉnh ℓ (block length) động cơ SCA trên mô phỏng. 🔬

docs/12 §3.2 chốt ℓ=12 (tháng) / 60 (ngày) bằng PHÁN ĐOÁN. docs/13 §5: moving-block
trên chuỗi dai dẳng RẤT DỄ SAI SIZE, và chỉ có 1 lần chạy trung thực trên dữ liệu
thật. Hiệu chỉnh ℓ trên dữ liệu MÔ PHỎNG là HỢP LỆ (không đụng dữ liệu thật, không
phải dò).

Cách: sinh nhiều mẫu với hiệu ứng THẬT = 0 nhưng shock+outcome đều dai dẳng (AR(1)
với ρ khớp GPR/macro thật). Với mỗi ℓ, đo tỉ lệ bác bỏ (SIZE) — phải ≈ danh nghĩa
5%. ℓ quá nhỏ → phá autocorr → size phình; ℓ quá lớn → ít block → CI rộng/size lệch.
Chọn ℓ giữ size gần 5% nhất. Cũng đo POWER (hiệu ứng≠0) để ℓ chọn không giết power.

Report versioned, KHÔNG ghi đè.

Chạy:  .venv/bin/python scripts/run_sca_calibration.py [--quick]
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.sca_engine import run_sca  # noqa: E402

REPORTS = Path("docs/reports")
# ℓ ứng viên cho mỗi track. Bao quanh giá trị chốt (12 tháng, 60 ngày) để thấy nó
# có phải lựa chọn giữ size tốt không.
GRID = {
    # locked = ℓ đã hiệu chỉnh 2026-07-19 (registry block_length_*). Giữ giá trị cũ
    # 12/60 trong blocks để report vẫn đối chứng được size ở giá trị phán đoán ban đầu.
    "monthly": {"n": 378, "rho": 0.85, "blocks": [3, 6, 12, 18, 24], "locked": 18},
    "daily":   {"n": 2000, "rho": 0.95, "blocks": [20, 40, 60, 90, 120], "locked": 40},
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def _ar1(n: int, rho: float, rng: np.random.Generator) -> np.ndarray:
    x = np.zeros(n)
    e = rng.standard_normal(n)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + e[i]
    return x


def _ols_spec(data: pd.DataFrame, idx: np.ndarray):
    d = data.iloc[idx]
    X = sm.add_constant(d[["x"]].values)
    res = sm.OLS(d["y"].values, X).fit()
    return float(res.params[1]), float(res.pvalues[1])


def rejection_rate(n: int, rho: float, block_len: int, effect: float,
                   n_trials: int, B: int, seed: int) -> float:
    """Tỉ lệ bác bỏ (pvalue_stouffer<0.05) qua n_trials mẫu độc lập."""
    rng = np.random.default_rng(seed)
    rej = 0
    for t in range(n_trials):
        x = _ar1(n, rho, rng)
        y = effect * x + _ar1(n, rho, rng)         # outcome cũng dai dẳng
        data = pd.DataFrame({"x": x, "y": y})
        res = run_sca([_ols_spec], data, B=B, block_len=block_len,
                      rng=np.random.default_rng(seed + 10_000 + t),
                      expected_sign=None)
        if res["pvalue_stouffer"] < 0.05:
            rej += 1
    return rej / n_trials


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="ít trial/B cho smoke")
    args = ap.parse_args()
    n_trials = 20 if args.quick else 60
    B = 150 if args.quick else 400

    results: dict[str, dict] = {}
    for track, cfg in GRID.items():
        results[track] = {"size": {}, "power": {}}
        for bl in cfg["blocks"]:
            size = rejection_rate(cfg["n"], cfg["rho"], bl, effect=0.0,
                                  n_trials=n_trials, B=B, seed=1)
            power = rejection_rate(cfg["n"], cfg["rho"], bl, effect=0.3,
                                   n_trials=n_trials, B=B, seed=2)
            results[track]["size"][bl] = round(size, 3)
            results[track]["power"][bl] = round(power, 3)

    # chọn ℓ: size gần 0.05 nhất (ưu tiên không vượt), trong các ℓ đó lấy power cao
    picks = {}
    for track, cfg in GRID.items():
        size = results[track]["size"]
        best = min(size, key=lambda bl: (abs(size[bl] - 0.05), -results[track]["power"][bl]))
        picks[track] = best

    commit = _git_commit()
    now = dt.datetime.now().isoformat(timespec="seconds")
    parts = [
        "# SCA calibration — hiệu chỉnh ℓ (block length) trên mô phỏng\n",
        "> 🔬 Diagnostic (docs/12 §3.2, docs/13 §5). Hiệu chỉnh ℓ trên dữ liệu MÔ "
        "PHỎNG — hợp lệ vì không đụng dữ liệu thật. Sinh bởi "
        "`scripts/run_sca_calibration.py`.\n",
        "## Metadata\n",
        f"- **git commit**: `{commit}` · **generated_at**: {now}",
        f"- **n_trials**: {n_trials} · **B**: {B} · quick={args.quick}\n",
        "## Câu hỏi\n",
        "ℓ chốt trong docs/12 (12 tháng / 60 ngày) là PHÁN ĐOÁN. Với hiệu ứng thật=0 "
        "trên chuỗi dai dẳng, tỉ lệ bác bỏ (SIZE) có ≈ 5% không? ℓ quá nhỏ phá "
        "autocorr → size phình; quá lớn → ít block. Chọn ℓ giữ size gần danh nghĩa.\n",
    ]
    for track, cfg in GRID.items():
        parts += [
            f"## Track {track} (n={cfg['n']}, ρ={cfg['rho']}, ℓ chốt docs/12 = {cfg['locked']})\n",
            "| ℓ (block) | SIZE (effect=0, mong ~0.05) | POWER (effect=0.3) |",
            "|---|---|---|",
        ]
        for bl in cfg["blocks"]:
            mark = " ← docs/12" if bl == cfg["locked"] else ""
            pick = " **← chọn**" if bl == picks[track] else ""
            parts.append(f"| {bl}{mark}{pick} | {results[track]['size'][bl]} | "
                         f"{results[track]['power'][bl]} |")
        parts.append("")
        locked_size = results[track]["size"][cfg["locked"]]
        parts.append(
            f"- ℓ={cfg['locked']} (docs/12) cho size = **{locked_size}**. "
            f"ℓ giữ size gần 0.05 nhất = **{picks[track]}**." +
            (" Khớp docs/12." if picks[track] == cfg["locked"]
             else f" ⚠️ KHÁC docs/12 ({cfg['locked']}) — cân nhắc cập nhật ℓ.") + "\n")

    parts += [
        "## Kết luận\n",
        f"- ℓ hiệu chỉnh (giữ size gần danh nghĩa): tháng **{picks['monthly']}**, "
        f"ngày **{picks['daily']}**.",
        "- Đây là hiệu chỉnh HỢP LỆ (mô phỏng, không đụng dữ liệu thật, docs/13 §5). "
        "Nếu khác giá trị chốt docs/12 → cập nhật registry `block_length_*` + ghi lý do.",
        "- ⚠️ Mô phỏng dùng AR(1) đơn giản; chuỗi thật có thể có đuôi/regime phức tạp "
        "hơn. Coi đây là cận dưới độ tin cậy, không phải bảo chứng tuyệt đối.\n",
    ]

    REPORTS.mkdir(parents=True, exist_ok=True)
    tag = "quick" if args.quick else commit
    out = REPORTS / f"SCA_calibration_{tag}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    print(f"  ℓ chọn: monthly={picks['monthly']} (docs/12={GRID['monthly']['locked']}), "
          f"daily={picks['daily']} (docs/12={GRID['daily']['locked']})")
    for track in GRID:
        print(f"  {track} size: {results[track]['size']}")


if __name__ == "__main__":
    main()
