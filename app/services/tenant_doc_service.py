# app/services/tenant_doc_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete as sqlalchemy_delete
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.tenant_doc import TenantDoc
from app.schemas.tenant_doc_schema import TenantDocCreateSchema, TenantDocUpdateSchema


class TenantDocService:

    @staticmethod
    async def create_tenant_doc(tenant_doc_data: TenantDocCreateSchema, db: AsyncSession):
        new_doc = TenantDoc(**tenant_doc_data.dict())
        db.add(new_doc)
        try:
            await db.flush()  # To get the ID
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="TenantDoc with this tenant_id and doc_name already exists.")
        await db.commit()
        await db.refresh(new_doc)
        return new_doc

    @staticmethod
    async def update_tenant_doc_entries(tenant_id: str, doc_name: str, update_data: TenantDocUpdateSchema,
                                        db: AsyncSession):
        result = await db.execute(
            select(TenantDoc).where(TenantDoc.tenant_id == tenant_id, TenantDoc.doc_name == doc_name)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="TenantDoc not found")

        doc.num_entries = update_data.num_entries
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def delete_tenant_doc(tenant_id: str, doc_name: str, db: AsyncSession):
        result = await db.execute(
            sqlalchemy_delete(TenantDoc).where(TenantDoc.tenant_id == tenant_id, TenantDoc.doc_name == doc_name)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="TenantDoc not found")
        return

    @staticmethod
    async def get_tenant_docs(tenant_id: str, db: AsyncSession):
        result = await db.execute(
            select(TenantDoc).where(TenantDoc.tenant_id == tenant_id)
        )
        docs = result.scalars().all()
        return docs
