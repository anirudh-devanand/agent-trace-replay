import json
from typing import Any

from confluent_kafka import Producer

from shared.config import Settings
from shared.schemas.kafka_envelope import KafkaEventEnvelope


class KafkaEventProducer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._delivery_errors: list[str] = []
        self._producer = Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "acks": "all",
                "enable.idempotence": True,
                "retries": 5,
            }
        )

    def publish(self, topic: str, envelope: KafkaEventEnvelope, partition_key: str) -> None:
        payload = envelope.model_dump(mode="json")
        value = json.dumps(payload).encode("utf-8")
        self._producer.produce(
            topic=topic,
            key=partition_key.encode("utf-8"),
            value=value,
            on_delivery=self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            raise RuntimeError(f"kafka producer flush timed out with {remaining} messages pending")
        if self._delivery_errors:
            errors = "; ".join(self._delivery_errors)
            self._delivery_errors.clear()
            raise RuntimeError(f"kafka delivery failed: {errors}")

    def _delivery_callback(self, err: Any, msg: Any) -> None:
        if err is not None:
            self._delivery_errors.append(str(err))
