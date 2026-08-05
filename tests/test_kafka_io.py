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
