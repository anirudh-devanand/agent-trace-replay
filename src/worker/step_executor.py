import asyncio
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_MS = 100
DEFAULT_SLOW_MS = 200


@dataclass
class StepExecutionResult:
    status: str
    actual_result: dict[str, Any]
    latency_ms: int
    error_message: str | None = None


def _base_actual(expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": expected.get("event_type"),
        "tool_name": expected.get("tool_name"),
        "service_name": expected.get("service_name"),
        "method": expected.get("method"),
        "path": expected.get("path"),
        "status_code": expected.get("status_code"),
        "error_type": expected.get("error_type"),
        "latency_ms": expected.get("latency_ms"),
        "redacted_payload": expected.get("redacted_payload"),
        "mock": True,
    }


async def _sleep_ms(delay_ms: int) -> None:
    await asyncio.sleep(max(delay_ms, 0) / 1000.0)


async def execute_mock_step(
    expected_result: dict[str, Any] | None,
    *,
    failure_injection: bool = False,
    simulate_latency: bool = True,
    max_sleep_ms: int = 50,
) -> StepExecutionResult:
    """Replay a single dependency call as a local mock.

    When failure_injection is enabled and the step carries an ``injection``
    block, the mock synthesizes timeout / HTTP 500 / malformed JSON / slow
    responses instead of returning the recorded happy-path outcome.
    """
    expected = expected_result or {}
    started = time.perf_counter()
    injection = expected.get("injection") if failure_injection else None

    if isinstance(injection, dict) and injection.get("kind"):
        return await _execute_injected(expected, injection, started)

    if simulate_latency:
        recorded = expected.get("latency_ms")
        sleep_ms = 1 if recorded is None else min(int(recorded), max_sleep_ms)
        await _sleep_ms(sleep_ms)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return StepExecutionResult(
        status="passed",
        actual_result=_base_actual(expected),
        latency_ms=elapsed_ms,
        error_message=None,
    )


async def _execute_injected(
    expected: dict[str, Any],
    injection: dict[str, Any],
    started: float,
) -> StepExecutionResult:
    kind = str(injection.get("kind"))
    delay_override = injection.get("delay_ms")
    actual = _base_actual(expected)
    actual["injection"] = {"kind": kind}

    if kind == "timeout":
        delay_ms = int(delay_override or DEFAULT_TIMEOUT_MS)
        await _sleep_ms(delay_ms)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        actual.update(
            {
                "status_code": None,
                "error_type": "timeout",
                "latency_ms": elapsed_ms,
                "redacted_payload": None,
            }
        )
        return StepExecutionResult(
            status="failed",
            actual_result=actual,
            latency_ms=elapsed_ms,
            error_message=f"injected timeout after {delay_ms}ms",
        )

    if kind == "http_500":
        if expected.get("latency_ms") is not None:
            await _sleep_ms(min(int(expected["latency_ms"]), 20))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        actual.update(
            {
                "status_code": 500,
                "error_type": "http_500",
                "latency_ms": elapsed_ms,
                "redacted_payload": {"error": "internal_server_error"},
            }
        )
        return StepExecutionResult(
            status="failed",
            actual_result=actual,
            latency_ms=elapsed_ms,
            error_message="injected HTTP 500",
        )

    if kind == "malformed_json":
        if expected.get("latency_ms") is not None:
            await _sleep_ms(min(int(expected["latency_ms"]), 20))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        actual.update(
            {
                "status_code": 200,
                "error_type": "malformed_json",
                "latency_ms": elapsed_ms,
                "redacted_payload": "{not-valid-json",
            }
        )
        return StepExecutionResult(
            status="failed",
            actual_result=actual,
            latency_ms=elapsed_ms,
            error_message="injected malformed JSON response body",
        )

    if kind == "slow":
        delay_ms = int(delay_override or DEFAULT_SLOW_MS)
        await _sleep_ms(delay_ms)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        actual.update(
            {
                "status_code": expected.get("status_code") or 200,
                "error_type": "slow_response",
                "latency_ms": elapsed_ms,
            }
        )
        return StepExecutionResult(
            status="failed",
            actual_result=actual,
            latency_ms=elapsed_ms,
            error_message=f"injected slow response ({delay_ms}ms)",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return StepExecutionResult(
        status="failed",
        actual_result=actual,
        latency_ms=elapsed_ms,
        error_message=f"unknown injection kind: {kind}",
    )
