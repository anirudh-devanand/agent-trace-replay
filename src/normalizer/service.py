import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from normalizer.manifest_builder import build_manifest
from shared.db.models import ReplayManifest, TraceEvent
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import TRACE_NORMALIZED_TOPIC
from shared.schemas.kafka_envelope import KafkaEventEnvelope
from shared.schemas.manifest import MANIFEST_VERSION, ReplayManifestDocument

logger = logging.getLogger(__name__)


class TraceEventsNotFoundError(Exception):
    pass


async def load_trace_events(session: AsyncSession, trace_id: str) -> list[TraceEvent]:
    events_result = await session.scalars(
        select(TraceEvent)
        .where(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.sequence.asc(), TraceEvent.event_ts.asc())
    )
    return list(events_result.all())


async def normalize_trace(
    session: AsyncSession,
    producer: KafkaEventProducer,
    trace_id: str,
) -> ReplayManifestDocument:
    events = await load_trace_events(session, trace_id)
    if not events:
        raise TraceEventsNotFoundError(trace_id)

    manifest = build_manifest(trace_id, events)
    manifest_json = manifest.model_dump(mode="json")

    manifest_stmt = (
        insert(ReplayManifest)
        .values(
            id=uuid4(),
            trace_id=trace_id,
            manifest_version=MANIFEST_VERSION,
            manifest_json=manifest_json,
        )
        .on_conflict_do_update(
            index_elements=["trace_id"],
            set_={
                "manifest_version": MANIFEST_VERSION,
                "manifest_json": manifest_json,
            },
        )
    )
    await session.execute(manifest_stmt)

    envelope = KafkaEventEnvelope(
        event_type=TRACE_NORMALIZED_TOPIC,
        trace_id=trace_id,
        idempotency_key=f"{trace_id}:normalized:{MANIFEST_VERSION}:{manifest.step_count}",
        timestamp=datetime.now(timezone.utc),
        payload={
            "manifest_version": MANIFEST_VERSION,
            "step_count": manifest.step_count,
        },
    )

    await session.commit()
    producer.publish(TRACE_NORMALIZED_TOPIC, envelope, partition_key=trace_id)
    producer.flush()

    logger.info(
        "normalized trace_id=%s step_count=%s",
        trace_id,
        manifest.step_count,
    )
    return manifest
