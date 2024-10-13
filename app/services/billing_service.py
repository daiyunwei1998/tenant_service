from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from app.models.billing_history import BillingHistory
from app.schemas.billing_history_schema import BillingHistoryCreateSchema
from app.services.pdf_generator import generate_invoice_pdf
from typing import List, Dict

class BillingService:

    @staticmethod
    async def get_billing_history(db: AsyncSession, tenant_id: str) -> List[BillingHistory]:
        result = await db.execute(
            select(BillingHistory).where(BillingHistory.tenant_id == tenant_id).order_by(BillingHistory.period.desc())
        )
        billing_history = result.scalars().all()
        if not billing_history:
            raise HTTPException(status_code=404, detail="No billing history found for this tenant")
        return billing_history

    @staticmethod
    async def get_billing_history_record(db: AsyncSession, tenant_id: str, billing_id: int) -> BillingHistory:
        result = await db.execute(
            select(BillingHistory).where(
                BillingHistory.tenant_id == tenant_id,
                BillingHistory.id == billing_id
            )
        )
        billing_history = result.scalar_one_or_none()
        if not billing_history:
            raise HTTPException(status_code=404, detail="Billing history record not found")
        return billing_history

    @staticmethod
    async def generate_invoice(billing_history: BillingHistory) -> bytes:
        """
        Generates a PDF invoice for a given billing history record.

        Args:
            billing_history (BillingHistory): Billing history record.

        Returns:
            bytes: PDF content.
        """
        # Convert SQLAlchemy model to dictionary if needed
        billing_data = {
            "id": billing_history.id,
            "tenant_id": billing_history.tenant_id,
            "period": billing_history.period,
            "tokens_used": billing_history.tokens_used,
            "total_price": billing_history.total_price,
            "invoice_url": billing_history.invoice_url,
            "created_at": billing_history.created_at,
            "updated_at": billing_history.updated_at,
        }

        # Generate PDF
        pdf_content = generate_invoice_pdf(billing_data)

        return pdf_content

    @staticmethod
    async def create_billing_history(db: AsyncSession, billing_data: BillingHistoryCreateSchema) -> BillingHistory:
        new_billing_history = BillingHistory(
            tenant_id=billing_data.tenant_id,
            period=billing_data.period,
            tokens_used=billing_data.tokens_used,
            total_price=billing_data.total_price,
            invoice_url=billing_data.invoice_url,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_billing_history)
        try:
            await db.commit()
            await db.refresh(new_billing_history)
            return new_billing_history
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create billing history") from e
