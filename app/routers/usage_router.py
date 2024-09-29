# app/routers/usage_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository.database_async import get_db_async
from app.services.usage_service import UsageService
from app.schemas.usage import UsageRead, TotalUsage, UsageCreate

router = APIRouter(
    prefix="/api/v1/usage",
    tags=["Usage"],
)

@router.get(
    "/past-day",
    response_model=List[UsageRead],
    summary="Get Past Day's Usage Data",
    description="Retrieve all billing records from the past day for a specific tenant."
)
async def get_past_day_usage(
    tenant_id: str = Query(..., description="The tenant's unique identifier"),
    db: AsyncSession = Depends(get_db_async)
):
    """
    Fetches all billing records from the past day for the specified tenant.

    - **tenant_id**: The unique identifier for the tenant.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)
    try:
        await service.ensure_table_exists(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error ensuring table exists.")

    try:
        usage_records = await service.get_past_day_usage(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching usage records.")

    if not usage_records:
        raise HTTPException(status_code=404, detail="No usage records found for the past day")

    return usage_records

@router.post(
    "/",
    response_model=UsageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Insert Usage Data",
    description="Insert a usage record for a specific tenant."
)
async def insert_usage_record(
    tenant_id: str = Query(..., description="The tenant's unique identifier"),
    usage_data: UsageCreate = ...,
    db: AsyncSession = Depends(get_db_async)
):
    """
    Inserts a usage record into the tenant's usage table.

    - **tenant_id**: The unique identifier for the tenant.
    - **usage_data**: The usage data to insert.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)
    try:
        await service.ensure_table_exists(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error ensuring table exists.")

    try:
        inserted_record = await service.insert_usage_record(db, usage_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error inserting usage record.")

    return inserted_record