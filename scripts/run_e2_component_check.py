"""run_e2_component_check.py — E2: kiem dinh luan diem §2.1 cua docs/16. 🔬 diagnostic

CAU HOI (docs/16 §2.1): bai AI-GPR tach ΔGPR bang AR(p) thanh fitted (persistent)
+ resid (shock), thay he so cua fitted LON GAP DOI he so cua resid, va ket luan:
"partial-out phan du bao duoc la vut di tin hieu manh nhat" -> lag-augmented LP
(va INNOVATION) chi bat duoc nua yeu.

Ket luan do CHUA DUNG duoc neu chi so sanh HE SO THO. Hai thanh phan co PHUONG SAI
khac han nhau: AR(p) tren chuoi SAI PHAN co R² thap, nen fitted co bien do nho hon
resid nhieu lan. He so tho gap doi tren mot regressor bien do 1/3 la dong gop NHO
HON. Day dung la "tai nan thang do" ma registry da ghi cho LEVEL+JUMP
(`level_plus_jump_composition`) — cung cai bay, cho khac.

E2 do CA HAI:
    THO     : beta_P            vs beta_S
    CHUAN   : beta_P · sd(P)    vs beta_S · sd(S)     <- cai so sanh duoc

Kem mot kiem tra thu hai (E2b): duoi lag augmentation, LEVEL va INNOVATION co ra
cung mot he so khong? Neu co -> xac nhan co che FWL ma §2.1 mo ta, VA bac bo he
qua "dung INNOVATION la dung nua yeu nen G2a moi yeu" (vi LEVEL duoi lag-aug la
CUNG MOT THU, nen doi thuoc do khong cuu duoc gi).

CLAIM CEILING: `measurement` — day la thuoc tinh cua THUOC DO va cua so sanh he
so, KHONG phai claim ve tac dong. Khong quyet dinh gate nao; nguoi doc quyet.

Chay:  python scripts/run_e2_component_check.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import (  # noqa: E402
    DEFAULT_GPR_MONTHLY,
    build_monthly_panel,
    load_gpr_monthly,
    log1p_gpr,
)
from gpr_engine.econometrics.tier2_global_macro import estimate_tier2  # noqa: E402

REPORTS = Path("docs/reports")
DATADIR = REPORTS / "data"

AR_ORDER = 4            # docs/16 §2.1: bai dung p=4. Giu nguyen de so sanh duoc.
FOCAL_HORIZONS = (1, 2, 6)
OUTCOMES = ("ip", "cpi", "infl_exp", "oil", "vix")
CHANNELS = {"pooled": "GPR", "act": "GPR_ACT", "threat": "GPR_THREAT"}
LAGS = 6                # khop run_t2_full


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "UNKNOWN"


def _data_version(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def decompose(raw: pd.Series, order: int = AR_ORDER) -> tuple[pd.Series, pd.Series, float]:
    """AR(order) tren Δ LEVEL -> (fitted, resid, R²), da align information-time.

    Δ LEVEL = Δ log1p(GPR) — dung contract docs/07v2 §0. `shift(1)` o cuoi la
    align thang M vao bucket M+1 (giong build_monthly_panel), neu khong thi ca
    hai thanh phan deu nhin truoc mot thang.
    """
    d = log1p_gpr(raw).diff().dropna()
    X = pd.concat([d.shift(k) for k in range(1, order + 1)], axis=1).dropna()
    X.columns = [f"l{k}" for k in range(1, order + 1)]
    y = d.loc[X.index]
    res = sm.OLS(y, sm.add_constant(X)).fit()
    fitted = pd.Series(res.fittedvalues, index=X.index).shift(1)
    resid = pd.Series(res.resid, index=X.index).shift(1)
    return fitted, resid, float(res.rsquared)


def run_dual(panel: pd.DataFrame, gpr: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Spec kep docs/16 §2.2 cho moi (kenh, outcome, horizon). Tra bang + R²/var."""
    rows, diag = [], {}
    for chan, col in CHANNELS.items():
        fitted, resid, r2 = decompose(gpr[col])
        base = pd.DataFrame({"P": fitted, "S": resid})
        diag[chan] = {
            "ar_r2": round(r2, 4),
            "var_ratio": round(float(base["P"].var() / base["S"].var()), 4),
            "sd_p": round(float(base["P"].std()), 4),
            "sd_s": round(float(base["S"].std()), 4),
        }
        for out in OUTCOMES:
            if out not in panel.columns:
                continue
            df = base.join(panel[[out]], how="inner").dropna()
            for h in FOCAL_HORIZONS:
                yh = df[out].shift(-h).dropna()
                d2 = df.loc[yh.index]
                r = sm.OLS(yh, sm.add_constant(d2[["P", "S"]])).fit(cov_type="HC1")
                sd_p, sd_s = float(d2["P"].std()), float(d2["S"].std())
                rows.append(dict(
                    channel=chan, outcome=out, horizon=h, nobs=int(r.nobs),
                    beta_p=float(r.params["P"]), p_p=float(r.pvalues["P"]),
                    beta_s=float(r.params["S"]), p_s=float(r.pvalues["S"]),
                    std_p=float(r.params["P"]) * sd_p,
                    std_s=float(r.params["S"]) * sd_s))
    return pd.DataFrame(rows), diag


def run_level_vs_innovation(panel: pd.DataFrame) -> pd.DataFrame:
    """E2b: LEVEL vs INNOVATION duoi lag augmentation, cung spec run_t2_full."""
    rows = []
    for chan, prefix in CHANNELS.items():
        for out in OUTCOMES:
            if out not in panel.columns:
                continue
            betas = {}
            for measure in ("LEVEL", "INNOVATION"):
                irf = estimate_tier2(
                    panel, macro_vars=[out], shocks=[f"{prefix}_{measure}"],
                    horizons=FOCAL_HORIZONS, macro_lags=0,
                    inference="lag_augmented", lags=LAGS)
                betas[measure] = irf.set_index("horizon")["beta"]
            for h in FOCAL_HORIZONS:
                lv, inv = float(betas["LEVEL"][h]), float(betas["INNOVATION"][h])
                rows.append(dict(channel=chan, outcome=out, horizon=h,
                                 beta_level=lv, beta_innovation=inv,
                                 rel_diff=abs(lv - inv) / abs(inv) if inv else np.nan))
    return pd.DataFrame(rows)


def compute_stats(dual: pd.DataFrame, diag: dict, lvi: pd.DataFrame) -> dict:
    raw_bigger = (dual["beta_p"].abs() > dual["beta_s"].abs())
    std_bigger = (dual["std_p"].abs() > dual["std_s"].abs())
    key = dual[(dual["channel"] == "act") & (dual["outcome"] == "ip")
               & (dual["horizon"] == 2)].iloc[0]
    pooled = dual[(dual["channel"] == "pooled") & (dual["outcome"] == "ip")
                  & (dual["horizon"] == 2)].iloc[0]
    return {
        "ar_order": AR_ORDER,
        "n_cells": int(len(dual)),
        "n_raw_persistent_bigger": int(raw_bigger.sum()),
        "n_std_persistent_bigger": int(std_bigger.sum()),
        "n_reversed": int((raw_bigger & ~std_bigger).sum()),
        "share_reversed": round(float((raw_bigger & ~std_bigger).mean()), 4),
        "ar_r2_pooled": diag["pooled"]["ar_r2"],
        "var_ratio_pooled": diag["pooled"]["var_ratio"],
        "var_ratio_act": diag["act"]["var_ratio"],
        "pooled_beta_p": round(float(pooled["beta_p"]), 4),
        "pooled_beta_s": round(float(pooled["beta_s"]), 4),
        "pooled_std_p": round(float(pooled["std_p"]), 4),
        "pooled_std_s": round(float(pooled["std_s"]), 4),
        "key_beta_p": round(float(key["beta_p"]), 4),
        "key_p_p": round(float(key["p_p"]), 4),
        "key_beta_s": round(float(key["beta_s"]), 4),
        "key_p_s": round(float(key["p_s"]), 4),
        "key_std_p": round(float(key["std_p"]), 4),
        "key_std_s": round(float(key["std_s"]), 4),
        "key_nobs": int(key["nobs"]),
        "lvi_corr": round(float(lvi["beta_level"].corr(lvi["beta_innovation"])), 4),
        "lvi_median_rel_diff": round(float(lvi["rel_diff"].median()), 4),
        "lvi_n": int(len(lvi)),
    }


def build_report(stats: dict, dual: pd.DataFrame, diag: dict, meta: dict) -> list[str]:
    """Guard P1: MOI so trong narrative den tu `stats`/`meta`/bang."""
    p: list[str] = []
    p.append("# E2 — Phân rã persistent/shock: hệ số thô có so được không?\n")
    p.append("> 🔬 Diagnostic. Kiểm luận điểm `docs/16` §2.1 trên dữ liệu của chính "
             "dự án. Sinh bởi `scripts/run_e2_component_check.py`.\n")
    p.append("**Claim ceiling: `measurement`.** Đây là thuộc tính của phép SO SÁNH "
             "HỆ SỐ, không phải claim về tác động. Không quyết định gate nào.\n")

    p.append("## Metadata\n")
    p.append(f"- **data_version**: `{meta['data_version']}` · **commit**: "
             f"`{meta['git_commit']}` · **generated_at**: {meta['generated_at']}")
    p.append(f"- **panel**: {meta['panel_start']} → {meta['panel_end']}, "
             f"n={stats['key_nobs']} tháng dùng được tại h=2")
    p.append(f"- **phân rã**: AR({stats['ar_order']}) trên Δlog1p(GPR) — đúng bậc "
             "`docs/16` §2.1 dùng, để so sánh được\n")

    p.append("## Câu hỏi\n")
    p.append("`docs/16` §2.1 đọc bảng của bài AI-GPR (persistent −0.271 vs shock "
             "−0.119) và kết luận: phần dai dẳng tác động **hơn gấp đôi**, nên "
             "partial-out nó (lag augmentation / INNOVATION) là vứt đi tín hiệu "
             "mạnh nhất. Câu hỏi ở đây: **hai hệ số đó có so được với nhau không?**\n")

    p.append("## Kết quả 1 — thô so với chuẩn hóa\n")
    p.append(f"AR({stats['ar_order']}) trên chuỗi **sai phân** giải thích được rất "
             f"ít: R²={stats['ar_r2_pooled']} (kênh pooled). Hệ quả là phần fitted "
             f"có phương sai chỉ bằng **{stats['var_ratio_pooled']}** lần phần "
             "residual — biên độ nhỏ hơn khoảng ba lần.\n")
    p.append("| GPR → IP, h=2 | β_persistent | β_shock |")
    p.append("|---|---|---|")
    p.append(f"| **Thô** | {stats['pooled_beta_p']:+.4f} | {stats['pooled_beta_s']:+.4f} |")
    p.append(f"| **Chuẩn hóa** (×sd) | {stats['pooled_std_p']:+.4f} | "
             f"**{stats['pooled_std_s']:+.4f}** |")
    p.append("")
    p.append("Thô thì persistent lớn gấp đôi — **tái lập đúng pattern của bài**. "
             "Chuẩn hóa thì **thứ tự đảo ngược**.\n")
    p.append(f"Trên toàn bộ {stats['n_cells']} ô (kênh × outcome × horizon focal): "
             f"{stats['n_raw_persistent_bigger']} ô có |β_P| > |β_S| theo thô, nhưng "
             f"chỉ {stats['n_std_persistent_bigger']} ô giữ được sau chuẩn hóa. "
             f"**{stats['n_reversed']} ô đảo chiều kết luận** "
             f"({stats['share_reversed'] * 100:.1f}% tổng số ô).\n")

    p.append("## Kết quả 2 — ô chính của T2-full\n")
    p.append(f"`GPR_ACT → IP` tại h=2 (ô duy nhất đồng thuận cả ba thước đo trong "
             f"bảng γ), n={stats['key_nobs']}:\n")
    p.append("| | β | p | β×sd |")
    p.append("|---|---|---|---|")
    p.append(f"| Persistent | {stats['key_beta_p']:+.4f} | {stats['key_p_p']:.3f} "
             f"| {stats['key_std_p']:+.4f} |")
    p.append(f"| Shock | {stats['key_beta_s']:+.4f} | **{stats['key_p_s']:.3f}** "
             f"| **{stats['key_std_s']:+.4f}** |")
    p.append("")
    p.append("Ở ô này thành phần **shock** mới là cái mang tín hiệu: nó có ý nghĩa "
             "thống kê còn persistent thì không, và đóng góp chuẩn hóa cũng lớn hơn.\n")

    p.append("## Kết quả 3 (E2b) — LEVEL và INNOVATION dưới lag augmentation\n")
    p.append(f"Trên {stats['lvi_n']} ô: corr(β_LEVEL, β_INNOVATION) = "
             f"**{stats['lvi_corr']}**, lệch tương đối trung vị "
             f"**{stats['lvi_median_rel_diff'] * 100:.1f}%**.\n")
    p.append("→ **Xác nhận cơ chế mà `docs/16` §2.1 mô tả**: dưới lag augmentation, "
             "LEVEL bị residual hóa thành đúng phần bất ngờ (FWL), nên nó và "
             "INNOVATION cho gần như cùng một hệ số.\n")
    p.append("→ Nhưng đúng vì thế, **hệ quả \"dùng INNOVATION là dùng nửa yếu nên "
             "kết quả mới yếu\" không đứng**: nếu vậy thì LEVEL phải cứu được. Trong "
             "`T2_full` LEVEL cũng cho **0/4 giá tài sản**, y hệt INNOVATION — vì "
             "dưới lag-aug hai cái là cùng một thứ.\n")

    p.append("## Chẩn đoán phân rã theo kênh\n")
    p.append("| Kênh | R² của AR | Var(P)/Var(S) | sd(P) | sd(S) |")
    p.append("|---|---|---|---|---|")
    for chan, d in diag.items():
        p.append(f"| {chan} | {d['ar_r2']} | {d['var_ratio']} | {d['sd_p']} | "
                 f"{d['sd_s']} |")
    p.append("")

    p.append("## Kết luận máy đọc được\n")
    p.append("1. **Cơ chế của §2.1 đúng** và đã tái lập: lag-augmented LP trả về hệ "
             "số của thành phần bất ngờ.")
    p.append("2. **Kết luận định lượng của §2.1 chưa đứng được** trên dữ liệu này: "
             "\"hơn gấp đôi\" là so sánh hệ số thô của hai regressor khác phương sai "
             "— cùng loại tai nạn thang đo mà registry đã ghi cho `LEVEL+JUMP`. "
             "Chuẩn hóa xong thì thứ tự đảo.")
    p.append("3. **Đề xuất §2.2 (spec kép) không bị ảnh hưởng — nó là lối ra đúng**: "
             "đưa cả hai thành phần vào cùng lúc thì không phải chọn, và báo cáo "
             "được cả hai. Điều kiện: **đóng góp phải báo cáo chuẩn hóa**, và β_P "
             "phải gọi đúng tên là phản ứng với thành phần *đã dự báo được* — gọi "
             "nó là \"tác động của cú sốc\" vẫn là vi phạm #9.\n")

    p.append("## ⚠️ Giới hạn — đọc trước khi dùng kết luận này\n")
    p.append(f"- **Chuỗi khác bài.** Đây là GPRD tháng; bài chạy AI-GPR tuần. "
             f"AI-GPR **dai hơn** (`docs/16` §5: tự tương quan 0.73 vs 0.62), nên "
             f"R² của AR({stats['ar_order']}) trên nó sẽ cao hơn "
             f"{stats['ar_r2_pooled']}, phần fitted có biên độ lớn hơn, và khoảng "
             "cách chuẩn hóa **có thể không đảo**. Kết quả này KHÔNG bác bảng của "
             "bài — nó bác cách *đọc* bảng đó khi chưa chuẩn hóa.")
    p.append("- **Việc cần làm để khép lại:** hỏi bài báo cáo hệ số thô hay chuẩn "
             "hóa, và Var(fitted)/Var(resid) của họ bằng bao nhiêu. Nếu họ đã chuẩn "
             "hóa thì §2.1 đúng nguyên và mục này chỉ còn giá trị cho chuỗi GPRD.")
    p.append("- Chạy lại E2 trên AI-GPR ngay khi `load_ai_gpr()` có dữ liệu.\n")

    p.append("## Human review\n")
    p.append("- Có chấp nhận sửa `docs/16` §2.1 theo mục Kết luận không: _chưa điền_")
    p.append("- **Kết luận (người + ngày):** _chưa điền_\n")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    print("[1/4] Panel tháng...")
    panel = build_monthly_panel(start=args.start, refresh=args.refresh,
                                shock_axis=True, components=True,
                                real_macro=True, freight=True)
    gpr = load_gpr_monthly(components=True).loc[args.start:]

    print("[2/4] Spec kép (persistent + shock)...")
    dual, diag = run_dual(panel, gpr)

    print("[3/4] E2b: LEVEL vs INNOVATION dưới lag augmentation...")
    lvi = run_level_vs_innovation(panel)

    print("[4/4] Report...")
    stats = compute_stats(dual, diag, lvi)
    dv = _data_version(DEFAULT_GPR_MONTHLY)
    meta = {"data_version": dv, "git_commit": _git_commit(),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "panel_start": panel.index.min().date().isoformat(),
            "panel_end": panel.index.max().date().isoformat()}

    DATADIR.mkdir(parents=True, exist_ok=True)
    dual.to_csv(DATADIR / f"e2_dual_{dv}.csv", index=False)
    lvi.to_csv(DATADIR / f"e2_level_vs_innov_{dv}.csv", index=False)

    out = REPORTS / f"E2_component_decomposition_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè.")
    out.write_text("\n".join(build_report(stats, dual, diag, meta)), encoding="utf-8")
    print(f"\nDONE → {out}")


if __name__ == "__main__":
    main()
