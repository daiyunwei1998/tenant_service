# app/dependencies.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.repository.database_async import engine_async  # Ensure this is correctly imported

SessionLocalAsync = sessionmaker(
    bind=engine_async,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncSession:
    async with SessionLocalAsync() as session:
        yield session
