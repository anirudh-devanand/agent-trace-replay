import pytest
from pydantic import ValidationError

from shared.schemas.replay import FailureInjectionSpec, ReplayCreateRequest
from worker.step_executor import execute_mock_step


@pytest.mark.asyncio
async def test_execute_mock_step_returns_recorded_outcome() -> None:
    expected = {
        "event_type": "tool_call",
        "tool_name": "customer_lookup",
        "status_code": 200,
        "latency_ms": 80,
        "redacted_payload": {"customer_id": "cust_123"},
    }

    result = await execute_mock_step(expected, simulate_latency=False)

    assert result.status == "passed"
    assert result.actual_result["mock"] is True
    assert result.actual_result["tool_name"] == "customer_lookup"
    assert result.actual_result["status_code"] == 200
    assert result.error_message is None


@pytest.mark.asyncio
async def test_execute_mock_step_handles_empty_expected() -> None:
    result = await execute_mock_step(None, simulate_latency=False)

    assert result.status == "passed"
    assert result.actual_result["mock"] is True


@pytest.mark.asyncio
async def test_injection_timeout() -> None:
    expected = {
        "tool_name": "refund_policy",
        "status_code": 200,
        "injection": {"kind": "timeout", "delay_ms": 5},
    }
    result = await execute_mock_step(expected, failure_injection=True, simulate_latency=False)
    assert result.status == "failed"
    assert result.actual_result["error_type"] == "timeout"
    assert result.actual_result["status_code"] is None
    assert "timeout" in (result.error_message or "")


@pytest.mark.asyncio
async def test_injection_http_500() -> None:
    expected = {
        "tool_name": "order_lookup",
        "status_code": 200,
        "injection": {"kind": "http_500"},
    }
    result = await execute_mock_step(expected, failure_injection=True, simulate_latency=False)
    assert result.status == "failed"
    assert result.actual_result["status_code"] == 500
    assert result.actual_result["error_type"] == "http_500"


@pytest.mark.asyncio
async def test_injection_malformed_json() -> None:
    expected = {
        "tool_name": "refund_policy",
        "status_code": 200,
        "injection": {"kind": "malformed_json"},
    }
    result = await execute_mock_step(expected, failure_injection=True, simulate_latency=False)
    assert result.status == "failed"
    assert result.actual_result["error_type"] == "malformed_json"
    assert result.actual_result["redacted_payload"] == "{not-valid-json"


@pytest.mark.asyncio
async def test_injection_slow() -> None:
    expected = {
        "tool_name": "customer_lookup",
        "status_code": 200,
        "injection": {"kind": "slow", "delay_ms": 5},
    }
    result = await execute_mock_step(expected, failure_injection=True, simulate_latency=False)
    assert result.status == "failed"
    assert result.actual_result["error_type"] == "slow_response"


@pytest.mark.asyncio
async def test_injection_ignored_when_flag_disabled() -> None:
    expected = {
        "tool_name": "order_lookup",
        "status_code": 200,
        "injection": {"kind": "http_500"},
    }
    result = await execute_mock_step(expected, failure_injection=False, simulate_latency=False)
    assert result.status == "passed"
    assert result.actual_result["status_code"] == 200


def test_injection_spec_requires_target() -> None:
    with pytest.raises(ValidationError):
        FailureInjectionSpec.model_validate({"kind": "timeout"})


def test_replay_request_enables_flag_when_injections_present() -> None:
    request = ReplayCreateRequest.model_validate(
        {
            "trace_id": "trace_abc",
            "injections": [{"kind": "http_500", "step_order": 1}],
        }
    )
    assert request.failure_injection is True
