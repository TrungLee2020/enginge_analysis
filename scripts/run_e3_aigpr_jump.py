"""run_e3_aigpr_jump.py — E3: AI-GPR có nên thay/bổ sung GPRD làm nguồn JUMP (chân A)?

🔬 RESEARCH (docs/10, CLAUDE.md #1) — KHÔNG tự đổi đường production. Sinh report
versioned vào docs/reports/, không bao giờ ghi đè.

CÂU HỎI: `service/store.py::load_jump_series` truy vấn CỨNG `series_id='GPRD'`.
AI-GPR đã ingest (12 chuỗi vào ext_series) nhưng không chạm đường serving nào.
`docs/16` §5 khẳng định đổi sang AI-GPR thì "PHẢI hiệu chuẩn lại ngưỡng q95/q99
vì AI-GPR mượt hơn, đuôi mỏng hơn, không có ngày bằng 0". Script này KIỂM
khẳng định đó trên dữ liệu thật thay vì tin theo.

PHƯƠNG PHÁP: cả hai chuỗi đi qua ĐÚNG đường production (`shocks.jump` với tham
số production window=250/q=0.95, rồi `expanding_percentile` min_periods=60, rồi
ngưỡng S4 `jump_pct > 95` của `config/ladder_v1.yaml`). So trên MẪU CHUNG.

TRẦN CLAIM: `measurement` — đo thuộc tính nội tại của thước đo (tần suất kích,
mức đồng thuận, thời điểm kích quanh sự kiện). KHÔNG hồi quy outcome, KHÔNG
claim cái nào "tốt hơn" theo nghĩa dự báo: câu đó thuộc KĐ-E1c (AUC trên gold
set ngoại sinh) và vẫn bị chặn bởi `data_blockers.gold_events_csv`.

Chạy: .venv/bin/python scripts/run_e3_aigpr_jump.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.econometrics.data_files import (  # noqa: E402
    DEFAULT_AI_GPR_DAILY,
    DEFAULT_GPR_DAILY,
    load_ai_gpr_daily,
    load_gpr_daily,
)
from gpr_engine.econometrics.shocks import jump  # noqa: E402
from gpr_engine.indices.s_gpr import expanding_percentile  # noqa: E402

REPORTS = Path("docs/reports")

# Tham so PRODUCTION — khong doi o day. Doi la doi thuoc do, phai qua governance.
JUMP_WINDOW, JUMP_Q, PCT_MIN_PERIODS, S4_THRESHOLD = 250, 0.95, 60, 95

# Su kien co NGAY XAC DINH KHACH QUAN (su kien lich su, khong phai phan doan).
# ⚠️ DAY KHONG PHAI `data/gold_events.csv` cua docs/13 §2.2 — gold set do doi
# HAI NGUOI dung tay, khong tra GPRD, va la thu quyet dinh primary_cell.shock.
# Danh sach nay chi de MO TA hanh vi quanh vai moc ai cung biet; n=8, khong du
# de suy dien, va Claude tu dung no lam gold set la vi pham chinh nguyen tac
# ngoai sinh cua docs/13. Doc dung muc do do.
EVENTS = {
    "1990-08-02": "Iraq xâm lược Kuwait",
    "1991-01-17": "Chiến dịch Desert Storm",
    "2001-09-11": "Tấn công 11/9",
    "2003-03-20": "Mỹ xâm lược Iraq",
    "2011-03-19": "Can thiệp Libya",
    "2014-03-18": "Nga sáp nhập Crimea",
    "2022-02-24": "Nga xâm lược Ukraine",
    "2023-10-07": "Hamas tấn công Israel",
}
EVENT_LEAD, EVENT_LAG = 3, 3   # cua so DOI XUNG — xem canh bao §2 trong report


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def main() -> None:
    gprd_raw = load_gpr_daily(DEFAULT_GPR_DAILY)
    aigpr_raw = load_ai_gpr_daily(DEFAULT_AI_GPR_DAILY)

    df = pd.concat([gprd_raw["GPRD"].rename("GPRD"),
                    aigpr_raw["AIGPR"].rename("AIGPR")], axis=1).dropna()
    pct = {c: expanding_percentile(jump(df[c], JUMP_WINDOW, JUMP_Q).dropna(),
                                   PCT_MIN_PERIODS) for c in ("GPRD", "AIGPR")}
    fire = pd.concat([(pct["GPRD"] > S4_THRESHOLD).rename("g"),
                      (pct["AIGPR"] > S4_THRESHOLD).rename("a")], axis=1).dropna()

    both = int((fire.g & fire.a).sum())
    only_g = int((fire.g & ~fire.a).sum())
    only_a = int((~fire.g & fire.a).sum())

    # Phat hien su kien + do tre kich, cua so DOI XUNG
    det = {"GPRD": 0, "AIGPR": 0}
    lead_rows, earlier = [], {"GPRD": 0, "AIGPR": 0, "tie": 0}
    for d, name in EVENTS.items():
        t = pd.Timestamp(d)
        w = slice(t - pd.Timedelta(days=EVENT_LEAD), t + pd.Timedelta(days=EVENT_LAG))
        offs = {}
        for c in ("GPRD", "AIGPR"):
            seg = pct[c].loc[w].dropna()
            hit = seg[seg > S4_THRESHOLD]
            if len(hit):
                det[c] += 1
                offs[c] = int((hit.index[0] - t).days)
            else:
                offs[c] = None
        if offs["GPRD"] is not None and offs["AIGPR"] is not None:
            if offs["GPRD"] < offs["AIGPR"]:
                earlier["GPRD"] += 1
            elif offs["AIGPR"] < offs["GPRD"]:
                earlier["AIGPR"] += 1
            else:
                earlier["tie"] += 1
        lead_rows.append((d, name, offs["GPRD"], offs["AIGPR"]))

    dev = fire.loc["2015":"2023"]
    s = {
        "n_common": len(df),
        "start": df.index.min().date().isoformat(),
        "end": df.index.max().date().isoformat(),
        "corr_level": round(float(df["GPRD"].corr(df["AIGPR"])), 3),
        "gprd_std": round(float(df["GPRD"].std()), 2),
        "aigpr_std": round(float(df["AIGPR"].std()), 2),
        "gprd_skew": round(float(df["GPRD"].skew()), 2),
        "aigpr_skew": round(float(df["AIGPR"].skew()), 2),
        "gprd_min": round(float(df["GPRD"].min()), 2),
        "aigpr_min": round(float(df["AIGPR"].min()), 2),
        "gprd_fire_pct": round(float(fire.g.mean()) * 100, 2),
        "aigpr_fire_pct": round(float(fire.a.mean()) * 100, 2),
        "union_pct": round(float((fire.g | fire.a).mean()) * 100, 2),
        "inter_pct": round(float((fire.g & fire.a).mean()) * 100, 2),
        "jaccard": round(both / (both + only_g + only_a), 3),
        "both": both, "only_gprd": only_g, "only_aigpr": only_a,
        "dev_jaccard": round(float((dev.g & dev.a).sum() / (dev.g | dev.a).sum()), 3),
        "dev_gprd_pct": round(float(dev.g.mean()) * 100, 2),
        "dev_aigpr_pct": round(float(dev.a.mean()) * 100, 2),
        "det_gprd": det["GPRD"], "det_aigpr": det["AIGPR"], "n_events": len(EVENTS),
        "earlier_gprd": earlier["GPRD"], "earlier_aigpr": earlier["AIGPR"],
        "earlier_tie": earlier["tie"],
        "gprd_last": gprd_raw.index.max().date().isoformat(),
        "aigpr_last": aigpr_raw.index.max().date().isoformat(),
        "freshness_days": int((aigpr_raw.index.max() - gprd_raw.index.max()).days),
    }
    for name, s0, e0 in (("p1", "1986", "1999"), ("p2", "2000", "2014"),
                         ("p3", "2015", "2026")):
        sub = fire.loc[s0:e0]
        s[f"{name}_gprd"] = round(float(sub.g.mean()) * 100, 2)
        s[f"{name}_aigpr"] = round(float(sub.a.mean()) * 100, 2)

    dv = f"{_sha(DEFAULT_GPR_DAILY)[:6]}_{_sha(DEFAULT_AI_GPR_DAILY)[:6]}"
    lead_tbl = "\n".join(
        f"| {d} | {n} | {'—' if g is None else f'{g:+d}'} | "
        f"{'—' if a is None else f'{a:+d}'} |" for d, n, g, a in lead_rows)

    parts = [
        "# E3 — AI-GPR làm nguồn JUMP chân A: đo trước khi nối\n",
        f"**Ngày chạy:** {dt.date.today().isoformat()} · **git:** `{_git_commit()}` · "
        f"**data_version:** `{dv}`",
        f"**Mẫu chung:** {s['start']} → {s['end']}, {s['n_common']} ngày · "
        f"**Trần claim:** `measurement`\n",
        "## 0. Câu hỏi\n",
        "`service/store.py::load_jump_series` truy vấn cứng `series_id='GPRD'`. AI-GPR "
        "đã ingest nhưng không chạm đường serving. `docs/16` §5 khẳng định đổi sang "
        "AI-GPR **phải hiệu chuẩn lại** ngưỡng q95/q99 vì AI-GPR mượt hơn/đuôi mỏng "
        "hơn/không có ngày bằng 0. Báo cáo này kiểm khẳng định đó.\n",
        "## 1. ✅ Kết luận chính: KHÔNG cần hiệu chuẩn lại ngưỡng — `docs/16` §5 sai ở điểm này\n",
        "Mức (level) hai chuỗi đúng là khác nhau như `docs/16` mô tả:\n",
        f"- độ lệch chuẩn {s['gprd_std']} (GPRD) so với {s['aigpr_std']} (AI-GPR)",
        f"- skew {s['gprd_skew']} so với {s['aigpr_skew']}",
        f"- giá trị nhỏ nhất {s['gprd_min']} so với {s['aigpr_min']} — AI-GPR "
        "thật sự không bao giờ chạm 0",
        f"- tương quan mức: {s['corr_level']}\n",
        "**Nhưng khác biệt đó bị `jump()` triệt tiêu.** JUMP dựng trên **z-score "
        "rolling** (`z = (x − mean_roll)/std_roll`) rồi trừ **phân vị q của chính z** "
        "— cả hai bước đều **bất biến theo thang đo**. Mức và độ lệch chuẩn bị chuẩn "
        "hóa đi trước khi ngưỡng được áp. Đo trên dữ liệu thật, dùng ĐÚNG tham số "
        "production:\n",
        f"| Chuỗi | % ngày kích S4 (`jump_pct > {S4_THRESHOLD}`) |",
        "|---|---|",
        f"| GPRD | {s['gprd_fire_pct']}% |",
        f"| AI-GPR | {s['aigpr_fire_pct']}% |\n",
        "Ổn định qua ba giai đoạn, không phải trùng hợp một lần:\n",
        "| Giai đoạn | GPRD | AI-GPR |",
        "|---|---|---|",
        f"| 1986–1999 | {s['p1_gprd']}% | {s['p1_aigpr']}% |",
        f"| 2000–2014 | {s['p2_gprd']}% | {s['p2_aigpr']}% |",
        f"| 2015–2026 | {s['p3_gprd']}% | {s['p3_aigpr']}% |\n",
        "→ Ngưỡng q95/q99 **giữ nguyên được**. Cảnh báo của `docs/16` §5 đúng cho bất "
        "kỳ thứ gì đọc **mức thô** (ví dụ ngưỡng cố định trên level), nhưng **không "
        "áp cho JUMP** — cần đính chính trong doc đó.\n",
        "## 2. ⚠️ Nhưng KHÔNG được đọc thành 'hai chuỗi thay thế nhau được'\n",
        "Cùng tần suất **không phải** cùng ngày:\n",
        f"- kích ở cả hai chuỗi: {s['both']} ngày",
        f"- chỉ GPRD kích: {s['only_gprd']} ngày",
        f"- chỉ AI-GPR kích: {s['only_aigpr']} ngày",
        f"- **Jaccard = {s['jaccard']}** (cửa sổ dự án 2015–2023: {s['dev_jaccard']})\n",
        "Nói cách khác: khoảng bốn phần năm số ngày kích của chuỗi này thì chuỗi kia "
        "im lặng. Đổi nguồn JUMP **là đổi thước đo**, không phải đổi cách đọc cùng "
        "một thước đo — dù tần suất trùng khớp.\n",
        "## 3. Hành vi quanh sự kiện lớn (mô tả, KHÔNG phải cổng E1c)\n",
        "⚠️ **Đây không phải `data/gold_events.csv`.** Gold set của `docs/13` §2.2 do "
        "hai người dựng tay, không tra GPRD, và là thứ quyết định "
        "`primary_cell.shock`; Claude tự dựng danh sách rồi coi là gold set là vi phạm "
        "chính nguyên tắc ngoại sinh. Danh sách dưới chỉ gồm vài mốc lịch sử có ngày "
        "khách quan, n nhỏ, đọc như **mô tả** chứ không phải kiểm định.\n",
        f"Cửa sổ đối xứng [D−{EVENT_LEAD}, D+{EVENT_LAG}]: "
        f"GPRD phát hiện {s['det_gprd']}/{s['n_events']}, "
        f"AI-GPR {s['det_aigpr']}/{s['n_events']}.\n",
        "**Đính chính một kết quả trung gian của chính phiên này:** với cửa sổ *một "
        "phía* [D, D+3], AI-GPR trông như trượt Crimea 2014 (phân vị 0). Sai — nó kích "
        "**trước** ngày sáp nhập (quanh trưng cầu dân ý 16/03), tức nằm ngoài cửa sổ "
        "một phía. Artifact của cách đặt cửa sổ, không phải của dữ liệu. Bảng dưới "
        "dùng cửa sổ đối xứng.\n",
        "| Ngày | Sự kiện | GPRD (ngày lệch) | AI-GPR (ngày lệch) |",
        "|---|---|---|---|",
        lead_tbl + "\n",
        f"Số sự kiện mỗi chuỗi kích sớm hơn: GPRD {s['earlier_gprd']}, "
        f"AI-GPR {s['earlier_aigpr']}, bằng nhau {s['earlier_tie']}. "
        "Gợi ý AI-GPR nhạy sớm hơn — **gợi ý, không phải kết luận**: n quá nhỏ, "
        "không có kiểm định, và chọn sự kiện nào cũng là một bậc tự do.\n",
        "## 4. Chi phí của phương án 'dùng cả hai'\n",
        "| Cách kết hợp | % ngày kích S4 |",
        "|---|---|",
        f"| chỉ GPRD (hiện tại) | {s['gprd_fire_pct']}% |",
        f"| chỉ AI-GPR | {s['aigpr_fire_pct']}% |",
        f"| hợp (kích nếu **bất kỳ** chuỗi nào vượt) | {s['union_pct']}% |",
        f"| giao (kích khi **cả hai** vượt) | {s['inter_pct']}% |\n",
        "Hợp làm S4 kích **gần gấp đôi** — đổi ý nghĩa của bậc S4, không phải nâng "
        "cấp miễn phí. Giao thì chặt hơn nhiều nhưng cũng là một thước đo mới. Cả hai "
        "đều là **thay đổi spec**, phải qua governance, không phải việc nối dây.\n",
        "## 5. Lợi ích vận hành THẬT và đo được: độ tươi\n",
        f"- GPRD mới nhất: {s['gprd_last']}",
        f"- AI-GPR mới nhất: {s['aigpr_last']}",
        f"- AI-GPR mới hơn **{s['freshness_days']} ngày**\n",
        "Đây không phải chi tiết vụn: ngưỡng `chain_a_stale` của pipeline là 35 ngày, "
        "và chạy thật ngày 2026-08-08 đã bị gắn cờ stale đúng vì GPRD dừng ở "
        f"{s['gprd_last']}. Với cùng ngày đó, AI-GPR **không** stale.\n",
        "## 6. Khuyến nghị\n",
        "1. **Giữ GPRD làm nguồn JUMP mặc định.** Không có bằng chứng AI-GPR dự báo "
        "tốt hơn — câu đó thuộc KĐ-E1c (AUC trên gold set) và vẫn bị chặn bởi "
        "`data_blockers.gold_events_csv`. Đổi mặc định lúc này là chọn bằng cảm tính.",
        "2. **Gỡ hard-code `series_id='GPRD'`** thành tham số cấu hình được, mặc định "
        "vẫn GPRD (hành vi không đổi). Hiện tại muốn thử AI-GPR phải sửa mã nguồn — "
        "đó mới là thứ đáng sửa ngay.",
        "3. **Fallback khi GPRD stale**: chuỗi chính stale thì đọc AI-GPR thay vì trả "
        "chuỗi rỗng, và ghi rõ đã dùng chuỗi nào. Giải đúng vấn đề vận hành ở §5 mà "
        "không đụng thước đo khi GPRD còn tươi.",
        "4. **KHÔNG dùng hợp/giao** cho tới khi có gold set — §4 cho thấy đó là đổi "
        "spec, và ta chưa có tiêu chí để nói bản nào tốt hơn.",
        "5. **Đính chính `docs/16` §5**: khẳng định 'phải hiệu chuẩn lại q95/q99' sai "
        "với JUMP (§1). Giữ cảnh báo cho các dùng khác đọc mức thô.\n",
        "## 7. Điều báo cáo này KHÔNG trả lời\n",
        "- Chuỗi nào **dự báo** outcome vĩ mô tốt hơn — cần hồi quy outcome, ngoài trần "
        "`measurement`.",
        "- Chuỗi nào phát hiện sốc **đúng hơn** — cần gold set ngoại sinh (KĐ-E1c), "
        "vẫn bị chặn.",
        "- Ảnh hưởng của việc đổi nguồn lên bảng γ tầng 2 — γ hiện ước lượng trên "
        "GPRD; đổi shock thì phải chạy lại `run_t2_full.py`, chưa làm.\n",
    ]

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"E3_aigpr_jump_{dv}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — không ghi đè (docs/10 F1).")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"DONE. Report: {out}")
    for k, v in s.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
