# app/services/usage_service.py
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.models.central_usage import CentralUsage
from app.schemas.usage import UsageRead, TotalUsage, UsageCreate
from sqlalchemy.exc import SQLAlchemyError



class UsageService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def get_past_day_usage(self, db: AsyncSession) -> List[UsageRead]:
        """
        Retrieves all billing records from the past day for the tenant.
        """
        now = datetime.utcnow()
        past_day = now - timedelta(days=1)
        start_of_past_day = datetime.combine(past_day.date(), datetime.min.time())
        end_of_past_day = datetime.combine(past_day.date(), datetime.max.time())

        stmt = select(CentralUsage).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= start_of_past_day,
            CentralUsage.date <= end_of_past_day
        )

        try:
            result = await db.execute(stmt)
            usages = result.scalars().all()
            return usages
        except SQLAlchemyError as e:
            logging.error(f"Error fetching past day usage for tenant {self.tenant_id}: {e}")
            raise e

    async def get_total_tokens_past_day(self, db: AsyncSession) -> TotalUsage:
        """
        Calculates the total tokens and total price used in the past day for the tenant.
        """
        now = datetime.utcnow()
        past_day = now - timedelta(days=1)
        past_day_date = past_day.date()

        stmt = select(
            func.sum(CentralUsage.tokens_used),
            func.sum(CentralUsage.total_price)
        ).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= datetime.combine(past_day_date, datetime.min.time()),
            CentralUsage.date <= datetime.combine(past_day_date, datetime.max.time())
        )

        try:
            result = await db.execute(stmt)
            total_tokens, total_price = result.fetchone()
            total_tokens = total_tokens or 0
            total_price = total_price or 0.0

            return TotalUsage(
                tenant_id=self.tenant_id,
                total_tokens_past_day=total_tokens,
                total_price_past_day=total_price
            )
        except SQLAlchemyError as e:
            logging.error(f"Error calculating total tokens past day for tenant {self.tenant_id}: {e}")
            raise e

    async def insert_usage_record(self, db: AsyncSession, usage_data: UsageCreate) -> UsageRead:
        """
        Inserts a new usage record into the tenant_usages table.

        :param db: The asynchronous database session.
        :param usage_data: The usage data to insert.
        :return: The inserted usage record as a UsageRead schema.
        """
        # Calculate total_price
        total_price = usage_data.tokens_used * usage_data.per_token_price

        # Create a new CentralUsage instance
        new_usage = CentralUsage(
            date=usage_data.date,
            tenant_id=self.tenant_id,
            tokens_used=usage_data.tokens_used,
            per_token_price=usage_data.per_token_price,
            total_price=total_price
        )

        try:
            db.add(new_usage)
            await db.commit()
            await db.refresh(new_usage)
            return UsageRead.from_orm(new_usage)
        except SQLAlchemyError as e:
            await db.rollback()
            logging.error(f"Error inserting usage record for tenant {self.tenant_id}: {e}")
            raise e
