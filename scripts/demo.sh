#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${API_BASE:-http://localhost:8000}"
DEMO_DIR="${ROOT}/fixtures/demo"
TMP_DIR="${TMPDIR:-/tmp}"

echo "==> Waiting for API at ${API_BASE}"
for _ in $(seq 1 60); do
  if curl -sf "${API_BASE}/ready" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "${API_BASE}/ready" >/dev/null

wait_manifest() {
  local trace_id="$1"
  for _ in $(seq 1 60); do
    if curl -sf "${API_BASE}/v1/traces/${trace_id}/manifest" >/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  echo "manifest not ready for ${trace_id}" >&2
  return 1
}

wait_replay() {
  local replay_id="$1"
  local out_file="$2"
  for _ in $(seq 1 60); do
    curl -sf "${API_BASE}/v1/replays/${replay_id}" >"${out_file}"
    local status
    status="$(python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' "${out_file}")"
    if [ "${status}" = "completed" ] || [ "${status}" = "failed" ]; then
      return 0
    fi
    sleep 0.5
  done
  echo "replay ${replay_id} did not finish" >&2
  return 1
}

print_summary() {
  local label="$1"
  local detail_file="$2"
  python - "${label}" "${detail_file}" <<'PY'
import json, sys
label, path = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding="utf-8"))
print(f"\n---- {label} ----")
print(f"trace:      {d['trace_id']}")
print(f"replay:     {d['replay_id']}")
print(f"status:     {d['status']}")
print(f"duration:   {d.get('duration_ms')} ms")
print(f"first fail: {d.get('first_failed_step_id')}")
s = d.get("summary_json") or {}
print(f"summary:    passed={s.get('passed')} failed={s.get('failed')} steps={s.get('step_count')}")
print("step breakdown:")
for step in d.get("steps", []):
    err = (step.get("actual_result") or {}).get("error_type")
    print(f"  #{step['step_order']:<2} {step['step_id']:<28} {step['status']:<8} {err}")
PY
}

echo
echo "==> Loading demo agent recordings (traces)"
for file in trace_refund_support.json trace_checkout.json trace_knowledge_assist.json; do
  path="${DEMO_DIR}/${file}"
  trace_id="$(python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["trace_id"])' "${path}")"
  count="$(python -c 'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["events"]))' "${path}")"
  echo "  ingest ${trace_id} (${count} events)"
  curl -sf -X POST "${API_BASE}/v1/traces/ingest" \
    -H "Content-Type: application/json" \
    --data-binary @"${path}" >/dev/null
  wait_manifest "${trace_id}"
  echo "  manifest ready for ${trace_id}"
done

echo
echo "==> Running replays"
declare -a FILES=("replay_checkout_clean.json" "replay_knowledge_slow.json" "replay_refund_inject.json")
declare -a LABELS=(
  "Checkout (happy path, no injected failures)"
  "Knowledge assist (slow doc fetch injected)"
  "Refund support (timeout + bad JSON + HTTP 500)"
)

for i in "${!FILES[@]}"; do
  path="${DEMO_DIR}/${FILES[$i]}"
  create="$(curl -sf -X POST "${API_BASE}/v1/replays/" \
    -H "Content-Type: application/json" \
    --data-binary @"${path}")"
  replay_id="$(printf '%s' "${create}" | python -c 'import json,sys; print(json.load(sys.stdin)["replay_id"])')"
  echo "  queued ${replay_id}"
  detail_file="${TMP_DIR}/atr-demo-${replay_id}.json"
  wait_replay "${replay_id}" "${detail_file}"
  print_summary "${LABELS[$i]}" "${detail_file}"
done

echo
echo "==> Demo data is loaded"
echo "Open Grafana: http://localhost:3000  (admin / admin)"
echo "Dashboard: Agent Trace Replay - How to read the platform"
echo "The top of the dashboard explains each chart in plain language."
