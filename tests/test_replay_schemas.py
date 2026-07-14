import pytest
from pydantic import ValidationError

from shared.schemas.replay import ReplayCreateRequest


def test_replay_create_request_defaults() -> None:
    request = ReplayCreateRequest.model_validate({"trace_id": "trace_abc"})
    assert request.trace_id == "trace_abc"
    assert request.mode == "deterministic"
    assert request.environment == "docker"
    assert request.failure_injection is False


def test_replay_create_rejects_empty_trace_id() -> None:
    with pytest.raises(ValidationError):
        ReplayCreateRequest.model_validate({"trace_id": ""})
