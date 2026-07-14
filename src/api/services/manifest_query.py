from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ReplayManifest
from shared.schemas.manifest import ManifestDetailResponse


class ManifestNotFoundError(Exception):
    pass


async def get_manifest_detail(session: AsyncSession, trace_id: str) -> ManifestDetailResponse:
    manifest = await session.scalar(
        select(ReplayManifest).where(ReplayManifest.trace_id == trace_id)
    )
    if manifest is None:
        raise ManifestNotFoundError(trace_id)

    return ManifestDetailResponse(
        trace_id=manifest.trace_id,
        manifest_version=manifest.manifest_version,
        manifest_json=manifest.manifest_json,
        created_at=manifest.created_at,
    )
