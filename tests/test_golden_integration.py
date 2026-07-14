import asyncio
import json
from pathlib import Path

import httpx
import pytest

API_BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parents[1]
INGEST_PATH = ROOT / "fixtures" / "sample_ingest.json"
INJECT_PATH = ROOT / "fixtures" / "sample_replay_inject.json"
GOLDEN_PATH = ROOT / "fixtures" / "golden" / "refund_inject_expected.json"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_golden_refund_injection_e2e() -> None:
    if not INGEST_PATH.exists() or not GOLDEN_PATH.exists():
        pytest.skip("fixtures missing")

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    ingest_payload = json.loads(INGEST_PATH.read_text(encoding="utf-8"))
    inject_payload = json.loads(INJECT_PATH.read_text(encoding="utf-8"))

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            pytest.skip("api not ready")

        await client.post("/v1/traces/ingest", json=ingest_payload)

        for _ in range(60):
            manifest = await client.get(f"/v1/traces/{ingest_payload['trace_id']}/manifest")
            if manifest.status_code == 200:
                break
            await asyncio.sleep(0.5)
        else:
            pytest.fail("manifest not ready")

        create = await client.post("/v1/replays/", json=inject_payload)
        assert create.status_code == 202
        replay_id = create.json()["replay_id"]

        detail = None
        for _ in range(60):
            response = await client.get(f"/v1/replays/{replay_id}")
            detail = response.json()
            if detail["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.5)

        assert detail is not None
        assert detail["status"] == golden["expected_status"]
        assert detail["summary_json"]["passed"] == golden["expected_passed"]
        assert detail["summary_json"]["failed"] == golden["expected_failed"]
        assert detail["first_failed_step_id"] == golden["first_failed_step_id"]

        for expected_step, actual_step in zip(golden["steps"], detail["steps"], strict=True):
            assert actual_step["step_id"] == expected_step["step_id"]
            assert actual_step["status"] == expected_step["expected_step_status"]
            assert actual_step["actual_result"]["error_type"] == expected_step["expected_error_type"]
