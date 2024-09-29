# app/services/usage_service.py

import logging
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone, date
from app.models.central_usage import CentralUsage
from app.schemas.usage import UsageRead, UsageCreate, MonthlySummary, DailySummary
from sqlalchemy.exc import SQLAlchemyError

from app.services.mongodb_service import mongodb_service


class UsageService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def get_monthly_usage(self, db: AsyncSession, year: int, month: int) -> List[UsageRead]:
        """
        Retrieves all billing records for the specified tenant and billing month, including today.
        """
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

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
        Calculates the total tokens used and total price for the specified tenant and billing month, including today.
        """
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

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

            # Aggregate additional data from MongoDB
            mongo_tokens, mongo_price = await mongodb_service.aggregate_monthly_data(self.tenant_id, year, month)

            total_tokens += mongo_tokens
            total_price += mongo_price

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

    async def get_combined_daily_usage(self, db: AsyncSession, year: int, month: int) -> List[DailySummary]:
        """
        Retrieves daily usage records for the specified tenant and billing month, combining MySQL and MongoDB data.
        """
        # Define the start and end dates of the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        try:
            # Fetch MySQL data aggregated by date
            stmt = select(
                func.date(CentralUsage.date).label("date"),
                func.sum(CentralUsage.tokens_used).label("tokens_used"),
                func.sum(CentralUsage.total_price).label("total_price")
            ).where(
                CentralUsage.tenant_id == self.tenant_id,
                CentralUsage.date >= datetime(year, month, 1, tzinfo=timezone.utc),
                CentralUsage.date <= datetime(year, month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)
            ).group_by(func.date(CentralUsage.date))

            result = await db.execute(stmt)
            mysql_records = result.fetchall()

            # Create a dictionary from MySQL records for easy lookup
            mysql_data: Dict[date, Dict[str, float]] = {
                record.date: {
                    "tokens_used": record.tokens_used,
                    "total_price": record.total_price
                } for record in mysql_records
            }

            # Generate all dates in the month
            total_days = (end_date - start_date).days + 1
            all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

            # Identify dates missing in MySQL data
            missing_dates = [d for d in all_dates if d not in mysql_data]

            # Fetch MongoDB data for missing dates
            mongo_data = await mongodb_service.aggregate_multiple_dates(self.tenant_id, missing_dates)

            # Merge MongoDB data into mysql_data
            for d, data in mongo_data.items():
                if d in mysql_data:
                    mysql_data[d]["tokens_used"] += data["tokens_used"]
                    mysql_data[d]["total_price"] += data["total_price"]
                else:
                    mysql_data[d] = data

            # Convert the data into a list of DailySummary
            daily_summaries = [
                DailySummary(
                    date=datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc),
                    tokens_used=int(data["tokens_used"]),
                    total_price=float(data["total_price"])
                )
                for d, data in sorted(mysql_data.items())
            ]

            return daily_summaries

        except SQLAlchemyError as e:
            logging.error(f"Error fetching daily usage for tenant {self.tenant_id}: {e}")
            raise e

    async def insert_usage_record(self, db: AsyncSession, usage_data: UsageCreate) -> UsageRead:
        """
        Inserts a new usage record into the tenant_usages table.

        :param db: The asynchronous database session.
        :param usage_data: The usage data to insert.
        :return: The inserted usage record as a UsageRead schema.
        """
        total_price = usage_data.tokens_used * usage_data.per_token_price

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
