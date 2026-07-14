import asyncio
import json
from pathlib import Path

import httpx
import pytest

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ingest.json"
API_BASE = "http://localhost:8000"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_triggers_manifest_creation() -> None:
    if not FIXTURE_PATH.exists():
        pytest.skip("fixture missing")

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["trace_id"] = "trace_normalizer_integration"
    for index, event in enumerate(payload["events"], start=1):
        event["idempotency_key"] = f"{payload['trace_id']}:span_{index}:tool_call"

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            pytest.skip("api not ready")

        ingest = await client.post("/v1/traces/ingest", json=payload)
        assert ingest.status_code == 202

        manifest_response = None
        for _ in range(30):
            response = await client.get(f"/v1/traces/{payload['trace_id']}/manifest")
            if response.status_code == 200:
                manifest_response = response.json()
                break
            await asyncio.sleep(0.5)

        if manifest_response is None:
            pytest.fail("manifest was not created by normalizer")

        assert manifest_response["trace_id"] == payload["trace_id"]
        assert manifest_response["manifest_version"] == "v1"
        assert manifest_response["manifest_json"]["step_count"] == 2
        assert len(manifest_response["manifest_json"]["steps"]) == 2
        assert manifest_response["manifest_json"]["steps"][0]["tool_name"] == "customer_lookup"
