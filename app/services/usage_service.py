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

    async def get_monthly_summary(self, db: AsyncSession, year: int, month: int,
                                  timezone_offset_minutes: int = 0) -> MonthlySummary:
        # Adjust the date range
        adjusted_start_date = datetime(year, month, 1, tzinfo=timezone.utc) - timedelta(minutes=timezone_offset_minutes)
        if month == 12:
            adjusted_end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1) - timedelta(
                minutes=timezone_offset_minutes)
        else:
            adjusted_end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1) - timedelta(
                minutes=timezone_offset_minutes)

        # Fetch data from MySQL
        stmt = select(
            func.sum(CentralUsage.tokens_used).label("total_tokens"),
            func.sum(CentralUsage.total_price).label("total_price")
        ).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= adjusted_start_date,
            CentralUsage.date <= adjusted_end_date
        )

        try:
            result = await db.execute(stmt)
            total_tokens, total_price = result.fetchone()
            total_tokens = total_tokens or 0
            total_price = total_price or 0.0

            # Fetch data from MongoDB and adjust
            mongo_records = await mongodb_service.get_data_for_date_range(
                self.tenant_id, adjusted_start_date, adjusted_end_date
            )
            # Adjust and sum tokens and prices
            total_tokens += sum(record['total_tokens'] for record in mongo_records)
            total_price += sum(record['total_tokens'] * record['per_token_price'] for record in mongo_records)

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

    async def get_combined_daily_usage(self, db: AsyncSession, year: int, month: int,
                                       timezone_offset_minutes: int = 0) -> List[DailySummary]:
        # Adjust the date range based on the time zone offset
        start_date = datetime(year, month, 1, tzinfo=timezone.utc) - timedelta(minutes=timezone_offset_minutes)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1) - timedelta(
                minutes=timezone_offset_minutes)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1) - timedelta(
                minutes=timezone_offset_minutes)

        # Fetch data from MySQL without grouping
        stmt = select(
            CentralUsage.date,
            CentralUsage.tokens_used,
            CentralUsage.total_price
        ).where(
            CentralUsage.tenant_id == self.tenant_id,
            CentralUsage.date >= start_date,
            CentralUsage.date <= end_date
        )
        result = await db.execute(stmt)
        mysql_records = result.fetchall()

        # Fetch data from MongoDB
        mongo_records = await mongodb_service.get_data_for_date_range(
            self.tenant_id, start_date, end_date
        )

        # Combine and adjust records
        all_records = []
        for record in mysql_records:
            all_records.append({
                'date': record.date,
                'tokens_used': record.tokens_used,
                'total_price': record.total_price
            })
        for record in mongo_records:
            all_records.append({
                'date': record['created_at'],
                'tokens_used': record['total_tokens'],
                'total_price': record['total_tokens'] * record['per_token_price']
            })

        # Adjust dates according to the time zone offset
        from collections import defaultdict
        daily_data = defaultdict(lambda: {'tokens_used': 0, 'total_price': 0.0})

        for record in all_records:
            adjusted_datetime = record['date'] + timedelta(minutes=timezone_offset_minutes)
            adjusted_date = adjusted_datetime.date()
            daily_data[adjusted_date]['tokens_used'] += record['tokens_used']
            daily_data[adjusted_date]['total_price'] += record['total_price']

        # Generate daily summaries
        daily_summaries = [
            DailySummary(
                date=d.strftime("%Y-%m-%d"),
                tokens_used=int(daily_data[d]['tokens_used']),
                total_price=float(daily_data[d]['total_price'])
            )
            for d in sorted(daily_data.keys())
        ]

        return daily_summaries

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
