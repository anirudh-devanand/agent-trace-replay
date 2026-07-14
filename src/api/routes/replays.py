from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session, get_kafka_producer, verify_api_key
from api.services.replay_schedule import (
    EmptyManifestError,
    InvalidInjectionTargetError,
    ManifestMissingError,
    ReplayNotFoundError,
    create_replay,
    get_replay_detail,
    list_replays,
)
from shared.kafka.producer import KafkaEventProducer
from shared.schemas.replay import (
    ReplayCreateRequest,
    ReplayCreateResponse,
    ReplayDetailResponse,
    ReplayListResponse,
)

router = APIRouter(prefix="/v1/replays", tags=["replays"])

REPLAY_CREATE_TOTAL = Counter(
    "replay_create_total",
    "Replay create requests",
    ["status"],
)


@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=ReplayCreateResponse)
async def create_replay_job(
    body: ReplayCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    producer: KafkaEventProducer = Depends(get_kafka_producer),
    _: None = Depends(verify_api_key),
) -> ReplayCreateResponse:
    try:
        response = await create_replay(session, producer, body)
        REPLAY_CREATE_TOTAL.labels(status="success").inc()
        return response
    except ManifestMissingError:
        REPLAY_CREATE_TOTAL.labels(status="manifest_missing").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="manifest not found for trace",
        ) from None
    except EmptyManifestError:
        REPLAY_CREATE_TOTAL.labels(status="empty_manifest").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="manifest has no replayable steps",
        ) from None
    except InvalidInjectionTargetError as exc:
        REPLAY_CREATE_TOTAL.labels(status="invalid_injection").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except Exception:
        REPLAY_CREATE_TOTAL.labels(status="error").inc()
        await session.rollback()
        raise


@router.get("/", response_model=ReplayListResponse)
async def list_replay_jobs(
    trace_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(verify_api_key),
) -> ReplayListResponse:
    return await list_replays(
        session,
        trace_id=trace_id,
        status_filter=status_filter,
        limit=limit,
    )


@router.get("/{replay_id}", response_model=ReplayDetailResponse)
async def get_replay(
    replay_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(verify_api_key),
) -> ReplayDetailResponse:
    try:
        return await get_replay_detail(session, replay_id)
    except ReplayNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="replay not found",
        ) from None
