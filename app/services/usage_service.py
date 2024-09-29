# app/services/usage_service.py

import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from app.models.central_usage import CentralUsage
from app.schemas.aggregation import MonthlyAggregation
from app.schemas.usage import UsageRead, UsageCreate, MonthlySummary
from sqlalchemy.exc import SQLAlchemyError

from app.services.mongodb_service import mongodb_service


class UsageService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def get_monthly_usage(self, db: AsyncSession, year: int, month: int) -> List[UsageRead]:
        """
        Retrieves all billing records for the specified tenant and billing month.
        Excludes today's data.
        """
        # Calculate the start and end dates of the billing month
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

        # Exclude today's data by setting end_date to start of today
        now = datetime.now(timezone.utc)
        start_of_today = datetime(year, month, now.day, tzinfo=timezone.utc)
        if end_date > start_of_today:
            end_date = start_of_today - timedelta(seconds=1)

        stmt = select(CentralUsage).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= start_date,
            CentralUsage.date <= end_date
        )

        try:
            result = await db.execute(stmt)
            usages = result.scalars().all()
            return usages
        except SQLAlchemyError as e:
            logging.error(f"Error fetching monthly usage for tenant {self.tenant_id}: {e}")
            raise e

    async def get_monthly_summary(self, db: AsyncSession, year: int, month: int) -> MonthlySummary:
        """
        Calculates the total tokens used and total price for the specified tenant and billing month.
        Excludes today's data.
        """
        # Calculate the start and end dates of the billing month
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

        # Exclude today's data by setting end_date to start of today
        now = datetime.now(timezone.utc)
        start_of_today = datetime(year, month, now.day, tzinfo=timezone.utc)
        if end_date > start_of_today:
            end_date = start_of_today - timedelta(seconds=1)

        stmt = select(
            func.sum(CentralUsage.tokens_used).label("total_tokens"),
            func.sum(CentralUsage.total_price).label("total_price")
        ).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= start_date,
            CentralUsage.date <= end_date
        )

        try:
            result = await db.execute(stmt)
            total_tokens, total_price = result.fetchone()
            total_tokens = total_tokens or 0
            total_price = total_price or 0.0

            summary = MonthlySummary(
                tenant_id=self.tenant_id,
                year=year,
                month=month,
                total_tokens_used=total_tokens,
                total_price=total_price
            )
            return summary
        except SQLAlchemyError as e:
            logging.error(f"Error calculating monthly summary for tenant {self.tenant_id}: {e}")
            raise e

    async def insert_usage_record(self, db: AsyncSession, usage_data: UsageCreate) -> UsageRead:
        """
        Inserts a new usage record into the tenant_usages table.

        :param db: The asynchronous database session.
        :param usage_data: The usage data to insert.
        :return: The inserted usage record as a UsageRead schema.
        """
        # Calculate total_price based on the updated per token price ($0.005 per 1K tokens)
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

    async def get_combined_monthly_aggregation(self, db: AsyncSession) -> MonthlyAggregation:
        """
        Combines usage data from MySQL and MongoDB for the current billing month.

        :param db: The asynchronous database session.
        :return: A MonthlyAggregation object containing combined data.
        """
        now = datetime.now(timezone.utc)
        year = now.year
        month = now.month

        # Aggregate previous data from MySQL
        summary = await self.get_monthly_summary(db, year, month)
        total_tokens_mysql = summary.total_tokens_used
        total_price_mysql = summary.total_price

        # Aggregate today's data from MongoDB
        total_tokens_mongodb, total_price_mongodb = await mongodb_service.aggregate_todays_data(self.tenant_id)

        # Calculate combined totals
        combined_total_tokens = total_tokens_mysql + total_tokens_mongodb
        combined_total_price = total_price_mysql + total_price_mongodb

        # Create MonthlyAggregation instance
        aggregation = MonthlyAggregation(
            tenant_id=self.tenant_id,
            year=year,
            month=month,
            total_tokens_used_mysql=total_tokens_mysql,
            total_price_mysql=total_price_mysql,
            total_tokens_used_mongodb=total_tokens_mongodb,
            total_price_mongodb=total_price_mongodb,
            combined_total_tokens=combined_total_tokens,
            combined_total_price=combined_total_price
        )

        return aggregation
