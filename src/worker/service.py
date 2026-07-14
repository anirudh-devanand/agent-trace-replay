import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ReplayJob, ReplayJobStatus, ReplayStep, ReplayStepStatus
from shared.kafka.producer import KafkaEventProducer
from shared.kafka.topics import REPLAY_PROGRESS_TOPIC
from shared.schemas.kafka_envelope import KafkaEventEnvelope
from worker.metrics import (
    REPLAY_INJECTIONS_TOTAL,
    REPLAY_JOB_DURATION_SECONDS,
    REPLAY_JOBS_TOTAL,
    REPLAY_STEP_LATENCY_MS,
    REPLAY_STEPS_TOTAL,
)
from worker.step_executor import execute_mock_step

logger = logging.getLogger(__name__)


class ReplayJobNotFoundError(Exception):
    pass


class ReplayJobNotClaimableError(Exception):
    pass


async def claim_replay_job(
    session: AsyncSession,
    replay_id: str,
    worker_id: str,
) -> ReplayJob:
    job = await session.scalar(
        select(ReplayJob)
        .where(ReplayJob.replay_id == replay_id)
        .with_for_update()
    )
    if job is None:
        raise ReplayJobNotFoundError(replay_id)
    if job.status != ReplayJobStatus.QUEUED.value:
        raise ReplayJobNotClaimableError(f"{replay_id}:{job.status}")

    job.status = ReplayJobStatus.RUNNING.value
    job.worker_id = worker_id
    job.started_at = datetime.now(timezone.utc)
    await session.commit()
    return job


async def run_replay(
    session: AsyncSession,
    producer: KafkaEventProducer,
    replay_id: str,
    worker_id: str,
) -> dict:
    try:
        job = await claim_replay_job(session, replay_id, worker_id)
    except ReplayJobNotClaimableError:
        logger.info("skipping replay_id=%s (already claimed or finished)", replay_id)
        return {"skipped": True, "replay_id": replay_id}

    steps_result = await session.scalars(
        select(ReplayStep)
        .where(ReplayStep.replay_id == replay_id)
        .order_by(ReplayStep.step_order.asc())
    )
    steps = list(steps_result.all())
    injection_plan = []
    if isinstance(job.summary_json, dict):
        injection_plan = job.summary_json.get("injection_plan") or []

    passed = 0
    failed = 0

    for step in steps:
        step.status = ReplayStepStatus.RUNNING.value
        await session.commit()

        execution = await execute_mock_step(
            step.expected_result,
            failure_injection=job.failure_injection,
        )
        step.status = (
            ReplayStepStatus.PASSED.value
            if execution.status == "passed"
            else ReplayStepStatus.FAILED.value
        )
        step.actual_result = execution.actual_result
        step.latency_ms = execution.latency_ms
        step.error_message = execution.error_message
        await session.commit()

        if execution.status == "passed":
            passed += 1
        else:
            failed += 1

        REPLAY_STEPS_TOTAL.labels(status=step.status).inc()
        if execution.latency_ms is not None:
            REPLAY_STEP_LATENCY_MS.observe(execution.latency_ms)
        injection = (step.expected_result or {}).get("injection") if job.failure_injection else None
        if isinstance(injection, dict) and injection.get("kind"):
            REPLAY_INJECTIONS_TOTAL.labels(kind=str(injection["kind"])).inc()

        progress = KafkaEventEnvelope(
            event_type=REPLAY_PROGRESS_TOPIC,
            trace_id=job.trace_id,
            replay_id=replay_id,
            idempotency_key=f"{replay_id}:{step.step_id}:{step.attempt_count}:progress",
            timestamp=datetime.now(timezone.utc),
            payload={
                "step_id": step.step_id,
                "step_order": step.step_order,
                "status": step.status,
                "passed": passed,
                "failed": failed,
                "failure_injection": job.failure_injection,
            },
        )
        producer.publish(REPLAY_PROGRESS_TOPIC, progress, partition_key=job.trace_id)

    completed_at = datetime.now(timezone.utc)
    started_at = job.started_at or completed_at
    duration_ms = max(int((completed_at - started_at).total_seconds() * 1000), 0)

    summary = {
        "step_count": len(steps),
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "failure_injection": job.failure_injection,
        "injection_plan": injection_plan,
        "duration_ms": duration_ms,
    }
    final_status = (
        ReplayJobStatus.COMPLETED.value if failed == 0 else ReplayJobStatus.FAILED.value
    )

    job.status = final_status
    job.summary_json = summary
    job.completed_at = completed_at
    await session.commit()
    producer.flush()

    REPLAY_JOBS_TOTAL.labels(status=final_status).inc()
    REPLAY_JOB_DURATION_SECONDS.observe(max(duration_ms / 1000.0, 0.0))

    logger.info(
        "finished replay_id=%s status=%s passed=%s failed=%s duration_ms=%s",
        replay_id,
        final_status,
        passed,
        failed,
        duration_ms,
    )
    return {"skipped": False, "replay_id": replay_id, "status": final_status, **summary}
