# app/routers/aggregation_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.services.usage_service import UsageService
from app.schemas.aggregation import MonthlyAggregation
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository.database_async import get_db_async
import logging

router = APIRouter(
    prefix="/api/v1/aggregation",
    tags=["Aggregation"],
)

@router.get(
    "/monthly/",
    response_model=MonthlyAggregation,
    summary="Get Real-Time Monthly Usage Aggregation",
    description="Retrieve aggregated AI usage data for a specific tenant and current billing month, combining MySQL and MongoDB data."
)
async def get_real_time_monthly_aggregation(
    tenant_id: str = Query(..., description="The tenant's unique identifier"),
    db: AsyncSession = Depends(get_db_async)
):
    """
    Fetches aggregated AI usage data for the specified tenant and current billing month,
    combining previous data from MySQL and today's data from MongoDB.

    - **tenant_id**: The unique identifier for the tenant.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    service = UsageService(tenant_id)  # Correct instantiation
    try:
        aggregation = await service.get_combined_monthly_aggregation(db)
        return aggregation
    except Exception as e:
        logging.error(f"Error in get_real_time_monthly_aggregation: {e}")
        raise HTTPException(status_code=500, detail="Error aggregating usage data.")
