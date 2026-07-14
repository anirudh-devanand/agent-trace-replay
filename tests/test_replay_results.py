from datetime import datetime, timezone

from shared.db.models import ReplayJob, ReplayJobStatus, ReplayStepStatus
from shared.schemas.replay import ReplayStepOut
from api.services.replay_schedule import _duration_ms, _first_failed_step_id, _list_item_from_job


def test_duration_ms_from_timestamps() -> None:
    job = ReplayJob(
        replay_id="replay_x",
        trace_id="trace_x",
        status=ReplayJobStatus.COMPLETED.value,
        mode="deterministic",
        environment="docker",
        failure_injection=False,
        started_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 1, 12, 0, 1, 500000, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert _duration_ms(job) == 1500


def test_first_failed_step_id() -> None:
    steps = [
        ReplayStepOut(step_id="a", step_order=1, status=ReplayStepStatus.PASSED.value, attempt_count=1),
        ReplayStepOut(step_id="b", step_order=2, status=ReplayStepStatus.FAILED.value, attempt_count=1),
    ]
    assert _first_failed_step_id(steps) == "b"


def test_list_item_reads_summary() -> None:
    job = ReplayJob(
        replay_id="replay_y",
        trace_id="trace_y",
        status=ReplayJobStatus.FAILED.value,
        mode="deterministic",
        environment="docker",
        failure_injection=True,
        summary_json={"step_count": 2, "passed": 0, "failed": 2, "duration_ms": 120},
        created_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    item = _list_item_from_job(job)
    assert item.step_count == 2
    assert item.failed == 2
    assert item.duration_ms == 120
