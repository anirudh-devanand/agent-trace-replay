from datetime import datetime, timezone
from uuid import uuid4

from normalizer.manifest_builder import build_manifest
from shared.db.models import TraceEvent


def _make_event(**overrides: object) -> TraceEvent:
    values: dict[str, object] = {
        "id": uuid4(),
        "trace_id": "trace_test",
        "span_id": "span_1",
        "parent_span_id": None,
        "sequence": 1,
        "event_type": "tool_call",
        "service_name": None,
        "tool_name": "lookup",
        "method": None,
        "path": None,
        "status_code": 200,
        "error_type": None,
        "latency_ms": 50,
        "payload_hash": None,
        "redacted_payload": {"key": "value"},
        "idempotency_key": "trace_test:span_1:tool_call",
        "event_ts": datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return TraceEvent(**values)


def test_build_manifest_orders_steps_by_sequence() -> None:
    events = [
        _make_event(sequence=2, span_id="span_2", tool_name="order_lookup", idempotency_key="k2"),
        _make_event(sequence=1, span_id="span_1", tool_name="customer_lookup", idempotency_key="k1"),
    ]

    manifest = build_manifest("trace_test", events)

    assert manifest.trace_id == "trace_test"
    assert manifest.step_count == 2
    assert manifest.steps[0].tool_name == "customer_lookup"
    assert manifest.steps[1].tool_name == "order_lookup"
    assert manifest.steps[0].step_order == 1
    assert manifest.steps[1].step_order == 2


def test_build_manifest_skips_non_replayable_events() -> None:
    events = [
        _make_event(sequence=1, event_type="tool_call"),
        _make_event(
            sequence=2,
            span_id="span_meta",
            event_type="metadata",
            tool_name=None,
            idempotency_key="meta",
        ),
    ]

    manifest = build_manifest("trace_test", events)

    assert manifest.step_count == 1
    assert manifest.steps[0].sequence == 1


def test_build_manifest_uses_sequence_fallback_step_id() -> None:
    event = _make_event(span_id=None, sequence=3, idempotency_key="k3")

    manifest = build_manifest("trace_test", [event])

    assert manifest.steps[0].step_id == "step_3"
