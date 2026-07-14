from shared.db.models import TraceEvent
from shared.schemas.manifest import (
    MANIFEST_VERSION,
    REPLAYABLE_EVENT_TYPES,
    ReplayManifestDocument,
    ReplayManifestStep,
)


def build_manifest(trace_id: str, events: list[TraceEvent]) -> ReplayManifestDocument:
    ordered_events = sorted(events, key=lambda event: (event.sequence, event.event_ts))
    steps: list[ReplayManifestStep] = []

    for event in ordered_events:
        if event.event_type not in REPLAYABLE_EVENT_TYPES:
            continue

        step_order = len(steps) + 1
        step_id = event.span_id or f"step_{event.sequence}"
        steps.append(
            ReplayManifestStep(
                step_id=step_id,
                step_order=step_order,
                span_id=event.span_id,
                parent_span_id=event.parent_span_id,
                sequence=event.sequence,
                event_type=event.event_type,
                tool_name=event.tool_name,
                service_name=event.service_name,
                method=event.method,
                path=event.path,
                expected_status_code=event.status_code,
                expected_error_type=event.error_type,
                expected_latency_ms=event.latency_ms,
                redacted_payload=event.redacted_payload,
                source_idempotency_key=event.idempotency_key,
            )
        )

    return ReplayManifestDocument(
        manifest_version=MANIFEST_VERSION,
        trace_id=trace_id,
        step_count=len(steps),
        steps=steps,
    )
