import pytest
from pydantic import ValidationError

from shared.schemas.trace import MAX_INGEST_BATCH_SIZE, TraceIngestRequest


def test_ingest_request_valid() -> None:
    payload = {
        "trace_id": "trace_abc",
        "source": "api",
        "events": [
            {
                "sequence": 1,
                "event_type": "tool_call",
                "tool_name": "lookup",
                "idempotency_key": "trace_abc:span_1:tool_call",
                "event_ts": "2026-05-01T12:00:00Z",
            }
        ],
    }
    request = TraceIngestRequest.model_validate(payload)
    assert request.trace_id == "trace_abc"
    assert len(request.events) == 1


def test_ingest_rejects_invalid_event_type() -> None:
    payload = {
        "trace_id": "trace_abc",
        "source": "api",
        "events": [
            {
                "sequence": 1,
                "event_type": "invalid_type",
                "idempotency_key": "k1",
                "event_ts": "2026-05-01T12:00:00Z",
            }
        ],
    }
    with pytest.raises(ValidationError):
        TraceIngestRequest.model_validate(payload)


def test_ingest_rejects_oversized_batch() -> None:
    events = [
        {
            "sequence": i,
            "event_type": "tool_call",
            "idempotency_key": f"k{i}",
            "event_ts": "2026-05-01T12:00:00Z",
        }
        for i in range(1, MAX_INGEST_BATCH_SIZE + 2)
    ]
    with pytest.raises(ValidationError):
        TraceIngestRequest.model_validate(
            {"trace_id": "trace_abc", "source": "api", "events": events}
        )
