#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${API_BASE:-http://localhost:8000}"
TRACE_ID="${TRACE_ID:-trace_demo_refund}"
TMP_DIR="${TMPDIR:-/tmp}"
DETAIL_FILE="${TMP_DIR}/atr-replay-detail.json"

echo "==> Waiting for API readiness at ${API_BASE}"
for _ in $(seq 1 60); do
  if curl -sf "${API_BASE}/ready" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "${API_BASE}/ready" >/dev/null

echo "==> Ingesting sample trace"
curl -sf -X POST "${API_BASE}/v1/traces/ingest" \
  -H "Content-Type: application/json" \
  --data-binary @"${ROOT}/fixtures/sample_ingest.json"
echo

echo "==> Waiting for manifest"
for _ in $(seq 1 60); do
  if curl -sf "${API_BASE}/v1/traces/${TRACE_ID}/manifest" >/dev/null; then
    break
  fi
  sleep 0.5
done
curl -sf "${API_BASE}/v1/traces/${TRACE_ID}/manifest" >/dev/null

echo "==> Starting failure-injection replay"
CREATE_JSON="$(curl -sf -X POST "${API_BASE}/v1/replays/" \
  -H "Content-Type: application/json" \
  --data-binary @"${ROOT}/fixtures/sample_replay_inject.json")"
echo "${CREATE_JSON}"
REPLAY_ID="$(printf '%s' "${CREATE_JSON}" | python -c 'import json,sys; print(json.load(sys.stdin)["replay_id"])')"

echo "==> Waiting for replay ${REPLAY_ID}"
STATUS="queued"
for _ in $(seq 1 60); do
  curl -sf "${API_BASE}/v1/replays/${REPLAY_ID}" >"${DETAIL_FILE}"
  STATUS="$(python -c 'import json; print(json.load(open("'"${DETAIL_FILE}"'"))["status"])')"
  if [ "${STATUS}" = "completed" ] || [ "${STATUS}" = "failed" ]; then
    break
  fi
  sleep 0.5
done

echo
echo "==> Replay result"
python - "${DETAIL_FILE}" <<'PY'
import json
import sys

detail = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"replay_id: {detail['replay_id']}")
print(f"status:    {detail['status']}")
print(f"duration:  {detail.get('duration_ms')} ms")
print(f"first fail:{detail.get('first_failed_step_id')}")
print(f"summary:   {detail.get('summary_json')}")
print("steps:")
for step in detail.get("steps", []):
    err = (step.get("actual_result") or {}).get("error_type")
    print(f"  - #{step['step_order']} {step['step_id']}: {step['status']} ({err})")
PY

echo
echo "Demo complete. Grafana: http://localhost:3000 (admin/admin)"
