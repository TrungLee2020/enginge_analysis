"""run_news_service.py — entrypoint SONG: doc tin tu Kafka, day ket qua GPR ra Kafka.

🏭 production-path. Vong lap dai han noi `pipeline.news_pipeline.process_news_item_live`
voi `service.kafka_io` — day la ban THAT cua chuoi "1 tin vao -> 1 ket qua ra"
(xem `pipeline/news_pipeline.py` cho logic, o day CHI la wiring config/env).

Bien moi truong (khong sua code de doi):
    GPR_DB_DSN            bat buoc — 'postgresql://user:pass@host/db'
    OPENAI_API_KEY        bat buoc (hoac tuong duong tren endpoint OpenAI-compatible)
    OPENAI_BASE_URL       tuy chon — tro sang endpoint OpenAI-compatible khac
    GPR_LLM_MODEL         mac dinh 'gpt-4o-mini' — doi model KHONG can sua code
    GPR_MODEL_VERSION     mac dinh = GPR_LLM_MODEL — vao statement_scores.model_version
    GPR_TRAINING_CUTOFF   bat buoc, ISO date — contamination guard (docs/14 §3.1.4)
    GPR_KAFKA_BOOTSTRAP   bat buoc — 'host1:9092,host2:9092'
    GPR_KAFKA_GROUP       mac dinh 'gpr-news-service'
    GPR_KAFKA_TOPIC_IN    mac dinh 'gpr.news.raw'
    GPR_KAFKA_TOPIC_OUT   mac dinh 'gpr.news.assessment'
    GPR_GAMMA_REPORTS_DIR mac dinh 'docs/reports'

Schema JSON tren topic input (khop `scoring.statement_scorer.Statement`):
    {"source": str, "url": str|null, "published_at": "ISO8601", "speaker": str,
     "speaker_role": str, "speaker_country": str|null, "text": str,
     "lang": str = "en", "cadence": "daily"|"slow" = "daily"}

Chay:  python scripts/run_news_service.py
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gpr_engine.pipeline.news_pipeline import (  # noqa: E402
    ExcludedResult,
    process_news_item_live,
)
from gpr_engine.scoring.statement_scorer import (  # noqa: E402
    ScorerConfig,
    Statement,
    openai_chat_client,
)
from gpr_engine.service import store  # noqa: E402
from gpr_engine.service.kafka_io import (  # noqa: E402
    DEFAULT_INPUT_TOPIC,
    DEFAULT_OUTPUT_TOPIC,
    confluent_publisher,
    run_consumer_loop,
)


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc: {name}")
    return val


def _statement_from_payload(payload: dict) -> Statement:
    return Statement(
        source=payload["source"], url=payload.get("url"),
        published_at=pd.Timestamp(payload["published_at"]),
        speaker=payload["speaker"], speaker_role=payload["speaker_role"],
        speaker_country=payload.get("speaker_country"), text=payload["text"],
        lang=payload.get("lang", "en"), cadence=payload.get("cadence", "daily"))


def main() -> None:
    dsn = _require_env("GPR_DB_DSN")
    _require_env("OPENAI_API_KEY")
    training_cutoff = pd.Timestamp(_require_env("GPR_TRAINING_CUTOFF")).date()
    bootstrap = _require_env("GPR_KAFKA_BOOTSTRAP")

    model = os.environ.get("GPR_LLM_MODEL", "gpt-4o-mini")
    model_version = os.environ.get("GPR_MODEL_VERSION", model)
    base_url = os.environ.get("OPENAI_BASE_URL")
    group = os.environ.get("GPR_KAFKA_GROUP", "gpr-news-service")
    topic_in = os.environ.get("GPR_KAFKA_TOPIC_IN", DEFAULT_INPUT_TOPIC)
    topic_out = os.environ.get("GPR_KAFKA_TOPIC_OUT", DEFAULT_OUTPUT_TOPIC)
    gamma_dir = os.environ.get("GPR_GAMMA_REPORTS_DIR", "docs/reports")

    llm = openai_chat_client(model=model, base_url=base_url)
    config = ScorerConfig(model_version=model_version, training_cutoff=training_cutoff)
    publisher = confluent_publisher(bootstrap)

    # Engine tao MOT LAN cho ca vong doi tien trinh, KHONG tao lai trong handler.
    # Truoc ban va, process_news_item_live tu goi store.get_engine(dsn) o MOI
    # LAN GOI (tuc moi message Kafka) -> connection pool SQLAlchemy moi ma
    # khong bao gio dispose, ro ri connection duoi tai lien tuc thuc te (bug
    # tim thay khi audit production-readiness 2026-08-05). Tiem engine co san
    # qua tham so `engine=` de tai su dung dung 1 pool cho toan bo consumer.
    engine = store.get_engine(dsn)

    def handler(payload: dict) -> None:
        stmt = _statement_from_payload(payload)
        result = process_news_item_live(stmt, dsn, llm, config,
                                         gamma_reports_dir=gamma_dir, engine=engine)
        key = hashlib.sha256(stmt.text.encode("utf-8")).hexdigest()[:16]
        if isinstance(result, ExcludedResult):
            publisher.publish(topic_out, key, {
                "excluded": True, "reason": result.reason,
                "source": stmt.source, "published_at": stmt.published_at.isoformat()})
            return
        publisher.publish(topic_out, key, {"excluded": False, **result.as_dict()})

    print(f"[run_news_service] {topic_in} -> {topic_out} @ {bootstrap} (group={group})")
    run_consumer_loop(bootstrap, group, topic_in, handler)


if __name__ == "__main__":
    main()
