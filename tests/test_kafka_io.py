"""Test service.kafka_io — mock confluent_kafka.Producer (KHONG broker that).

Bug da vá: `produce()` bất đồng bộ, gọi xong không có nghĩa là đã gửi — thiếu
`on_delivery`/`flush()` thì lỗi broker hoặc message còn kẹt lúc tiến trình
thoát sẽ MẤT hoàn toàn, không dấu hiệu. Test này khóa hành vi vá: publish
phải raise rõ ràng khi flush không xong hoặc delivery báo lỗi.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gpr_engine.service.kafka_io import KafkaResultPublisher, confluent_publisher


def test_publish_calls_produce_and_flush_on_success():
    mock_producer = MagicMock()
    mock_producer.flush.return_value = 0  # 0 = da gui het, khong con kep
    with patch("confluent_kafka.Producer", return_value=mock_producer):
        pub = confluent_publisher("localhost:9092")
        assert isinstance(pub, KafkaResultPublisher)
        pub.publish("gpr.news.assessment", "key1", {"v": 0.5})
    mock_producer.produce.assert_called_once()
    mock_producer.flush.assert_called_once()


def test_publish_raises_when_flush_incomplete():
    """Message con ket trong hang doi (vd broker khong ket noi duoc) -> raise,
    khong duoc coi la thanh cong trong im lang."""
    mock_producer = MagicMock()
    mock_producer.flush.return_value = 1  # 1 message chua gui xong
    with patch("confluent_kafka.Producer", return_value=mock_producer):
        pub = confluent_publisher("localhost:9092", flush_timeout=1.0)
        with pytest.raises(RuntimeError, match="không xác nhận"):
            pub.publish("gpr.news.assessment", "key1", {"v": 0.5})


def test_publish_raises_on_delivery_error():
    """Broker tra loi trong on_delivery callback -> raise, khong nuot loi."""
    mock_producer = MagicMock()
    mock_producer.flush.return_value = 0

    def fake_produce(topic, key, value, on_delivery):
        on_delivery("Unknown topic or partition", None)

    mock_producer.produce.side_effect = fake_produce
    with patch("confluent_kafka.Producer", return_value=mock_producer):
        pub = confluent_publisher("localhost:9092")
        with pytest.raises(RuntimeError, match="thất bại"):
            pub.publish("gpr.news.assessment", "key1", {"v": 0.5})


def test_kafka_result_publisher_injectable_fake_needs_no_broker():
    """Pattern injection cho unit test khac (news_pipeline, run_news_service)
    — khong dung confluent_kafka that."""
    calls = []
    pub = KafkaResultPublisher(publish_fn=lambda t, k, v: calls.append((t, k, v)))
    pub.publish("topic", "key", {"a": 1})
    assert calls == [("topic", "key", {"a": 1})]


# --- run_consumer_loop: message hong -> dead-letter, khong mat im lang ---

def _fake_msg(value: bytes, offset: int = 7, key: bytes | None = b"k1"):
    m = MagicMock()
    m.error.return_value = None
    m.value.return_value = value
    m.key.return_value = key
    m.topic.return_value = "gpr.news.raw"
    m.partition.return_value = 0
    m.offset.return_value = offset
    return m


def _run_loop(msgs, handler, dead_letter):
    from gpr_engine.service.kafka_io import run_consumer_loop

    consumer = MagicMock()
    consumer.poll.side_effect = list(msgs)
    with patch("confluent_kafka.Consumer", return_value=consumer):
        run_consumer_loop("b:9092", "g", "gpr.news.raw", handler,
                          max_messages=len(msgs), dead_letter=dead_letter)
    return consumer


def test_failed_handler_goes_to_dead_letter_then_commits():
    """Bug da vá (pre-deploy 2026-10-30): ban cu commit trong `finally` sau khi
    chi print loi — handler/publish hong la message MAT HAN."""
    dead = []

    def handler(payload):
        raise ValueError("speaker_role la")

    consumer = _run_loop([_fake_msg(b'{"text": "x"}')], handler, dead.append)
    assert len(dead) == 1
    rec = dead[0]
    assert rec["value"] == '{"text": "x"}' and rec["offset"] == 7
    assert rec["key"] == "k1" and rec["error_type"] == "ValueError"
    consumer.commit.assert_called_once()   # khong retry vo han poison pill


def test_unparseable_payload_also_dead_lettered():
    dead = []
    _run_loop([_fake_msg(b"\xff not json")], lambda p: None, dead.append)
    assert dead and dead[0]["error_type"] in ("UnicodeDecodeError", "JSONDecodeError")


def test_dead_letter_failure_does_not_commit():
    def handler(payload):
        raise RuntimeError("boom")

    def broken_sink(record):
        raise OSError("disk full")

    from gpr_engine.service.kafka_io import run_consumer_loop

    consumer = MagicMock()
    consumer.poll.side_effect = [_fake_msg(b"{}")]
    with patch("confluent_kafka.Consumer", return_value=consumer):
        with pytest.raises(OSError):
            run_consumer_loop("b:9092", "g", "gpr.news.raw", handler,
                              max_messages=1, dead_letter=broken_sink)
    consumer.commit.assert_not_called()
    consumer.close.assert_called_once()


def test_successful_message_not_dead_lettered():
    dead, seen = [], []
    consumer = _run_loop([_fake_msg(b'{"a": 1}')], seen.append, dead.append)
    assert seen == [{"a": 1}] and dead == []
    consumer.commit.assert_called_once()


def test_dead_letter_sink_prefers_dlq_topic_then_file(tmp_path):
    from gpr_engine.service.kafka_io import DEFAULT_DLQ_TOPIC, dead_letter_sink

    sent = []
    ok = dead_letter_sink(KafkaResultPublisher(lambda t, k, v: sent.append((t, k, v))),
                          fallback_path=tmp_path / "dlq.jsonl")
    ok({"key": "k1", "value": "{}"})
    assert sent == [(DEFAULT_DLQ_TOPIC, "k1", {"key": "k1", "value": "{}"})]
    assert not (tmp_path / "dlq.jsonl").exists()

    def down(t, k, v):
        raise RuntimeError("broker down")

    path = tmp_path / "sub" / "dlq.jsonl"
    fb = dead_letter_sink(KafkaResultPublisher(down), fallback_path=path)
    fb({"key": "k2", "value": "{}"})
    import json
    assert json.loads(path.read_text(encoding="utf-8").strip())["key"] == "k2"
