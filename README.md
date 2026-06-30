# Agent Trace Replay Platform

Kafka-backed backend for ingesting AI agent tool-call traces, compiling replay manifests, and executing failure-injected mock replays in isolated workers.

## Problem

Agent workflows fail intermittently due to tool-call ordering, retries, latency spikes, and malformed downstream responses. Logs show what happened; this platform lets engineers **re-run the recorded dependency sequence** under controlled conditions.

## MVP scope (week 1)

- REST trace ingestion (`POST /v1/traces/ingest`)
- PostgreSQL storage + Kafka event pipeline
- Trace normalization into replay manifests
- Replay job scheduling and mock step execution
- Synthetic failures: timeout, HTTP 500, malformed JSON, slow response
- Replay results API + Prometheus metrics + Grafana dashboard

**Not in MVP:** live LLM replay, full payload capture, Kubernetes per-job isolation, OTLP ingest.

## Planned architecture

```text
Client → API (FastAPI) → PostgreSQL
                      ↘ Kafka → Normalizer → manifest
                                ↘ Worker → replay steps + results
Prometheus ← API / Normalizer / Worker
Grafana ← Prometheus
```

## Stack

Python 3.12, FastAPI, PostgreSQL, Kafka (KRaft), Docker Compose, Prometheus, Grafana

## Local development

```bash
cp .env.example .env
docker compose up --build
```

| Service    | URL                          |
|------------|------------------------------|
| API        | http://localhost:8000        |
| API health | http://localhost:8000/health |
| API ready  | http://localhost:8000/ready  |
| Prometheus | http://localhost:9091        |
| Grafana    | http://localhost:3000 (admin/admin) |

Run unit tests locally:

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/
```

## Demo scenario

Refund support agent trace: `refund_policy` times out, retry returns malformed JSON, agent proceeds with bad state, workflow fails. Replay reproduces the first failing dependency step.

## License

MIT
