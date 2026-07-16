from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Create async engine using asyncpg driver (URL provided via settings)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
)

# AsyncSession factory with expire_on_commit=False
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base model class using modern DeclarativeBase
class Base(DeclarativeBase):
    pass

# Dependency function yielding async sessions
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
