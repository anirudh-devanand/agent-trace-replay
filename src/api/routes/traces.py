from fastapi import APIRouter, Depends, HTTPException, status
from prometheus_client import Counter
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session, get_kafka_producer, verify_api_key
from api.services.trace_ingest import TraceNotFoundError, get_trace_detail, ingest_trace
from shared.kafka.producer import KafkaEventProducer
from shared.schemas.trace import TraceDetailResponse, TraceIngestRequest, TraceIngestResponse

router = APIRouter(prefix="/v1/traces", tags=["traces"])

TRACE_INGESTION_TOTAL = Counter(
    "trace_ingestion_total",
    "Trace ingestion requests",
    ["status"],
)
TRACE_INGESTION_DUPLICATES_TOTAL = Counter(
    "trace_ingestion_duplicates_total",
    "Duplicate trace events ignored during ingestion",
)


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED, response_model=TraceIngestResponse)
async def ingest_trace_events(
    body: TraceIngestRequest,
    session: AsyncSession = Depends(get_db_session),
    producer: KafkaEventProducer = Depends(get_kafka_producer),
    _: None = Depends(verify_api_key),
) -> TraceIngestResponse:
    try:
        response = await ingest_trace(session, producer, body)
        TRACE_INGESTION_TOTAL.labels(status="success").inc()
        TRACE_INGESTION_DUPLICATES_TOTAL.inc(response.duplicates_ignored)
        return response
    except Exception:
        TRACE_INGESTION_TOTAL.labels(status="error").inc()
        await session.rollback()
        raise


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(verify_api_key),
) -> TraceDetailResponse:
    try:
        return await get_trace_detail(session, trace_id)
    except TraceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found") from None
