# app/routers/usage_router.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository.database_async import get_db_async
from app.services.usage_service import UsageService
from app.schemas.usage import UsageRead, MonthlySummary, UsageCreate, DailySummary

router = APIRouter(
    prefix="/api/v1/usage",
    tags=["Usage"],
)


@router.get(
    "/monthly/summary/",
    response_model=MonthlySummary,
    summary="Get Monthly Usage Summary",
    description="Retrieve the total number of tokens and total price used in a specific billing month for a tenant, combining MySQL and MongoDB data."
)
async def get_monthly_summary_endpoint(
        tenant_id: str = Query(..., description="The tenant's unique identifier"),
        year: int = Query(..., ge=1900, le=2100, description="The billing year"),
        month: int = Query(..., ge=1, le=12, description="The billing month (1-12)"),
        db: AsyncSession = Depends(get_db_async)
):
    """
    Calculates the total tokens and total price used in the specified billing month for the tenant,
    combining data from MySQL and MongoDB.

    - **tenant_id**: The unique identifier for the tenant.
    - **year**: The billing year.
    - **month**: The billing month (1-12).
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)
    try:
        summary = await service.get_monthly_summary(db, year, month)
    except Exception as e:
        logging.error(f"Error in get_monthly_summary_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error calculating monthly summary.")

    return summary


@router.get(
    "/monthly/daily/",
    response_model=List[DailySummary],
    summary="Get Daily Usage Details",
    description="Retrieve daily usage records (tokens used and total price) for each date within a specific billing month for a tenant, combining MySQL and MongoDB data."
)
async def get_daily_usage_endpoint(
        tenant_id: str = Query(..., description="The tenant's unique identifier"),
        year: int = Query(..., ge=1900, le=2100, description="The billing year"),
        month: int = Query(..., ge=1, le=12, description="The billing month (1-12)"),
        timezone_offset_minutes: int = Query(0, description="Timezone offset in minutes from UTC"),
        db: AsyncSession = Depends(get_db_async)
):
    """
    Fetches daily usage records for the specified tenant and billing month,
    combining data from MySQL and MongoDB.

    - **tenant_id**: The unique identifier for the tenant.
    - **year**: The billing year.
    - **month**: The billing month (1-12).
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)
    try:
        daily_usage = await service.get_combined_daily_usage(db, year, month, timezone_offset_minutes)
    except Exception as e:
        logging.error(f"Error in get_daily_usage_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error fetching daily usage records.")

    if not daily_usage:
        raise HTTPException(status_code=404, detail="No daily usage records found for the specified month")

    return daily_usage


@router.post(
    "/",
    response_model=UsageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Insert Usage Data",
    description="Insert a usage record for a specific tenant."
)
async def insert_usage_record(
        usage_data: UsageCreate,
        tenant_id: str = Query(..., description="The tenant's unique identifier"),
        db: AsyncSession = Depends(get_db_async)
):
    """
    Inserts a usage record into the tenant_usages table.

    - **usage_data**: The usage data to insert.
    - **tenant_id**: The unique identifier for the tenant.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)
    try:
        inserted_record = await service.insert_usage_record(db, usage_data)
    except Exception as e:
        logging.error(f"Error in insert_usage_record: {e}")
        raise HTTPException(status_code=500, detail="Error inserting usage record.")

    return inserted_record
