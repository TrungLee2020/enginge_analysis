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

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

DEFAULT_INPUT_TOPIC = "gpr.news.raw"
DEFAULT_OUTPUT_TOPIC = "gpr.news.assessment"

PublishFn = Callable[[str, str, dict], None]   # (topic, key, value) -> None


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


def run_consumer_loop(
    bootstrap_servers: str,
    group_id: str,
    input_topic: str,
    handler: Callable[[dict], None],
    poll_timeout: float = 1.0,
    max_messages: int | None = None,
) -> None:
    """Vong lap consumer toi gian: doc JSON tu `input_topic`, goi `handler(payload)`.

    `handler` chiu trach nhiem parse payload thanh `Statement` + chay
    `process_news_item_live` + publish ket qua (xem `scripts/run_news_service.py`)
    — vong lap nay CHI lo I/O Kafka, khong biet gi ve GPR.

    Loi parse/handler cua MOT message duoc log va commit tiep (khong lam sap
    ca consumer vi mot message hong) — commit SAU khi xu ly xong (at-least-once,
    khop nguyen tac "sai la bao loi ro, khong am tham mat du lieu").
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
                print(f"[kafka_io] handler lỗi trên offset {msg.offset()}: {e}")
            finally:
                consumer.commit(msg)
                n += 1
    finally:
        consumer.close()
