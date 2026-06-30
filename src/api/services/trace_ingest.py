from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Trace, TraceEvent, TraceStatus
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import TRACE_INGESTED_TOPIC
from shared.schemas.kafka_envelope import KafkaEventEnvelope
from shared.schemas.trace import (
    TraceDetailResponse,
    TraceEventOut,
    TraceIngestRequest,
    TraceIngestResponse,
)


class TraceNotFoundError(Exception):
    pass


async def ingest_trace(
    session: AsyncSession,
    producer: KafkaEventProducer,
    request: TraceIngestRequest,
) -> TraceIngestResponse:
    event_timestamps = [event.event_ts for event in request.events]
    started_at = min(event_timestamps)
    ended_at = max(event_timestamps)

    trace_stmt = (
        insert(Trace)
        .values(
            id=uuid4(),
            trace_id=request.trace_id,
            agent_run_id=request.agent_run_id,
            source=request.source,
            status=TraceStatus.OPEN.value,
            started_at=started_at,
            ended_at=ended_at,
        )
        .on_conflict_do_update(
            index_elements=["trace_id"],
            set_={
                "agent_run_id": request.agent_run_id,
                "ended_at": ended_at,
            },
        )
    )
    await session.execute(trace_stmt)

    accepted = 0
    duplicates_ignored = 0

    for event in request.events:
        event_stmt = (
            insert(TraceEvent)
            .values(
                id=uuid4(),
                trace_id=request.trace_id,
                span_id=event.span_id,
                parent_span_id=event.parent_span_id,
                sequence=event.sequence,
                event_type=event.event_type,
                service_name=event.service_name,
                tool_name=event.tool_name,
                method=event.method,
                path=event.path,
                status_code=event.status_code,
                error_type=event.error_type,
                latency_ms=event.latency_ms,
                payload_hash=event.payload_hash,
                redacted_payload=event.redacted_payload,
                idempotency_key=event.idempotency_key,
                event_ts=event.event_ts,
            )
            .on_conflict_do_nothing(constraint="uq_trace_events_idempotency_key")
            .returning(TraceEvent.id)
        )
        result = await session.execute(event_stmt)
        if result.first() is not None:
            accepted += 1
        else:
            duplicates_ignored += 1

    batch_idempotency_key = f"{request.trace_id}:ingest:batch:{uuid4()}"
    envelope = KafkaEventEnvelope(
        event_type=TRACE_INGESTED_TOPIC,
        trace_id=request.trace_id,
        idempotency_key=batch_idempotency_key,
        timestamp=datetime.now(timezone.utc),
        payload={
            "accepted": accepted,
            "duplicates_ignored": duplicates_ignored,
            "source": request.source,
            "agent_run_id": request.agent_run_id,
        },
    )

    await session.commit()
    producer.publish(TRACE_INGESTED_TOPIC, envelope, partition_key=request.trace_id)
    producer.flush()

    return TraceIngestResponse(
        trace_id=request.trace_id,
        accepted=accepted,
        duplicates_ignored=duplicates_ignored,
    )


async def get_trace_detail(session: AsyncSession, trace_id: str) -> TraceDetailResponse:
    trace = await session.scalar(select(Trace).where(Trace.trace_id == trace_id))
    if trace is None:
        raise TraceNotFoundError(trace_id)

    events_result = await session.scalars(
        select(TraceEvent)
        .where(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.sequence.asc(), TraceEvent.event_ts.asc())
    )
    events = [
        TraceEventOut(
            span_id=event.span_id,
            parent_span_id=event.parent_span_id,
            sequence=event.sequence,
            event_type=event.event_type,
            service_name=event.service_name,
            tool_name=event.tool_name,
            method=event.method,
            path=event.path,
            status_code=event.status_code,
            error_type=event.error_type,
            latency_ms=event.latency_ms,
            payload_hash=event.payload_hash,
            redacted_payload=event.redacted_payload,
            idempotency_key=event.idempotency_key,
            event_ts=event.event_ts,
        )
        for event in events_result.all()
    ]

    return TraceDetailResponse(
        trace_id=trace.trace_id,
        agent_run_id=trace.agent_run_id,
        source=trace.source,
        status=trace.status,
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        created_at=trace.created_at,
        events=events,
    )
