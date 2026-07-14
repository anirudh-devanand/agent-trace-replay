import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ingest.json"
API_BASE = "http://localhost:8000"


async def _wait_for_manifest(client: httpx.AsyncClient, trace_id: str) -> None:
    for _ in range(60):
        response = await client.get(f"/v1/traces/{trace_id}/manifest")
        if response.status_code == 200:
            return
        await asyncio.sleep(0.5)
    pytest.fail("manifest was not created by normalizer")


async def _wait_for_replay(client: httpx.AsyncClient, replay_id: str) -> dict:
    detail = None
    for _ in range(40):
        response = await client.get(f"/v1/replays/{replay_id}")
        assert response.status_code == 200
        detail = response.json()
        if detail["status"] in {"completed", "failed"}:
            return detail
        await asyncio.sleep(0.5)
    pytest.fail("replay did not finish")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_replay_and_complete() -> None:
    if not FIXTURE_PATH.exists():
        pytest.skip("fixture missing")

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["trace_id"] = f"trace_replay_{uuid4().hex[:8]}"
    for index, event in enumerate(payload["events"], start=1):
        event["idempotency_key"] = f"{payload['trace_id']}:span_{index}:tool_call"

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            pytest.skip("api not ready")

        ingest = await client.post("/v1/traces/ingest", json=payload)
        assert ingest.status_code == 202
        await _wait_for_manifest(client, payload["trace_id"])

        create = await client.post(
            "/v1/replays/",
            json={
                "trace_id": payload["trace_id"],
                "mode": "deterministic",
                "failure_injection": False,
            },
        )
        assert create.status_code == 202
        body = create.json()
        assert body["status"] == "queued"
        assert body["step_count"] == 2

        detail = await _wait_for_replay(client, body["replay_id"])
        assert detail["status"] == "completed"
        assert detail["summary_json"]["passed"] == 2
        assert detail["summary_json"]["failed"] == 0
        assert all(step["status"] == "passed" for step in detail["steps"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_with_failure_injection() -> None:
    if not FIXTURE_PATH.exists():
        pytest.skip("fixture missing")

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["trace_id"] = f"trace_inject_{uuid4().hex[:8]}"
    for index, event in enumerate(payload["events"], start=1):
        event["idempotency_key"] = f"{payload['trace_id']}:span_{index}:tool_call"

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            pytest.skip("api not ready")

        ingest = await client.post("/v1/traces/ingest", json=payload)
        assert ingest.status_code == 202
        await _wait_for_manifest(client, payload["trace_id"])

        create = await client.post(
            "/v1/replays/",
            json={
                "trace_id": payload["trace_id"],
                "failure_injection": True,
                "injections": [
                    {"kind": "timeout", "step_order": 1, "delay_ms": 10},
                    {"kind": "malformed_json", "step_order": 2},
                ],
            },
        )
        assert create.status_code == 202
        body = create.json()
        assert body["failure_injection"] is True
        assert len(body["injections"]) == 2

        detail = await _wait_for_replay(client, body["replay_id"])
        assert detail["status"] == "failed"
        assert detail["summary_json"]["passed"] == 0
        assert detail["summary_json"]["failed"] == 2
        assert detail["steps"][0]["actual_result"]["error_type"] == "timeout"
        assert detail["steps"][1]["actual_result"]["error_type"] == "malformed_json"
