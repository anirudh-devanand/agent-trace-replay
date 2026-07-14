from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import (
    ReplayJob,
    ReplayJobStatus,
    ReplayManifest,
    ReplayStep,
    ReplayStepStatus,
)
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import REPLAY_REQUESTED_TOPIC
from shared.schemas.kafka_envelope import KafkaEventEnvelope
from shared.schemas.manifest import ReplayManifestDocument, ReplayManifestStep
from shared.schemas.replay import (
    FailureInjectionSpec,
    ReplayCreateRequest,
    ReplayCreateResponse,
    ReplayDetailResponse,
    ReplayListItem,
    ReplayListResponse,
    ReplayStepOut,
)


class ManifestMissingError(Exception):
    pass


class EmptyManifestError(Exception):
    pass


class ReplayNotFoundError(Exception):
    pass


class InvalidInjectionTargetError(Exception):
    pass


def _expected_result_from_step(step: ReplayManifestStep) -> dict:
    return {
        "event_type": step.event_type,
        "tool_name": step.tool_name,
        "service_name": step.service_name,
        "method": step.method,
        "path": step.path,
        "status_code": step.expected_status_code,
        "error_type": step.expected_error_type,
        "latency_ms": step.expected_latency_ms,
        "redacted_payload": step.redacted_payload,
    }


def resolve_injections(
    document: ReplayManifestDocument,
    request: ReplayCreateRequest,
) -> list[FailureInjectionSpec]:
    if not request.failure_injection:
        return []

    if request.injections:
        resolved = list(request.injections)
    else:
        first = document.steps[0]
        resolved = [
            FailureInjectionSpec(kind="timeout", step_id=first.step_id, step_order=1)
        ]

    known_ids = {step.step_id for step in document.steps}
    known_orders = {step.step_order for step in document.steps}
    for spec in resolved:
        if spec.step_id is not None and spec.step_id not in known_ids:
            raise InvalidInjectionTargetError(f"unknown step_id: {spec.step_id}")
        if spec.step_order is not None and spec.step_order not in known_orders:
            raise InvalidInjectionTargetError(f"unknown step_order: {spec.step_order}")
    return resolved


def _injection_for_step(
    step: ReplayManifestStep,
    injections: list[FailureInjectionSpec],
) -> dict | None:
    for spec in injections:
        if spec.step_id is not None and spec.step_id == step.step_id:
            payload = {"kind": spec.kind}
            if spec.delay_ms is not None:
                payload["delay_ms"] = spec.delay_ms
            return payload
        if spec.step_order is not None and spec.step_order == step.step_order:
            payload = {"kind": spec.kind}
            if spec.delay_ms is not None:
                payload["delay_ms"] = spec.delay_ms
            return payload
    return None


async def create_replay(
    session: AsyncSession,
    producer: KafkaEventProducer,
    request: ReplayCreateRequest,
) -> ReplayCreateResponse:
    manifest_row = await session.scalar(
        select(ReplayManifest).where(ReplayManifest.trace_id == request.trace_id)
    )
    if manifest_row is None:
        raise ManifestMissingError(request.trace_id)

    document = ReplayManifestDocument.model_validate(manifest_row.manifest_json)
    if document.step_count == 0 or not document.steps:
        raise EmptyManifestError(request.trace_id)

    injections = resolve_injections(document, request)

    replay_id = f"replay_{uuid4().hex[:12]}"
    job = ReplayJob(
        id=uuid4(),
        replay_id=replay_id,
        trace_id=request.trace_id,
        status=ReplayJobStatus.QUEUED.value,
        mode=request.mode,
        environment=request.environment,
        failure_injection=bool(injections) or request.failure_injection,
        summary_json={
            "injection_plan": [spec.model_dump(mode="json") for spec in injections],
        },
    )
    session.add(job)

    for step in document.steps:
        expected = _expected_result_from_step(step)
        injection = _injection_for_step(step, injections)
        if injection is not None:
            expected["injection"] = injection
        session.add(
            ReplayStep(
                id=uuid4(),
                replay_id=replay_id,
                step_id=step.step_id,
                step_order=step.step_order,
                status=ReplayStepStatus.PENDING.value,
                expected_result=expected,
                attempt_count=1,
            )
        )

    envelope = KafkaEventEnvelope(
        event_type=REPLAY_REQUESTED_TOPIC,
        trace_id=request.trace_id,
        replay_id=replay_id,
        idempotency_key=f"{replay_id}:requested",
        timestamp=datetime.now(timezone.utc),
        payload={
            "mode": request.mode,
            "environment": request.environment,
            "failure_injection": job.failure_injection,
            "step_count": document.step_count,
            "injections": [spec.model_dump(mode="json") for spec in injections],
        },
    )

    await session.commit()
    producer.publish(REPLAY_REQUESTED_TOPIC, envelope, partition_key=request.trace_id)
    producer.flush()

    return ReplayCreateResponse(
        replay_id=replay_id,
        trace_id=request.trace_id,
        status=ReplayJobStatus.QUEUED.value,
        step_count=document.step_count,
        mode=request.mode,
        failure_injection=job.failure_injection,
        injections=injections,
    )


async def get_replay_detail(session: AsyncSession, replay_id: str) -> ReplayDetailResponse:
    job = await session.scalar(select(ReplayJob).where(ReplayJob.replay_id == replay_id))
    if job is None:
        raise ReplayNotFoundError(replay_id)

    steps_result = await session.scalars(
        select(ReplayStep)
        .where(ReplayStep.replay_id == replay_id)
        .order_by(ReplayStep.step_order.asc(), ReplayStep.attempt_count.asc())
    )
    steps = [
        ReplayStepOut(
            step_id=step.step_id,
            step_order=step.step_order,
            status=step.status,
            expected_result=step.expected_result,
            actual_result=step.actual_result,
            latency_ms=step.latency_ms,
            attempt_count=step.attempt_count,
            error_message=step.error_message,
        )
        for step in steps_result.all()
    ]

    return ReplayDetailResponse(
        replay_id=job.replay_id,
        trace_id=job.trace_id,
        status=job.status,
        mode=job.mode,
        environment=job.environment,
        failure_injection=job.failure_injection,
        worker_id=job.worker_id,
        summary_json=job.summary_json,
        duration_ms=_duration_ms(job),
        first_failed_step_id=_first_failed_step_id(steps),
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        steps=steps,
    )


def _duration_ms(job: ReplayJob) -> int | None:
    if job.started_at is None or job.completed_at is None:
        if isinstance(job.summary_json, dict) and job.summary_json.get("duration_ms") is not None:
            return int(job.summary_json["duration_ms"])
        return None
    return max(int((job.completed_at - job.started_at).total_seconds() * 1000), 0)


def _first_failed_step_id(steps: list[ReplayStepOut]) -> str | None:
    for step in steps:
        if step.status == ReplayStepStatus.FAILED.value:
            return step.step_id
    return None


def _list_item_from_job(job: ReplayJob) -> ReplayListItem:
    summary = job.summary_json if isinstance(job.summary_json, dict) else {}
    return ReplayListItem(
        replay_id=job.replay_id,
        trace_id=job.trace_id,
        status=job.status,
        mode=job.mode,
        failure_injection=job.failure_injection,
        worker_id=job.worker_id,
        step_count=summary.get("step_count"),
        passed=summary.get("passed"),
        failed=summary.get("failed"),
        duration_ms=_duration_ms(job),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


async def list_replays(
    session: AsyncSession,
    *,
    trace_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
) -> ReplayListResponse:
    stmt = select(ReplayJob).order_by(ReplayJob.created_at.desc()).limit(limit)
    if trace_id:
        stmt = stmt.where(ReplayJob.trace_id == trace_id)
    if status_filter:
        stmt = stmt.where(ReplayJob.status == status_filter)

    jobs = list((await session.scalars(stmt)).all())
    items = [_list_item_from_job(job) for job in jobs]
    return ReplayListResponse(items=items, count=len(items))
