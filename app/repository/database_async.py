# app/repository/database_async.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Base  # Ensure all models are imported here

# Create the asynchronous engine
engine_async = create_async_engine(settings.database_url, echo=True)

# Create the asynchronous sessionmaker
SessionLocalAsync = sessionmaker(
    bind=engine_async,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency for getting the async session (used in FastAPI)
async def get_db_async() -> AsyncSession:
    async with SessionLocalAsync() as session:
        yield session
