"""run_fomc_gpr_salience.py — do do hien dien cua GPR trong van ban Fed. 🔬 research

Thu thap FOMC statement/minutes THAT tu federalreserve.gov -> cham bang LLM theo
rubric `scoring/policy_gpr_scorer.py` -> chuoi thang + report versioned.

CAI NAY DO GI, VA KHONG DO GI:
    DO    : rui ro dia chinh tri hien dien den dau trong van ban chinh sach Fed,
            qua kenh nao, co duoc trinh bay nhu yeu to anh huong quyet dinh khong.
    KHONG : cu soc chinh sach tien te My (da co ban do sach hon tu gia phai sinh
            quanh cua so FOMC — xem docstring `ingest/fomc.py`), va khong do
            hawkish/dovish.

PHAM VI MAC DINH `--from-year 2000`: trung moc bat dau mau cua bang γ tang 2
    (2000-02, xem T2_full_*.md) de hai chuoi doi chieu duoc tren CUNG cua so.

TRAN CLAIM: `measurement`. Report chi mo ta van ban noi gi. Cau "GPR di vao ham
    phan ung chinh sach" la muc `association`, can hoi quy — KHONG duoc viet vao
    report nay.

BACKFILL DOC VAN BAN THAT. Tuyet doi khong hoi LLM "nho lai" noi dung cu: do la
    sinh du lieu tu tri nho model (#1) va nhiem hindsight (`training_cutoff`).

CHAY:
    python scripts/run_fomc_gpr_salience.py --collect-only        # khong goi LLM
    python scripts/run_fomc_gpr_salience.py --from-year 2000
Cau hinh LLM doc tu .env: VLLM_API_BASE / VLLM_MODEL / VLLM_API_KEY.

Guard P1: moi so trong narrative lay tu dict `stats`, khong go tay.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.ingest.fomc import (  # noqa: E402
    fetch_document,
    list_archive,
)
from gpr_engine.scoring.policy_gpr_scorer import (  # noqa: E402
    PolicyScorerConfig,
    RUBRIC_VERSION,
    score_document,
)

REPORTS = Path("docs/reports")
DATADIR = REPORTS / "data"
CACHE = Path("data/cache/fomc_gpr_salience.jsonl")


def load_env(path: str = ".env") -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def build_llm(env: dict[str, str]):
    from gpr_engine.scoring.statement_scorer import openai_chat_client

    base = env.get("VLLM_API_BASE", "").rstrip("/")
    if not base:
        raise SystemExit(
            "Thieu VLLM_API_BASE trong .env — khong doan endpoint. "
            "Dung --collect-only neu chi muon thu thap van ban.")
    if not base.endswith("/v1"):
        base += "/v1"
    return openai_chat_client(model=env.get("VLLM_MODEL", "default"),
                              base_url=base,
                              api_key=env.get("VLLM_API_KEY") or "dummy")


def collect(from_year: int, to_year: int) -> list:
    """Release tu trang lich hien tai + cac trang nam lich su, khu trung.

    Fed CHI xuat ban `fomchistorical<YYYY>.htm` cho nhung nam da lui du xa; nam
    gan day nam o trang lich. Nen 404 tren mot nam la BINH THUONG, khong phai
    loi — bo qua va bao coverage, thay vi de ca lan chay gay.
    """
    rels = list_archive(strict=False)                      # lich hien tai
    missing = []
    for y in range(from_year, to_year + 1):
        try:
            rels += list_archive(years=[y], strict=False)
        except Exception as e:                             # noqa: BLE001
            missing.append((y, type(e).__name__))
    if missing:
        print(f"      (không có trang lịch sử: "
              f"{', '.join(str(y) for y, _ in missing)} — nằm ở trang lịch hoặc "
              "Fed chưa xuất bản)")
    seen, out = set(), []
    for r in sorted(rels, key=lambda r: r.published_at):
        if r.published_at.year < from_year:
            continue
        key = (r.doc_type, r.url)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def load_cache() -> dict:
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["key"]] = rec["value"]
    return out


class JsonlCache(dict):
    """Cache ghi thang xuong dia — chay lai sau khi dut khong mat tien da tra."""

    def __init__(self, path: Path):
        super().__init__(load_cache())
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


def monthly_series(rows: pd.DataFrame) -> pd.DataFrame:
    """Chuoi THANG. Grid dau thang that, KHONG forward-fill (#10).

    Thang khong hop FOMC thi KHONG co hang — de trong, khong dien 0: "khong hop"
    khac "hop va khong nhac gi".
    """
    df = rows.copy()
    df["month"] = pd.to_datetime(df["published_at"], utc=True).dt.tz_localize(
        None).dt.to_period("M").dt.to_timestamp()
    g = df.groupby("month")
    out = pd.DataFrame({
        "gpr_salience": g["gpr_salience"].mean(),
        "gpr_salience_max": g["gpr_salience_max"].max(),
        "binding_any": g["binding"].any(),
        "n_docs": g.size(),
    })
    return out.sort_index()


def compute_stats(rows: pd.DataFrame, monthly: pd.DataFrame,
                  elapsed: float, n_releases: int) -> dict:
    by_type = rows.groupby("doc_type")["gpr_salience"].mean()
    return {
        "n_releases_found": int(n_releases),
        "n_scored": int(len(rows)),
        "n_statements": int((rows["doc_type"] == "statement").sum()),
        "n_minutes": int((rows["doc_type"] == "minutes").sum()),
        "n_months": int(len(monthly)),
        "n_chunks_total": int(rows["n_chunks"].sum()),
        "mean_salience": round(float(rows["gpr_salience"].mean()), 4),
        "mean_salience_statement": round(float(by_type.get("statement", float("nan"))), 4),
        "mean_salience_minutes": round(float(by_type.get("minutes", float("nan"))), 4),
        "max_salience": round(float(rows["gpr_salience_max"].max()), 4),
        "share_binding": round(float(rows["binding"].mean()), 4),
        "share_zero": round(float((rows["gpr_salience"] == 0).mean()), 4),
        "n_with_channel": int(rows["channel"].notna().sum()),
        "elapsed_sec": round(elapsed, 1),
    }


def build_report(stats: dict, rows: pd.DataFrame, monthly: pd.DataFrame,
                 meta: dict) -> list[str]:
    p: list[str] = []
    p.append("# Độ hiện diện của rủi ro địa chính trị trong văn bản Fed\n")
    p.append("> 🔬 Research. Sinh tự động bởi `scripts/run_fomc_gpr_salience.py`. "
             "Văn bản THẬT từ federalreserve.gov, chấm bằng LLM theo rubric "
             "`scoring/policy_gpr_scorer.py`.\n")
    p.append("**Claim tối đa: `measurement`.** Bảng này mô tả VĂN BẢN NÓI GÌ. "
             "Câu \"GPR đi vào hàm phản ứng chính sách\" là mức `association`, "
             "cần hồi quy — không có trong report này.\n")
    p.append("**KHÔNG phải cú sốc chính sách tiền tệ.** Cú sốc đó đã có bản đo "
             "sạch hơn từ giá phái sinh quanh cửa sổ FOMC (Kuttner 2001; "
             "Gürkaynak-Sack-Swanson 2005; Nakamura-Steinsson 2018). Đây là "
             "chiều ngược lại: địa chính trị hiện diện đến đâu trong phát ngôn Fed.\n")

    p.append("## Metadata\n")
    p.append(f"- **model**: `{meta['model_version']}` (rubric `{meta['rubric_version']}`, "
             f"prompt `{meta['prompt_version']}`, temperature {meta['temperature']})")
    p.append(f"- **training_cutoff**: {meta['training_cutoff']}")
    p.append(f"- **git commit**: `{meta['git_commit']}`")
    p.append(f"- **generated_at**: {meta['generated_at']}")
    p.append(f"- **phạm vi**: {meta['range_start']} → {meta['range_end']} "
             f"({stats['n_scored']} văn bản: {stats['n_statements']} statement + "
             f"{stats['n_minutes']} minutes, {stats['n_chunks_total']} đoạn chấm)")
    p.append(f"- **thời gian chạy**: {stats['elapsed_sec']} giây\n")

    p.append("## Kết quả\n")
    p.append(f"Trung bình `gpr_salience` = **{stats['mean_salience']}** "
             f"(statement {stats['mean_salience_statement']} · "
             f"minutes {stats['mean_salience_minutes']}); đỉnh "
             f"{stats['max_salience']}. **{stats['share_binding']}** tỉ lệ văn bản "
             f"có ít nhất một đoạn `binding` (địa chính trị được trình bày như yếu "
             f"tố ảnh hưởng quyết định/triển vọng); {stats['share_zero']} tỉ lệ "
             f"hoàn toàn không có nội dung địa chính trị. "
             f"{stats['n_with_channel']}/{stats['n_scored']} văn bản nêu một kênh "
             "truyền dẫn cụ thể.\n")
    p.append("⚠️ **statement và minutes không so trực tiếp được**: statement dài "
             "~1.000-1.300 ký tự và thuần thủ tục, minutes dài 36.000-46.000 ký tự "
             "có hẳn mục thảo luận. Chênh lệch salience giữa hai loại phần lớn là "
             "chênh lệch THỂ LOẠI, không phải chênh lệch mức độ quan tâm.\n")

    p.append("## Top 15 văn bản theo `gpr_salience`\n")
    p.append("| Ngày công bố | Loại | salience | max | binding | kênh | trích dẫn |")
    p.append("|---|---|---|---|---|---|---|")
    for _, r in rows.nlargest(15, "gpr_salience").iterrows():
        ev = str(r["evidence"]).replace("|", "/")[:80]
        p.append(f"| {pd.Timestamp(r['published_at']).date()} | {r['doc_type']} "
                 f"| {r['gpr_salience']:.3f} | {r['gpr_salience_max']:.2f} "
                 f"| {'✓' if r['binding'] else '—'} | {r['channel'] or '—'} | {ev} |")
    p.append("")

    p.append("## Giới hạn — đọc trước khi trích số\n")
    p.append("- **Chưa hiệu chuẩn với người chấm.** Không có mẫu vàng do người "
             "dựng, nên chưa biết LLM chấm lệch bao nhiêu. Đây là điều kiện của "
             "cổng docs/14 §6.2 (người chấm thứ hai) — vẫn đang mở.")
    p.append("- **Chuỗi tháng bỏ trống tháng không họp FOMC**, không điền 0: "
             "\"không họp\" khác \"họp và không nhắc gì\". Forward-fill là vi phạm #10.")
    p.append("- **Văn bản dài được CHIA ĐOẠN chấm rồi gộp** (trung bình có trọng "
             "số theo độ dài), không cắt. Cắt sẽ làm salience của minutes lệch "
             "xuống có hệ thống vì phần bàn về rủi ro nằm giữa/cuối văn bản.")
    p.append("- **Bao phủ không đều theo thời kỳ**: URL statement đổi dạng nhiều "
             "lần; script đọc đúng những gì trang mục lục của Fed liệt kê, không "
             "suy ra URL. Số văn bản tìm được ghi ở Metadata.")
    p.append("- **`evidence` là trích dẫn do LLM trả về** — đã yêu cầu nguyên văn "
             "trong prompt nhưng CHƯA đối chiếu máy với văn bản gốc. Trước khi "
             "trích vào bất kỳ đâu, kiểm lại bằng tay.\n")

    p.append("## Human review (điền tay sau khi đọc)\n")
    p.append("- Điểm cao có khớp giai đoạn căng thẳng thật không: _chưa điền_")
    p.append("- `evidence` có đúng nguyên văn không (soi ngẫu nhiên 10 văn bản): _chưa điền_")
    p.append("- **Kết luận (GO/NO-GO + lý do + ngày + người):** _chưa điền_\n")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=2000)
    ap.add_argument("--to-year", type=int, default=dt.date.today().year)
    ap.add_argument("--collect-only", action="store_true",
                    help="chi thu thap van ban, KHONG goi LLM")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-chars", type=int, default=12000)
    args = ap.parse_args()

    t0 = time.time()
    print(f"[1/4] Mục lục FOMC {args.from_year}-{args.to_year}...")
    rels = collect(args.from_year, args.to_year)
    if args.limit:
        rels = rels[-args.limit:]
    print(f"      {len(rels)} văn bản "
          f"({sum(r.doc_type == 'statement' for r in rels)} statement + "
          f"{sum(r.doc_type == 'minutes' for r in rels)} minutes), "
          f"{rels[0].published_at.date()} → {rels[-1].published_at.date()}")

    print("[2/4] Tải nội dung...")
    docs, failed = [], []
    for i, r in enumerate(rels, 1):
        try:
            docs.append(fetch_document(r))
        except Exception as e:                       # noqa: BLE001
            failed.append((r.url, str(e)[:120]))
        if i % 25 == 0:
            print(f"      {i}/{len(rels)}...")
    print(f"      {len(docs)} tải được, {len(failed)} lỗi")
    for u, e in failed[:5]:
        print(f"        ✗ {u}: {e}")
    if args.collect_only:
        print(f"\nDỪNG (--collect-only). {len(docs)} văn bản, "
              f"{sum(len(d.text) for d in docs):,} ký tự.")
        return

    env = load_env()
    llm = build_llm(env)
    cfg = PolicyScorerConfig(model_version=env.get("VLLM_MODEL", "unknown"),
                             training_cutoff=dt.date(2026, 1, 1))
    cache = JsonlCache(CACHE)
    print(f"[3/4] Chấm bằng `{cfg.model_version}` (cache {len(cache)} đoạn)...")
    rows, score_failed = [], []
    for i, d in enumerate(docs, 1):
        try:
            rows.append(score_document(d, llm, cfg, cache=cache,
                                       max_chars=args.max_chars))
        except Exception as e:                       # noqa: BLE001
            score_failed.append((d.doc_id, str(e)[:120]))
        if i % 10 == 0:
            print(f"      {i}/{len(docs)}... ({time.time() - t0:.0f}s)")
    print(f"      {len(rows)} chấm được, {len(score_failed)} lỗi")
    for did, e in score_failed[:5]:
        print(f"        ✗ {did}: {e}")
    if not rows:
        raise SystemExit("Không chấm được văn bản nào — dừng, không ghi report rỗng.")

    df = pd.DataFrame(rows)
    monthly = monthly_series(df)
    stats = compute_stats(df, monthly, time.time() - t0, len(rels))

    import subprocess
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         text=True).strip()
    except Exception:                                # noqa: BLE001
        commit = "UNKNOWN"
    meta = {
        "model_version": cfg.model_version, "rubric_version": cfg.rubric_version,
        "prompt_version": cfg.prompt_version, "temperature": cfg.temperature,
        "training_cutoff": cfg.training_cutoff.isoformat(), "git_commit": commit,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "range_start": str(df["published_at"].min().date()),
        "range_end": str(df["published_at"].max().date()),
    }

    print("[4/4] Ghi report + CSV...")
    DATADIR.mkdir(parents=True, exist_ok=True)
    tag = f"{RUBRIC_VERSION}_{args.from_year}"
    df.to_csv(DATADIR / f"fomc_gpr_salience_{tag}.csv", index=False)
    monthly.to_csv(DATADIR / f"fomc_gpr_salience_monthly_{tag}.csv")
    out = REPORTS / f"FOMC_gpr_salience_{tag}.md"
    if out.exists():
        raise FileExistsError(f"{out} đã tồn tại — xóa CÓ CHỦ ĐÍCH rồi chạy lại.")
    out.write_text("\n".join(build_report(stats, df, monthly, meta)),
                   encoding="utf-8")
    print(f"\nDONE ({stats['elapsed_sec']}s). → {out}")


if __name__ == "__main__":
    main()
