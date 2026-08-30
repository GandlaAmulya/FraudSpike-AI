from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

database_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))
if database_path.name:
    database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, future=True)
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session for future API routes."""
    async with session_factory() as session:
        yield session