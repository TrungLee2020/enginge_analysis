"""kafka_io.py — Kafka producer/consumer cho pipeline production (docs/00 §0:
"SERVING: gpr-api + Kafka → BeaverX agents").

🏭 production-path. `confluent-kafka` (requirements.txt) — import LAZY nen
module nay import duoc ngay ca khi package chua cai (test dung fake, khong
can broker that — khong co broker song trong sandbox nay, xem ke hoach da
duyet "Ngoai pham vi V1").

`KafkaResultPublisher` boc mot callable `publish_fn` — cung pattern injection
voi `LLMClient` trong statement_scorer.py: production dung `confluent_producer`,
test tiem list/callable de kiem tra khong can broker.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INPUT_TOPIC = "gpr.news.raw"
DEFAULT_OUTPUT_TOPIC = "gpr.news.assessment"
DEFAULT_DLQ_TOPIC = "gpr.news.raw.dlq"

PublishFn = Callable[[str, str, dict], None]   # (topic, key, value) -> None
DeadLetterFn = Callable[[dict], None]          # ban ghi dead-letter -> None

log = logging.getLogger(__name__)


def _json_default(obj):
    """Serialize gia tri khong phai JSON-native (Timestamp, datetime, dataclass...)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


@dataclass
class KafkaResultPublisher:
    """Publish MOT ket qua JSON len topic. `publish_fn` tiem vao — xem module docstring."""
    publish_fn: PublishFn

    def publish(self, topic: str, key: str, value: Mapping) -> None:
        self.publish_fn(topic, key, dict(value))


def confluent_publisher(bootstrap_servers: str, flush_timeout: float = 10.0,
                        **producer_config) -> KafkaResultPublisher:
    """`KafkaResultPublisher` that, dung `confluent_kafka.Producer`.

    Import `confluent_kafka` LAZY — chi can khi thuc su goi ham nay (production
    entrypoint `scripts/run_news_service.py`), khong ep test/import khac phai
    co package.

    `produce()` cua confluent-kafka la BAT DONG BO — goi xong khong co nghia
    la da gui: neu khong dang ky `on_delivery` va khong `flush()`, mot loi
    broker/topic (hoac ca tien trinh thoat truoc khi hang doi noi bo day het)
    se lam MAT message MA KHONG CO DAU HIEU nao — im lang tuyet doi, khong
    exception, khong log. `run_consumer_loop` xu ly TUNG message mot (khong
    batch) nen doi `flush()` moi lan la dung: doi lay xac nhan GUI THAT truoc
    khi tra ve, raise ro rang neu khong gui duoc — dung tinh than "sai la bao
    loi ro" da ap dung cho cac phan khac cua pipeline nay.
    """
    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": bootstrap_servers, **producer_config})

    def _publish(topic: str, key: str, value: dict) -> None:
        delivery_errors: list[str] = []

        def _on_delivery(err, msg):
            if err is not None:
                delivery_errors.append(str(err))

        producer.produce(topic, key=key.encode("utf-8"),
                         value=json.dumps(value, default=_json_default,
                                          ensure_ascii=False).encode("utf-8"),
                         on_delivery=_on_delivery)
        remaining = producer.flush(flush_timeout)
        if remaining > 0:
            raise RuntimeError(
                f"Kafka publish tới topic {topic!r} không xác nhận được trong "
                f"{flush_timeout}s ({remaining} message còn kẹt trong hàng đợi "
                "nội bộ) — không rõ đã gửi hay chưa, không được coi là thành công.")
        if delivery_errors:
            raise RuntimeError(
                f"Kafka publish tới topic {topic!r} thất bại: {delivery_errors[0]}")

    return KafkaResultPublisher(_publish)


def dead_letter_record(msg, error: BaseException) -> dict:
    """Ban ghi dead-letter cho MOT message xu ly hong — du de phat lai sau.

    `value` giu NGUYEN VAN (decode utf-8, ky tu hong thay bang U+FFFD chu
    khong raise — ban ghi nay khong duoc phep hong vi chinh payload hong).
    """
    raw_key, raw_value = msg.key(), msg.value()
    return {
        "topic": msg.topic(), "partition": msg.partition(), "offset": msg.offset(),
        "key": raw_key.decode("utf-8", "replace") if raw_key is not None else None,
        "value": raw_value.decode("utf-8", "replace") if raw_value is not None else None,
        "error_type": type(error).__name__, "error": str(error),
        "failed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def dead_letter_sink(publisher: KafkaResultPublisher | None,
                     dlq_topic: str = DEFAULT_DLQ_TOPIC,
                     fallback_path: str | Path | None = None) -> DeadLetterFn:
    """Noi luu message hong: topic DLQ truoc, ghi JSONL vao `fallback_path`
    neu publish DLQ khong duoc. Ca hai deu hong -> raise (caller KHONG commit
    offset — mat du lieu im lang con te hon dung consumer)."""
    def _sink(record: dict) -> None:
        dlq_error: Exception | None = None
        if publisher is not None:
            try:
                publisher.publish(dlq_topic, record.get("key") or "", record)
                return
            except Exception as e:  # noqa: BLE001 — roi xuong file
                dlq_error = e
                log.error("[kafka_io] DLQ publish to %s failed: %s", dlq_topic, e)
        if fallback_path is None:
            raise RuntimeError(f"Không lưu được dead-letter (DLQ: {dlq_error}) "
                               "và không có fallback_path.")
        path = Path(fallback_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=_json_default, ensure_ascii=False) + "\n")
    return _sink


def run_consumer_loop(
    bootstrap_servers: str,
    group_id: str,
    input_topic: str,
    handler: Callable[[dict], None],
    poll_timeout: float = 1.0,
    max_messages: int | None = None,
    dead_letter: DeadLetterFn | None = None,
) -> None:
    """Vong lap consumer toi gian: doc JSON tu `input_topic`, goi `handler(payload)`.

    `handler` chiu trach nhiem parse payload thanh `Statement` + chay
    `process_news_item_live` + publish ket qua (xem `scripts/run_news_service.py`)
    — vong lap nay CHI lo I/O Kafka, khong biet gi ve GPR.

    Loi parse/handler cua MOT message: log ERROR (topic/partition/offset/key),
    dua ban ghi nguyen van vao `dead_letter`, ROI moi commit — khong lam sap
    ca consumer vi mot message hong, va khong retry vo han mot poison pill.
    Bug da vá (pre-deploy 2026-10-30): ban cu chi `print` roi commit trong
    `finally` — handler/publish hong la message MAT HAN, khong dau vet ngoai
    mot dong stdout. Neu chinh `dead_letter` raise thi KHONG commit va de
    exception thoat ra (dung consumer; restart doc lai tu offset chua commit).
    `dead_letter=None`: giu hanh vi cu (log + commit) nhung log kem payload.
    Luu y: handler hong SAU khi da ghi DB (vd publish ket qua loi) thi phat
    lai tu DLQ se ghi statement lan nua — chap nhan, phat lai la thao tac tay.
    `max_messages`: gioi han so message xu ly — dung cho test/manual run co dinh,
    None = chay mai (production).
    """
    from confluent_kafka import Consumer

    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([input_topic])
    n = 0
    try:
        while max_messages is None or n < max_messages:
            msg = consumer.poll(poll_timeout)
            if msg is None:
                continue
            if msg.error():
                print(f"[kafka_io] consumer error: {msg.error()}")
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
                handler(payload)
            except Exception as e:  # noqa: BLE001 — 1 message hong khong duoc lam sap loop
                record = dead_letter_record(msg, e)
                log.error("[kafka_io] handler failed topic=%s partition=%s offset=%s "
                          "key=%s: %s: %s", record["topic"], record["partition"],
                          record["offset"], record["key"], record["error_type"], e)
                if dead_letter is None:
                    log.error("[kafka_io] no dead-letter sink, payload dropped: %s",
                              record["value"])
                else:
                    dead_letter(record)   # raise -> khong commit, thoat loop
            consumer.commit(msg)
            n += 1
    finally:
        consumer.close()
