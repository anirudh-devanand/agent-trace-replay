# Limitations

This document describes what the platform does **not** do today and what is out of scope.

## Replay model

- **Mock dependency replay only.** Steps replay recorded tool-call inputs/outputs or synthetic stubs — not live LLM inference. Re-running an agent end-to-end with deterministic model output is explicitly out of scope.
- **No full payload capture.** Traces store event metadata and structured fields needed for replay manifests; arbitrary binary or PII-heavy payloads are not retained.
- **Schema-first design.** Database tables for replay jobs, manifests, and steps exist before all services are implemented. Migrations may run ahead of the code that uses them.

## Infrastructure

- **Single-node Kafka (KRaft)** via Docker Compose. Not production-hardened: no TLS, no multi-broker cluster, no managed streaming.
- **No Kubernetes or per-job isolation.** Workers run as Compose services, not isolated job pods.
- **No OTLP ingest.** Traces arrive via the REST ingest API only.

## Observability

- Grafana ships with a minimal overview dashboard. Deep replay-specific panels depend on worker and replay metrics that are not emitted yet.

## Out of scope

- Live LLM replay or prompt-level determinism
- Full payload / conversation capture at scale
- Kubernetes-native job scheduling
- OpenTelemetry trace ingest as a first-class path
