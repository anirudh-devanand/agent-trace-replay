import asyncio
import logging

from prometheus_client import Counter

from shared.config import get_settings
from shared.db.session import async_session_factory
from shared.kafka.consumer import KafkaEventConsumer, parse_envelope
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import REPLAY_REQUESTED_TOPIC
from worker.service import ReplayJobNotFoundError, run_replay

logger = logging.getLogger(__name__)

REPLAY_WORKER_MESSAGES_TOTAL = Counter(
    "replay_worker_messages_total",
    "Replay worker Kafka messages processed",
    ["status"],
)


async def handle_message(producer: KafkaEventProducer, replay_id: str, worker_id: str) -> None:
    async with async_session_factory() as session:
        await run_replay(session, producer, replay_id, worker_id)


async def run_consumer_loop() -> None:
    settings = get_settings()
    producer = KafkaEventProducer(settings)
    consumer = KafkaEventConsumer(
        settings,
        group_id=settings.worker_consumer_group,
        topics=[REPLAY_REQUESTED_TOPIC],
    )
    loop = asyncio.get_running_loop()

    logger.info("replay worker listening on topic=%s", REPLAY_REQUESTED_TOPIC)

    try:
        while True:
            message = await loop.run_in_executor(None, consumer.poll, 1.0)
            if message is None:
                continue

            try:
                envelope = parse_envelope(message)
                if not envelope.replay_id:
                    raise ValueError("replay.requested message missing replay_id")
                await handle_message(producer, envelope.replay_id, settings.worker_id)
                consumer.commit(message)
                REPLAY_WORKER_MESSAGES_TOTAL.labels(status="success").inc()
            except ReplayJobNotFoundError:
                logger.warning("replay job not found, committing offset")
                consumer.commit(message)
                REPLAY_WORKER_MESSAGES_TOTAL.labels(status="missing").inc()
            except Exception:
                logger.exception("failed to process replay request")
                REPLAY_WORKER_MESSAGES_TOTAL.labels(status="error").inc()
    finally:
        consumer.close()
        producer.flush()
