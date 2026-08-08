"""run_e4_aigpr_unique.py — E4: AI-GPR cung cap gi mà GPRD KHÔNG có, và dùng ở đâu?

🔬 RESEARCH (CLAUDE.md #1) — không đổi đường production. Report versioned vào
docs/reports/, không ghi đè.

BOI CANH: E3 kết luận không nên thay GPRD bằng AI-GPR cho JUMP (cùng tần suất
nhưng khác ngày, Jaccard thấp). User chỉ ra AI-GPR là dữ liệu kèm PAPER nên cập
nhật theo nhịp nghiên cứu (chậm hơn GPRD gốc), và muốn "tận dụng tối đa".

CÂU HỎI: nếu không dùng cho JUMP thì AI-GPR đáng dùng vào đâu? Giả thuyết kiểm
ở đây: **tách theo TỐC ĐỘ BIẾN ĐỔI của đại lượng, không theo nguồn**.
  - Đại lượng biến động NHANH (trigger/JUMP) -> cần dữ liệu TƯƠI -> GPRD.
  - Đại lượng biến đổi CHẬM (cấu trúc: kênh nào đang nóng, phơi nhiễm) -> một
    bản chậm vài tuần vẫn còn nguyên giá trị -> AI-GPR, nơi nó độc quyền.
Nếu đúng, nhịp cập nhật chậm của AI-GPR KHÔNG phải nhược điểm cho nhóm thứ hai.

TRAN CLAIM: `measurement` — mô tả thuộc tính chuỗi (tính độc lập, độ dai). KHÔNG
hồi quy outcome, KHÔNG claim chuỗi nào dự báo tốt hơn.

Chạy: .venv/bin/python scripts/run_e4_aigpr_unique.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import (  # noqa: E402
    DEFAULT_AI_GPR_DAILY,
    DEFAULT_GPR_DAILY,
    load_ai_gpr_daily,
    load_gpr_daily,
)
from gpr_engine.econometrics.shocks import jump  # noqa: E402

REPORTS = Path("docs/reports")
SAMPLE_START = "2015"          # cua so Development+Validation cua du an
OIL_PREFIX = "AIGPR_OIL_"


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def main() -> None:
    a = load_ai_gpr_daily(DEFAULT_AI_GPR_DAILY)
    g = load_gpr_daily(DEFAULT_GPR_DAILY)
    sub = a.loc[SAMPLE_START:]
    regions = [c for c in a.columns if c.startswith(OIL_PREFIX)]

    # Tinh DOC LAP giua cac vung — neu chi la ban sao co ty le cua chuoi tong
    # thi tuong quan phai gan 1 va khong co gi de khai thac them.
    corr = sub[regions].corr()
    iu = np.triu_indices_from(corr, k=1)

    # Toc do bien doi: dai luong CAU TRUC (ty so cuong do nang luong) vs
    # dai luong TRIGGER (JUMP). So sanh tu tuong quan theo THANG.
    ratio_m = (sub["AIGPR_OIL"] / sub["AIGPR"]).resample("MS").mean()
    jump_m = jump(sub["AIGPR"], 250, 0.95).dropna().resample("MS").mean()

    s = {
        "start": sub.index.min().date().isoformat(),
        "end": sub.index.max().date().isoformat(),
        "n_regions": len(regions),
        "corr_mean": round(float(corr.values[iu].mean()), 3),
        "corr_min": round(float(corr.values[iu].min()), 3),
        "corr_max": round(float(corr.values[iu].max()), 3),
        "ratio_ac1": round(float(ratio_m.autocorr(1)), 3),
        "ratio_ac3": round(float(ratio_m.autocorr(3)), 3),
        "jump_ac1": round(float(jump_m.autocorr(1)), 3),
        "oil_gt_total_pct": round(float((sub["AIGPR_OIL"] > sub["AIGPR"]).mean()) * 100, 1),
        "corr_oil_total": round(float(sub["AIGPR_OIL"].corr(sub["AIGPR"])), 3),
        "corr_nonoil_total": round(float(sub["AIGPR_NONOIL"].corr(sub["AIGPR"])), 3),
        "gprd_cols": ", ".join(g.columns),
        "aigpr_n_cols": len(a.columns),
    }

    reg_rows = []
    for c in regions:
        r = (sub[c] / sub["AIGPR_OIL"]).resample("MS").mean()
        reg_rows.append((c.replace(OIL_PREFIX, ""), r.mean(), r.std(),
                         r.autocorr(1)))
    reg_rows.sort(key=lambda t: -t[1])
    reg_tbl = "\n".join(f"| {n} | {m:.3f} | {sd:.3f} | {ac:.3f} |"
                        for n, m, sd, ac in reg_rows)

    dv = f"{_sha(DEFAULT_AI_GPR_DAILY)[:6]}_{_sha(DEFAULT_GPR_DAILY)[:6]}"
    parts = [
        "# E4 — AI-GPR độc quyền có gì, và nhịp cập nhật chậm có sao không?\n",
        f"**Ngày chạy:** {dt.date.today().isoformat()} · **git:** `{_git_commit()}` · "
        f"**data_version:** `{dv}`",
        f"**Mẫu:** {s['start']} → {s['end']} · **Trần claim:** `measurement`\n",
        "## 0. Câu hỏi\n",
        "E3 kết luận **không** thay GPRD bằng AI-GPR cho JUMP. Vậy AI-GPR — dữ liệu "
        "kèm paper, cập nhật theo nhịp nghiên cứu nên chậm hơn GPRD gốc — nên dùng "
        "vào đâu để không lãng phí?\n",
        "**Giả thuyết kiểm ở đây:** phân công theo **TỐC ĐỘ BIẾN ĐỔI của đại lượng**, "
        "không theo nguồn. Đại lượng đổi nhanh cần dữ liệu tươi; đại lượng đổi chậm "
        "thì một bản chậm vài tuần vẫn còn nguyên giá trị.\n",
        "## 1. AI-GPR có gì mà GPRD hoàn toàn không có\n",
        f"GPRD daily chỉ có **3 cột**: `{s['gprd_cols']}` — không có bất kỳ phân rã "
        f"theo vùng/kênh nào. AI-GPR daily có **{s['aigpr_n_cols']} cột**, trong đó "
        f"**{s['n_regions']} chỉ số dầu theo vùng** (Middle East, Russia, USA, "
        "Venezuela, Africa, Americas, Asia, North Sea) — ở tần suất NGÀY.\n",
        "Đây là điểm quan trọng: với những chuỗi này **không tồn tại nguồn thay thế**. "
        "Câu hỏi 'GPRD hay AI-GPR' không áp dụng — GPRD đơn giản là không có.\n",
        "## 2. Các vùng có mang thông tin RIÊNG không, hay chỉ là bản sao có tỷ lệ?\n",
        "Nếu 8 vùng chỉ là chuỗi tổng nhân hệ số thì tương quan cặp phải gần 1 và "
        "chẳng khai thác thêm được gì. Đo trên mẫu:\n",
        f"- tương quan trung bình giữa các cặp vùng: **{s['corr_mean']}**",
        f"- thấp nhất {s['corr_min']}, cao nhất {s['corr_max']}\n",
        "→ Các vùng **gần như độc lập nhau**. Một cú sốc Trung Đông và một cú sốc Nga "
        "là hai tín hiệu khác nhau, không phải cùng một tín hiệu ở hai mức độ. Đây là "
        "thông tin thật, và hiện đang bị bỏ không hoàn toàn.\n",
        "## 3. ⚠️ Đính chính một cách đọc SAI (tôi mắc trong chính phiên này)\n",
        "`AIGPR_OIL` trông như 'phần năng lượng của AI-GPR' nhưng **KHÔNG PHẢI**:\n",
        f"- có **{s['oil_gt_total_pct']}%** số ngày `AIGPR_OIL` **lớn hơn** `AIGPR`",
        f"- `AIGPR_OIL + AIGPR_NONOIL` **không** cộng về `AIGPR`",
        f"- tương quan với chuỗi tổng: OIL {s['corr_oil_total']}, "
        f"NONOIL {s['corr_nonoil_total']}\n",
        "Mỗi chỉ số được **chuẩn hóa riêng** (mỗi cái ~100 ở kỳ gốc của nó), nên tỷ số "
        "giữa chúng **không phải tỷ trọng phần trăm**. Gọi `AIGPR_OIL/AIGPR` là 'tỷ "
        "trọng năng lượng' là sai — nó là **tỷ số cường độ tương đối** (năng lượng "
        "đang căng thế nào so với nền chung), không cộng về 100%. Cách đọc này phải "
        "ghi rõ ở mọi chỗ dùng, nếu không sẽ có người cộng các vùng lại rồi thắc mắc "
        "vì sao vượt 100%.\n",
        "## 4. Kết quả chính: đại lượng cấu trúc đổi CHẬM, trigger đổi NHANH\n",
        "Tự tương quan theo THÁNG (giá trị tháng này dự đoán được tháng sau bao nhiêu):\n",
        "| Đại lượng | Vai trò | Tự tương quan lag-1 tháng |",
        "|---|---|---|",
        f"| `AIGPR_OIL/AIGPR` (cường độ tương đối kênh năng lượng) | cấu trúc | "
        f"**{s['ratio_ac1']}** (lag-3: {s['ratio_ac3']}) |",
        f"| JUMP trên `AIGPR` | trigger | **{s['jump_ac1']}** |\n",
        "→ **Giả thuyết §0 được ủng hộ.** Đại lượng cấu trúc dai: giá trị tháng trước "
        "vẫn nói được nhiều về tháng này. Trigger thì gần như không tự tương quan — "
        "giá trị tháng trước gần như vô dụng cho tháng này, đúng bản chất 'cú sốc'.\n",
        "**Hệ quả trực tiếp cho câu hỏi nhịp cập nhật:** AI-GPR trễ vài tuần làm hỏng "
        "một trigger (thứ cần đúng NGÀY), nhưng gần như không làm suy giảm một đại "
        "lượng cấu trúc dai như trên. Nói cách khác **nhịp chậm của AI-GPR không phải "
        "nhược điểm cho đúng nhóm việc mà nó độc quyền.**\n",
        "## 5. Ổn định của từng vùng (tỷ số so với `AIGPR_OIL`)\n",
        "| Vùng | Trung bình | Độ lệch chuẩn | Tự tương quan lag-1 |",
        "|---|---|---|---|",
        reg_tbl + "\n",
        "Middle East và Russia chi phối, và là hai vùng dai nhất — hợp lý về cơ chế. "
        "Các vùng nhỏ (North Sea) tỷ số thấp và nhiễu; đừng đọc chúng như tín hiệu "
        "độc lập khi chưa kiểm.\n",
        "## 6. Khuyến nghị — phân công theo tốc độ, không theo nguồn\n",
        "| Việc | Nguồn | Lý do |",
        "|---|---|---|",
        "| JUMP / trigger S4 (chân A realtime) | **GPRD** | cần đúng ngày; E3 cho thấy "
        "hai chuỗi khác ngày nên không thay thế được nhau |",
        "| Cường độ kênh năng lượng | **AI-GPR** (`AIGPR_OIL`, 8 vùng) | GPRD không có; "
        "đại lượng dai nên trễ vài tuần không sao |",
        "| Phơi nhiễm VN theo cặp nước | **AI-GPR** bilateral (monthly) | GPRD/GPRC "
        "không có chiều song phương |",
        "| Vai trò VN (spillover/respondent) | **AI-GPR** country×role (monthly) | "
        "GPRC chỉ có mức nước, không tách vai |\n",
        "**Việc code đề xuất (CHƯA làm trong report này):** chuỗi 8 vùng oil đã nằm "
        "trong `ext_series` sau `ingest/ai_gpr.py` nhưng chưa có đường đọc ra. Bước "
        "nhỏ nhất có ích: hàm đọc cường độ kênh năng lượng tại `as_of` (point-in-time, "
        "cùng quy ước `available_at` với `load_jump_series`), để `transmission_channel"
        "='energy'` có số kèm theo thay vì chỉ là nhãn.\n",
        "## 7. Đối chiếu PHƯƠNG PHÁP trong paper — cái nào đã được tác giả kiểm, cái nào là rủi ro thật\n",
        "Đọc lại `AI_GPR_PAPER.pdf` sau khi user đặt vấn đề cẩn trọng. Kết quả: mấy "
        "nghi ngại hiển nhiên nhất **đã được chính tác giả đo**, không phải lỗ hổng bỏ ngỏ:\n",
        "| Nghi ngại | Tác giả xử lý thế nào | Còn là rủi ro? |",
        "|---|---|---|",
        "| Lọc từ khóa giai đoạn 1 bỏ sót bài (chỉ số không thật sự 'ngữ nghĩa') | Đo "
        "trực tiếp: chấm LLM trên mẫu ngẫu nhiên các bài KHÔNG khớp từ khóa — chỉ **0.9%** "
        "có điểm dương, và đều điểm thấp | Nhỏ, đã đo |",
        "| Cắt bài còn 2.000 ký tự làm sai điểm | Chấm lại toàn văn để đối chiếu: tương "
        "quan rất cao, thứ hạng gần như không đổi, toàn văn chỉ cao hơn chút | Nhỏ, đã đo |",
        "| Chia cho `A_t` (tổng số bài báo) | Có chủ đích, kế thừa Caldara-Iacoviello "
        "(2022) để khử biến động sản lượng báo | Là lựa chọn thiết kế, không phải lỗi |\n",
        "**Rủi ro THẬT còn lại, và nó ảnh hưởng trực tiếp tới cách ta dùng:**\n",
        "1. **Công thức (2) của Oil GPR KHÔNG có hằng số chuẩn hóa `S̄`** mà công thức "
        "(1) của AI-GPR tổng thì có. Đây chính là lý do gốc của §3: hai chỉ số nằm trên "
        "hai thang khác nhau, nên **mọi tỷ số giữa chúng không phải phần trăm**. Phát "
        "hiện thực nghiệm ở §3 và công thức trong paper xác nhận lẫn nhau.",
        "2. **Oil GPR có điều kiện lồng**: chỉ xét bài đã có điểm GPR > 0.5 *và* chứa từ "
        "khóa dầu/năng lượng. Nên `AIGPR_OIL` **không độc lập** với `AIGPR` — nó là tập "
        "con đã lọc. Tính độc lập đo ở §2 là **giữa các VÙNG với nhau**, không phải giữa "
        "oil và chuỗi tổng (tương quan hai cái đó là "
        f"{s['corr_oil_total']}). Đừng đọc lẫn hai điều này.",
        "3. **Phụ thuộc GPT-4o mini** (temperature 0). Model bị deprecate là mất khả năng "
        "tái lập y hệt — `docs/16` §4.2 đã ghi, vẫn còn nguyên.",
        "4. **Chỉ 3 tờ báo**, so với 10–11 tờ của GPRD gốc. Nền nguồn hẹp hơn.\n",
        "## 8. Ranh giới với chân B của DỰ ÁN NÀY — đừng để lẫn\n",
        "AI-GPR đo **tỷ lệ đưa tin về rủi ro trong báo chí**. Chân B của ta đo **mức leo "
        "thang trong MỘT phát ngôn chính thức**. Hai thứ khác nhau về bản chất:\n",
        "| | AI-GPR | Chân B (`statement_scorer` + `s_gpr`) |",
        "|---|---|---|",
        "| Đầu vào | bài báo | phát ngôn chính thức |",
        "| Thang điểm | 0.0…1.0, MỘT chiều | −1.0…+1.0, HAI chiều (có hòa giải) |",
        "| Tổng hợp | `Σ Sᵢ / Aₜ` (tỷ lệ đưa tin) | `Σ w(role)·max(v,0)·specificity` |",
        "| Trọng số người nói | không có | có (`w(role)`) |",
        "| Nhịp | chỉ số ngày | theo từng tin, realtime |\n",
        "→ **AI-GPR không thay được chân B, và chân B không tái lập AI-GPR.** Chiều hòa "
        "giải (v < 0) và trọng số vai người phát ngôn là hai thứ AI-GPR **không có** — "
        "đó đúng là phần giá trị tự xây mà CLAUDE.md #2 chỉ ra. Nếu sau này ai đó kéo "
        "chân B về phía chấm bài báo 0–1 một chiều thì đó là **đánh mất khác biệt**, "
        "không phải nâng cấp.\n",
        "## 9. Điều report này KHÔNG trả lời\n",
        "- Cường độ kênh năng lượng có **dự báo** được outcome không — cần hồi quy "
        "outcome, vượt trần `measurement`. Phải qua cổng IC gia tăng (CLAUDE.md #6) "
        "trước khi vào production.",
        "- Trọng số nên gán cho từng vùng — đó là ước lượng, không phải mô tả.",
        "- Có nên thay `AIGPR_OIL` bằng tổng 8 vùng không — chúng **không cộng về** "
        "chuỗi tổng (một bài báo gắn nhiều vùng, `docs/16` §1), nên là hai đại lượng "
        "khác nhau, phải chọn có chủ đích.\n",
    ]

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E4_aigpr_unique_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    for k, v in s.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
