import asyncio
import logging

from prometheus_client import Counter

from normalizer.service import TraceEventsNotFoundError, normalize_trace
from shared.config import get_settings
from shared.db.session import async_session_factory
from shared.kafka.consumer import KafkaEventConsumer, parse_envelope
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import TRACE_INGESTED_TOPIC

logger = logging.getLogger(__name__)

NORMALIZER_MESSAGES_TOTAL = Counter(
    "normalizer_messages_total",
    "Normalizer Kafka messages processed",
    ["status"],
)
NORMALIZER_MANIFESTS_TOTAL = Counter(
    "normalizer_manifests_total",
    "Replay manifests compiled by the normalizer",
)
NORMALIZER_MANIFEST_STEPS_TOTAL = Counter(
    "normalizer_manifest_steps_total",
    "Total steps written into compiled manifests",
)


async def handle_message(
    producer: KafkaEventProducer,
    trace_id: str,
) -> None:
    async with async_session_factory() as session:
        manifest = await normalize_trace(session, producer, trace_id)
        NORMALIZER_MANIFESTS_TOTAL.inc()
        NORMALIZER_MANIFEST_STEPS_TOTAL.inc(manifest.step_count)


async def run_consumer_loop() -> None:
    settings = get_settings()
    producer = KafkaEventProducer(settings)
    consumer = KafkaEventConsumer(
        settings,
        group_id=settings.normalizer_consumer_group,
        topics=[TRACE_INGESTED_TOPIC],
    )
    loop = asyncio.get_running_loop()

    logger.info("normalizer listening on topic=%s", TRACE_INGESTED_TOPIC)

    try:
        while True:
            message = await loop.run_in_executor(None, consumer.poll, 1.0)
            if message is None:
                continue

            try:
                envelope = parse_envelope(message)
                await handle_message(producer, envelope.trace_id)
                consumer.commit(message)
                NORMALIZER_MESSAGES_TOTAL.labels(status="success").inc()
            except TraceEventsNotFoundError:
                logger.warning("trace events not ready, will retry")
                NORMALIZER_MESSAGES_TOTAL.labels(status="retry").inc()
            except Exception:
                logger.exception("failed to normalize kafka message")
                NORMALIZER_MESSAGES_TOTAL.labels(status="error").inc()
    finally:
        consumer.close()
        producer.flush()
