import json
from pathlib import Path

import httpx
import pytest

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ingest.json"
API_BASE = "http://localhost:8000"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_and_duplicate_ignore() -> None:
    if not FIXTURE_PATH.exists():
        pytest.skip("fixture missing")

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            pytest.skip("api not ready")

        first = await client.post("/v1/traces/ingest", json=payload)
        assert first.status_code == 202
        first_body = first.json()
        assert first_body["accepted"] == 2
        assert first_body["duplicates_ignored"] == 0

        second = await client.post("/v1/traces/ingest", json=payload)
        assert second.status_code == 202
        second_body = second.json()
        assert second_body["accepted"] == 0
        assert second_body["duplicates_ignored"] == 2

        detail = await client.get(f"/v1/traces/{payload['trace_id']}")
        assert detail.status_code == 200
        assert len(detail.json()["events"]) == 2
