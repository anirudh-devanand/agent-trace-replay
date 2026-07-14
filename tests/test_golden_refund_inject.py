import json
from pathlib import Path

import pytest

from worker.step_executor import execute_mock_step

GOLDEN_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "refund_inject_expected.json"
)


@pytest.mark.asyncio
async def test_golden_refund_inject_step_outcomes() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["expected_status"] == "failed"
    assert golden["expected_failed"] == 2

    for step in golden["steps"]:
        expected = {
            "event_type": "tool_call",
            "tool_name": step["tool_name"],
            "status_code": 200,
            "injection": {"kind": step["injection_kind"], "delay_ms": 5},
        }
        result = await execute_mock_step(
            expected,
            failure_injection=True,
            simulate_latency=False,
        )
        assert result.status == step["expected_step_status"]
        assert result.actual_result["error_type"] == step["expected_error_type"]
        assert result.actual_result["tool_name"] == step["tool_name"]
