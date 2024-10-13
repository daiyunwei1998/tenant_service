from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.billing import Billing
from app.schemas.billing_schema import BillingCreateSchema, BillingUpdateSchema

class BillingService:

    @staticmethod
    async def get_billing(db: AsyncSession, tenant_id: str) -> Billing:
        result = await db.execute(select(Billing).where(Billing.tenant_id == tenant_id))
        billing = result.scalar_one_or_none()
        if not billing:
            raise HTTPException(status_code=404, detail="Billing information not found")
        return billing

    @staticmethod
    async def set_billing(db: AsyncSession, billing_data: BillingCreateSchema) -> Billing:
        billing = Billing(**billing_data.dict())
        db.add(billing)
        try:
            await db.commit()
            await db.refresh(billing)
            return billing
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Billing information for this tenant already exists")

    @staticmethod
    async def update_billing(db: AsyncSession, tenant_id: str, billing_update: BillingUpdateSchema) -> Billing:
        billing = await BillingService.get_billing(db, tenant_id)
        if billing_update.usage_alert is not None:
            billing.usage_alert = billing_update.usage_alert
        try:
            await db.commit()
            await db.refresh(billing)
            return billing
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update billing information: {str(e)}")

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