import json
from typing import Any

from confluent_kafka import Consumer, KafkaError, Message

from shared.config import Settings
from shared.schemas.kafka_envelope import KafkaEventEnvelope

# Recoverable while brokers auto-create topics on first produce.
_RETRYABLE_CONSUMER_ERRORS = frozenset(
    {
        KafkaError.UNKNOWN_TOPIC_OR_PART,
        KafkaError._PARTITION_EOF,
    }
)


class KafkaEventConsumer:
    def __init__(self, settings: Settings, group_id: str, topics: list[str]) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "allow.auto.create.topics": True,
            }
        )
        self._consumer.subscribe(topics)

    def poll(self, timeout: float = 1.0) -> Message | None:
        message = self._consumer.poll(timeout)
        if message is None:
            return None
        if message.error():
            error = message.error()
            if error.code() in _RETRYABLE_CONSUMER_ERRORS:
                return None
            raise RuntimeError(f"kafka consumer error: {error}")
        return message

    def commit(self, message: Message) -> None:
        self._consumer.commit(message=message, asynchronous=False)

    def close(self) -> None:
        self._consumer.close()


def parse_envelope(message: Message) -> KafkaEventEnvelope:
    raw_value = message.value()
    if raw_value is None:
        raise ValueError("kafka message has no value")
    payload: dict[str, Any] = json.loads(raw_value.decode("utf-8"))
    return KafkaEventEnvelope.model_validate(payload)
