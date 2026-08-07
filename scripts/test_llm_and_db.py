"""test_llm_and_db.py — kiem tra thu công, KHONG cần Kafka.

Mục đích: xác nhận endpoint LLM (OpenAI thật, hoặc bất kỳ endpoint tương
thích OpenAI nào — vd Gemini qua OPENAI_BASE_URL) trả về ĐÚNG contract JSON
mà `scoring.statement_scorer.parse_score` đòi hỏi, TRƯỚC khi cắm vào pipeline
Kafka đầy đủ. Kafka là lớp I/O tách biệt (`service/kafka_io.py`) — bước kiểm
tra ở đây hoàn toàn không chạm tới nó, đúng câu hỏi "chỉ thiếu Kafka thôi thì
vẫn được chứ": được, vì `process_news_item_live()` (hàm pipeline "1 tin vào
-> 1 kết quả" thật) không phụ thuộc Kafka — chỉ phụ thuộc LLM client +
Postgres (nếu dùng --dsn) + file γ đã công bố (đã có sẵn trong repo).

Hai chế độ:
  1. Không --dsn: chỉ gọi `score_statement()` — in RAW giá trị LLM trả về.
     Không chạm DB, dùng để soi nhanh model có theo đúng contract JSON
     không (đặc biệt quan trọng khi đổi sang model khác GPT-4o-mini —
     `response_format={"type": "json_object"}` không phải model nào cũng hỗ
     trợ giống nhau).
  2. Có --dsn: chạy `process_news_item_live()` đầy đủ — ghi thật vào
     Postgres (statements/statement_scores/ladder_state/news_assessment).
     Cần đã nạp schema (sql/001, sql/002) và lý tưởng là đã ingest GPRD
     (thiếu thì `jump_series_provider` trả chuỗi rỗng — pipeline vẫn chạy,
     chỉ JUMP percentile sẽ NaN, không crash).

Gemini qua endpoint tương thích OpenAI (Google công bố tại
generativelanguage.googleapis.com/v1beta/openai/): đặt GEMINI_API_KEY thay
vì OPENAI_API_KEY — script này tự map sang OPENAI_API_KEY + OPENAI_BASE_URL
mặc định của Gemini nếu OPENAI_BASE_URL chưa đặt tường minh. `openai_chat_client()`
trong statement_scorer.py KHÔNG đổi — nó vốn đã nhận base_url tuỳ ý, đây chỉ là
tiện ích map biến môi trường cho việc test.

⚠️ CHƯA XÁC MINH: Gemini có tôn trọng `response_format={"type": "json_object"}`
giống hệt OpenAI hay không (Google tài liệu có nói hỗ trợ JSON mode qua lớp
tương thích, nhưng chưa tự chạy thật để xác nhận trong phiên này — không có
API key thật trong sandbox). Đây chính là lý do tồn tại của script: chạy nó
với key thật để BIẾT, không đoán. Nếu Gemini trả JSON không đúng contract,
`ScoreParseError` sẽ raise với nội dung lỗi rõ ràng — không sửa hộ, không
đoán JSON còn thiếu là gì (statement_scorer.parse_score đã tự retry 1 lần
kèm thông báo lỗi gửi lại cho model trước khi raise hẳn).

vLLM tự host cũng đi đúng đường này (đã chạy thật với Qwen3-14B-AWQ): đặt
VLLM_API_BASE + VLLM_MODEL (+ VLLM_API_KEY, mặc định "EMPTY"). Script tự thêm
hậu tố `/v1` nếu thiếu. Qwen3 tôn trọng `response_format={"type":"json_object"}`
qua guided decoding của vLLM nên KHÔNG rò khối `<think>` — không cần
`enable_thinking=false`; nếu đổi sang server không hỗ trợ JSON mode thì thân
`<think>` sẽ làm `parse_score` raise, đó là dấu hiệu cần bật guided decoding.

Biến môi trường: script tự nạp `.env` ở repo root (KEY=value, biến đã export ở
shell thắng, không bị ghi đè). Có sẵn nhiều bộ trong `.env` thì `--provider`
chọn tay; auto ưu tiên OPENAI_API_KEY > VLLM_API_BASE > GEMINI_API_KEY.

Chạy:
  # chỉ test LLM (không DB, không Kafka) — cấu hình lấy từ .env:
  python scripts/test_llm_and_db.py
  python scripts/test_llm_and_db.py --provider vllm      # ép dùng vLLM nội bộ

  # hoặc truyền tường minh, ghi đè .env:
  GEMINI_API_KEY=... GPR_LLM_MODEL=gemini-2.0-flash python scripts/test_llm_and_db.py

  # test cả ghi Postgres thật (cần: docker compose up -d postgres, đã nạp
  # sql/001+002, có thể chưa ingest GPRD):
  GEMINI_API_KEY=... GPR_LLM_MODEL=gemini-2.0-flash python scripts/test_llm_and_db.py \\
      --dsn postgresql://gpr:gpr_dev_password@localhost:5432/gpr_engine
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gpr_engine.scoring.statement_scorer import (
    ScoreParseError,
    ScorerConfig,
    Statement,
    openai_chat_client,
    score_statement,
)

# Endpoint tương thích OpenAI của Gemini (Google công bố công khai). Chỉ dùng
# làm MẶC ĐỊNH khi có GEMINI_API_KEY mà chưa đặt OPENAI_BASE_URL tường minh —
# đặt OPENAI_BASE_URL thì luôn ưu tiên giá trị đó, không ghi đè ngầm.
GEMINI_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

DEFAULT_TEXT = (
    "We are prepared to impose sanctions if these violations continue, "
    "and we call on our allies to join us in condemning this aggression."
)


def _load_dotenv(path: Path) -> None:
    """Nạp `.env` ở repo root vào os.environ.

    Cùng ngữ nghĩa với `python-dotenv`: biến ĐÃ có trong môi trường thắng
    (không ghi đè) — chạy `GPR_LLM_MODEL=x python scripts/...` vẫn ưu tiên giá
    trị gõ ở dòng lệnh. Dùng python-dotenv nếu có (xử lý quote/multiline đầy
    đủ); không có thì parser tối giản bên dưới đủ cho định dạng KEY=value mà
    docker-compose `env_file` cũng chấp nhận — script test không nên chết chỉ
    vì thiếu một dependency tuỳ chọn.
    """
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
    except ImportError:
        pass
    else:
        load_dotenv(path, override=False)
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_llm_env(provider: str) -> tuple[str, str, str | None, str]:
    """Tra (provider_da_chon, api_key, base_url, model).

    `provider="auto"` chon theo thu tu OPENAI -> VLLM -> GEMINI: OPENAI_API_KEY
    tuong minh thang truoc (khong doi hanh vi cu), roi den vLLM tu host (endpoint
    rieng thi khong ai dat nham), cuoi cung Gemini. Dat --provider de chon tay
    khi .env co san nhieu hon mot bo (truong hop thuong gap: vua giu key Gemini
    vua tro vLLM noi bo).

    MOI provider mang theo TEN MODEL cua chinh no — gui `gemini-2.0-flash` sang
    vLLM la 404, nen GPR_LLM_MODEL (bien chung, dung cho OpenAI/Gemini) KHONG duoc
    tran sang nhanh vLLM; nhanh do lay VLLM_MODEL.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    openai_base = os.environ.get("OPENAI_BASE_URL")
    vllm_base = os.environ.get("VLLM_API_BASE")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    generic_model = os.environ.get("GPR_LLM_MODEL")

    if provider == "auto":
        provider = ("openai" if openai_key else
                    "vllm" if vllm_base else
                    "gemini" if gemini_key else "none")

    if provider == "openai":
        if not openai_key:
            raise RuntimeError("provider=openai nhưng thiếu OPENAI_API_KEY.")
        return provider, openai_key, openai_base, generic_model or "gpt-4o-mini"

    if provider == "vllm":
        if not vllm_base:
            raise RuntimeError("provider=vllm nhưng thiếu VLLM_API_BASE.")
        model = os.environ.get("VLLM_MODEL")
        if not model:
            raise RuntimeError(
                "provider=vllm nhưng thiếu VLLM_MODEL — phải khớp `id` mà server "
                "báo ở GET {}/models, không đoán hộ.".format(vllm_base.rstrip("/")))
        # vLLM mount API tuong thich OpenAI tai /v1; SDK noi duoi
        # "/chat/completions" -> thieu /v1 la 404. Them neu chua co, khong ep
        # nguoi dung nho quy uoc nay.
        base = vllm_base.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        # SDK OpenAI raise neu api_key rong; "EMPTY" la quy uoc cua vLLM khi
        # server chay khong bat --api-key.
        return provider, os.environ.get("VLLM_API_KEY") or "EMPTY", base, model

    if provider == "gemini":
        if not gemini_key:
            raise RuntimeError("provider=gemini nhưng thiếu GEMINI_API_KEY.")
        return (provider, gemini_key,
                openai_base or GEMINI_OPENAI_COMPAT_BASE_URL,
                generic_model or "gpt-4o-mini")

    raise RuntimeError(
        "Không tìm thấy cấu hình LLM nào — cần OPENAI_API_KEY, hoặc VLLM_API_BASE"
        " + VLLM_MODEL, hoặc GEMINI_API_KEY. Đặt trong .env ở repo root (script "
        "tự nạp) hoặc export ở shell.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=None,
                    help="Có -> ghi thật vào Postgres qua process_news_item_live(). "
                         "Không -> chỉ gọi score_statement(), không chạm DB.")
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--speaker", default="Test Speaker")
    ap.add_argument("--speaker-role", default="minister",
                    help="Phải thuộc DEFAULT_ROLE_WEIGHTS_INIT (s_gpr.py): "
                         "head_of_state|minister|spokesperson|central_bank_governor")
    ap.add_argument("--source", default="manual_test")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "openai", "vllm", "gemini"],
                    help="auto = OPENAI_API_KEY > VLLM_API_BASE > GEMINI_API_KEY.")
    args = ap.parse_args()

    _load_dotenv(REPO_ROOT / ".env")
    provider, api_key, base_url, model = _resolve_llm_env(args.provider)
    training_cutoff_raw = os.environ.get("GPR_TRAINING_CUTOFF")
    training_cutoff = (pd.Timestamp(training_cutoff_raw).date()
                       if training_cutoff_raw else dt.datetime.now(dt.UTC).date())

    print(f"[test_llm_and_db] provider={provider} model={model} "
          f"base_url={base_url or '(OpenAI mặc định)'}")
    llm = openai_chat_client(model=model, base_url=base_url, api_key=api_key)
    config = ScorerConfig(model_version=model, training_cutoff=training_cutoff)

    stmt = Statement(source=args.source, published_at=pd.Timestamp.now(tz="UTC"),
                     speaker=args.speaker, speaker_role=args.speaker_role,
                     text=args.text)

    print("\n--- Gọi score_statement() (LLM thật, chưa chạm DB) ---")
    try:
        score = score_statement(stmt, llm, config)
    except ScoreParseError as e:
        print(f"\n❌ LLM KHÔNG trả đúng contract JSON: {e}")
        print("Model không tuân JSON mode giống OpenAI, hoặc thiếu/sai key bắt buộc.")
        raise SystemExit(1) from e

    if score is None:
        print("(encoder lọc — không xảy ra vì không truyền encoder ở đây)")
        return

    print("\nGiá trị LLM trả về (đã parse, khớp contract):")
    print(json.dumps({k: v for k, v in score.items()
                      if k not in ("published_at",)}, indent=2, ensure_ascii=False, default=str))

    if not args.dsn:
        print("\n(Không có --dsn — dừng ở đây, chưa chạm Postgres. "
             "Kafka hoàn toàn không cần cho bước này.)")
        return

    print(f"\n--- Ghi thật qua process_news_item_live() vào {args.dsn} ---")
    from gpr_engine.pipeline.news_pipeline import ExcludedResult, process_news_item_live

    result = process_news_item_live(stmt, args.dsn, llm, config)
    if isinstance(result, ExcludedResult):
        print(f"Bị loại: {result.reason}")
        return

    print(f"S-GPR now={result.s_gpr_now} prev={result.s_gpr_prev} pctile={result.s_gpr_pctile}")
    print(f"Ladder state={result.ladder_state} (computed={result.ladder_computed})")
    print(f"Transmission channel={result.transmission_channel}")
    print("\nMeasurement card:\n", result.measurement_card)
    print("\nMacro brief:\n", result.macro_brief)
    print("\nVN note:\n", result.vn_note)
    print("\n✅ Đã ghi vào statements/statement_scores/news_assessment"
         + ("/ladder_state" if result.ladder_computed else " (ladder_state KHÔNG ghi — xem ladder_computed)")
         + f". Kiểm tra bằng: SELECT * FROM news_assessment ORDER BY id DESC LIMIT 1; (dsn={args.dsn})")


if __name__ == "__main__":
    main()
