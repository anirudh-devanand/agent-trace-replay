from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

MANIFEST_VERSION = "v1"
REPLAYABLE_EVENT_TYPES = frozenset({"tool_call", "http_request", "retry", "timeout"})


class ReplayManifestStep(BaseModel):
    step_id: str
    step_order: int = Field(ge=1)
    span_id: str | None = None
    parent_span_id: str | None = None
    sequence: int = Field(ge=1)
    event_type: str
    tool_name: str | None = None
    service_name: str | None = None
    method: str | None = None
    path: str | None = None
    expected_status_code: int | None = None
    expected_error_type: str | None = None
    expected_latency_ms: int | None = Field(default=None, ge=0)
    redacted_payload: dict[str, Any] | None = None
    source_idempotency_key: str


class ReplayManifestDocument(BaseModel):
    manifest_version: str = MANIFEST_VERSION
    trace_id: str
    step_count: int = Field(ge=0)
    steps: list[ReplayManifestStep]


class ManifestDetailResponse(BaseModel):
    trace_id: str
    manifest_version: str
    manifest_json: dict[str, Any]
    created_at: datetime
