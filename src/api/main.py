from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shared.config import get_settings
from shared.db.session import engine
from shared.kafka.health import check_kafka_connection

REQUESTS_TOTAL = Counter("http_requests_total", "Total HTTP requests", ["endpoint", "method"])

app = FastAPI(
    title="Agent Trace Replay Platform",
    version="0.1.0",
    description="Ingest tool-call traces and replay failures in isolated workers.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    REQUESTS_TOTAL.labels(endpoint="/health", method="GET").inc()
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    REQUESTS_TOTAL.labels(endpoint="/ready", method="GET").inc()
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = str(exc)

    kafka_ok, kafka_msg = check_kafka_connection(settings)
    checks["kafka"] = kafka_msg if kafka_ok else kafka_msg

    all_ok = checks.get("postgres") == "ok" and kafka_ok
    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
