from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_EVENT_TYPES = frozenset({"http_request", "tool_call", "retry", "timeout"})
MAX_INGEST_BATCH_SIZE = 500


class TraceEventIn(BaseModel):
    span_id: str | None = None
    parent_span_id: str | None = None
    sequence: int = Field(ge=1)
    event_type: str
    service_name: str | None = None
    tool_name: str | None = None
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    error_type: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    payload_hash: str | None = None
    redacted_payload: dict[str, Any] | None = None
    idempotency_key: str = Field(min_length=1, max_length=512)
    event_ts: datetime

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value not in ALLOWED_EVENT_TYPES:
            allowed = ", ".join(sorted(ALLOWED_EVENT_TYPES))
            raise ValueError(f"event_type must be one of: {allowed}")
        return value


class TraceIngestRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=256)
    agent_run_id: str | None = Field(default=None, max_length=256)
    source: str = Field(min_length=1, max_length=64)
    events: list[TraceEventIn] = Field(min_length=1)

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, value: list[TraceEventIn]) -> list[TraceEventIn]:
        if len(value) > MAX_INGEST_BATCH_SIZE:
            raise ValueError(f"events batch exceeds max size of {MAX_INGEST_BATCH_SIZE}")
        return value


class TraceIngestResponse(BaseModel):
    trace_id: str
    accepted: int
    duplicates_ignored: int
    status: Literal["accepted"] = "accepted"


class TraceEventOut(BaseModel):
    span_id: str | None
    parent_span_id: str | None
    sequence: int
    event_type: str
    service_name: str | None
    tool_name: str | None
    method: str | None
    path: str | None
    status_code: int | None
    error_type: str | None
    latency_ms: int | None
    payload_hash: str | None
    redacted_payload: dict[str, Any] | None
    idempotency_key: str
    event_ts: datetime


class TraceDetailResponse(BaseModel):
    trace_id: str
    agent_run_id: str | None
    source: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    events: list[TraceEventOut]
