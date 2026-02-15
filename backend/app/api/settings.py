from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..dependencies import get_directory_sync_service
from ..core.database import get_session
from ..models.sql import Settings
from ..schemas.settings import Settings as SettingsSchema, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

async def get_or_create_settings(session: AsyncSession) -> Settings:
    result = await session.execute(select(Settings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = Settings()
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    
    return settings

@router.get("", response_model=SettingsSchema)
async def get_settings(session: AsyncSession = Depends(get_session)):
    """Get global application settings."""
    settings = await get_or_create_settings(session)
    return SettingsSchema(
        id=settings.id,
        embedding_model=settings.embedding_model,
        batch_size=settings.batch_size,
        image_extensions=settings.image_extensions,
        auto_reindex=settings.auto_reindex,
        sync_frequency=settings.sync_frequency,
        updated_at=settings.updated_at
    )

@router.put("", response_model=SettingsSchema)
async def update_settings(
    update_data: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    directory_sync_service= Depends(get_directory_sync_service),
):
    """Update global application settings."""
    settings = await get_or_create_settings(session)

    settings.embedding_model = update_data.embedding_model
    settings.batch_size = update_data.batch_size
    settings.image_extensions = update_data.image_extensions
    settings.auto_reindex = update_data.auto_reindex
    settings.sync_frequency = update_data.sync_frequency

    await session.commit()
    await session.refresh(settings)

    # Notify sync service of changes
    await directory_sync_service.update_settings(
        auto_reindex=settings.auto_reindex,
        sync_frequency=settings.sync_frequency
    )

    return SettingsSchema(
        id=settings.id,
        embedding_model=settings.embedding_model,
        batch_size=settings.batch_size,
        image_extensions=settings.image_extensions,
        auto_reindex=settings.auto_reindex,
        sync_frequency=settings.sync_frequency,
        updated_at=settings.updated_at
    )
