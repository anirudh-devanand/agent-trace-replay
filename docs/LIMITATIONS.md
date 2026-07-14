# Limitations

This document describes what the platform does **not** do and what is intentionally out of scope for `v0.1.0-mvp`.

## Replay model

- **Mock dependency replay only.** Steps replay recorded tool-call metadata and synthetic stubs — not live LLM inference. Re-running an agent end-to-end with deterministic model output is out of scope.
- **Synthetic failure injection.** Supported kinds are `timeout`, `http_500`, `malformed_json`, and `slow`. These are local mock behaviors inside the worker, not calls to real downstream services.
- **No full payload capture.** Traces store the fields needed for manifests and debugging; arbitrary binary or PII-heavy payloads are not retained.

## Infrastructure

- **Single-node Kafka (KRaft)** via Docker Compose. Not production-hardened: no TLS, no multi-broker cluster, no managed streaming.
- **No Kubernetes or per-job isolation.** The API, normalizer, and worker run as Compose services.
- **No OTLP ingest.** Traces arrive via the REST ingest API only.

## Observability

- Grafana provisions an overview dashboard for ingest, normalization, replay jobs/steps, injection kinds, and latency histograms. This is a local Compose setup, not a production observability stack.

## Out of scope

- Live LLM replay or prompt-level determinism
- Full payload / conversation capture at scale
- Kubernetes-native job scheduling
- OpenTelemetry / OTLP as a first-class ingest path
- Public hosted demo environment (run locally with Compose)
