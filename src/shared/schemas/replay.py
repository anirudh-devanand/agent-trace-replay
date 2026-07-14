from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

FailureInjectionKind = Literal["timeout", "http_500", "malformed_json", "slow"]


class FailureInjectionSpec(BaseModel):
    kind: FailureInjectionKind
    step_id: str | None = Field(default=None, max_length=256)
    step_order: int | None = Field(default=None, ge=1)
    delay_ms: int | None = Field(
        default=None,
        ge=1,
        le=60_000,
        description="Override delay for timeout/slow injections",
    )

    @model_validator(mode="after")
    def require_step_target(self) -> "FailureInjectionSpec":
        if self.step_id is None and self.step_order is None:
            raise ValueError("either step_id or step_order is required")
        return self


class ReplayCreateRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=256)
    mode: Literal["deterministic"] = "deterministic"
    environment: str = Field(default="docker", min_length=1, max_length=64)
    failure_injection: bool = False
    injections: list[FailureInjectionSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_injection_flag(self) -> "ReplayCreateRequest":
        if self.injections and not self.failure_injection:
            self.failure_injection = True
        return self


class ReplayCreateResponse(BaseModel):
    replay_id: str
    trace_id: str
    status: str
    step_count: int
    mode: str
    failure_injection: bool
    injections: list[FailureInjectionSpec] = Field(default_factory=list)


class ReplayStepOut(BaseModel):
    step_id: str
    step_order: int
    status: str
    expected_result: dict[str, Any] | None = None
    actual_result: dict[str, Any] | None = None
    latency_ms: int | None = None
    attempt_count: int
    error_message: str | None = None


class ReplayListItem(BaseModel):
    replay_id: str
    trace_id: str
    status: str
    mode: str
    failure_injection: bool
    worker_id: str | None
    step_count: int | None = None
    passed: int | None = None
    failed: int | None = None
    duration_ms: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ReplayListResponse(BaseModel):
    items: list[ReplayListItem]
    count: int


class ReplayDetailResponse(BaseModel):
    replay_id: str
    trace_id: str
    status: str
    mode: str
    environment: str
    failure_injection: bool
    worker_id: str | None
    summary_json: dict[str, Any] | None
    duration_ms: int | None = None
    first_failed_step_id: str | None = None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    steps: list[ReplayStepOut]
