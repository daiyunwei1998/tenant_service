# app/dependencies.py

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.repository.database_async import engine_async  # Ensure this is correctly imported

SessionLocalAsync = sessionmaker(
    bind=engine_async,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocalAsync() as session:
        yield session

# Helper function to obtain a single session for background tasks
async def get_session() -> AsyncSession:
    async for session in get_db():
        return session

# New session maker specifically for background tasks
SessionBackground = sessionmaker(
    bind=engine_async,
    class_=AsyncSession,
    expire_on_commit=False
)

def get_background_session() -> AsyncSession:
    """
    Provides a new AsyncSession for background tasks.
    Ensures that each background task gets its own session.
    """
    return SessionBackground()