# app/services/usage_service.py

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.models.usage import get_usage_model
from app.schemas.usage import UsageRead, TotalUsage, UsageCreate
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError


class UsageService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.Usage = get_usage_model(tenant_id)

    async def ensure_table_exists(self, db: AsyncSession):
        """
        Ensures that the usage table for the tenant exists. If not, creates it.
        """
        try:
            insp = inspect(db.sync_session.bind)
            table_name = self.Usage.__tablename__
            if not insp.has_table(table_name):
                self.Usage.__table__.create(bind=db.sync_session.bind)
        except SQLAlchemyError as e:
            # Log the error appropriately
            raise e

    async def get_past_day_usage(self, db: AsyncSession) -> List[UsageRead]:
        """
        Retrieves all billing records from the past day for the tenant.
        """
        now = datetime.utcnow()
        past_day = now - timedelta(days=1)
        start_of_past_day = datetime.combine(past_day.date(), datetime.min.time())
        end_of_past_day = datetime.combine(past_day.date(), datetime.max.time())

        stmt = select(self.Usage).where(
            self.Usage.date >= start_of_past_day,
            self.Usage.date <= end_of_past_day
        )

        try:
            result = await db.execute(stmt)
            usages = result.scalars().all()
            return usages
        except SQLAlchemyError as e:
            # Log the error appropriately
            raise e

    async def get_total_tokens_past_day(self, db: AsyncSession) -> TotalUsage:
        """
        Calculates the total tokens and total price used in the past day for the tenant.
        """
        now = datetime.utcnow()
        past_day = now - timedelta(days=1)
        past_day_date = past_day.date()

        stmt = select(
            func.sum(self.Usage.tokens_used),
            func.sum(self.Usage.total_price)
        ).where(
            self.Usage.date >= datetime.combine(past_day_date, datetime.min.time()),
            self.Usage.date <= datetime.combine(past_day_date, datetime.max.time())
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
            # Log the error appropriately
            raise e

    async def insert_usage_record(self, db: AsyncSession, usage_data: UsageCreate) -> UsageRead:
        """
        Inserts a new usage record into the tenant's usage table.

        :param db: The asynchronous database session.
        :param usage_data: The usage data to insert.
        :return: The inserted usage record as a UsageRead schema.
        """
        # Calculate total_price
        total_price = usage_data.tokens_used * usage_data.per_token_price

        # Create a new Usage instance
        new_usage = self.Usage(
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
            # Log the error appropriately
            raise e
