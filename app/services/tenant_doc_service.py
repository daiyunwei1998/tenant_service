# app/services/tenant_doc_service.py
import logging

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
        # Check if the TenantDoc already exists
        stmt = select(TenantDoc).where(
            TenantDoc.tenant_id == tenant_doc_data.tenant_id,
            TenantDoc.doc_name == tenant_doc_data.doc_name
        )
        result = await db.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            logging.warning(
                f"TenantDoc already exists for tenant_id '{tenant_doc_data.tenant_id}' and doc_name '{tenant_doc_data.doc_name}'.")
            raise HTTPException(status_code=400, detail="TenantDoc with this tenant_id and doc_name already exists.")

        # If not existing, proceed to create
        new_doc = TenantDoc(**tenant_doc_data.dict())
        db.add(new_doc)
        try:
            await db.flush()  # To get the ID
            logging.info(f"Added TenantDoc: {tenant_doc_data}")
        except IntegrityError as e:
            await db.rollback()
            logging.error(f"IntegrityError while creating TenantDoc: {e}")
            raise HTTPException(status_code=400, detail="TenantDoc with this tenant_id and doc_name already exists.")
        except Exception as e:
            await db.rollback()
            logging.error(f"Unexpected error while creating TenantDoc: {e}")
            raise HTTPException(status_code=500, detail="Internal server error.")
        await db.commit()
        await db.refresh(new_doc)
        logging.info(f"Committed TenantDoc: {new_doc}")
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
    async def decrement_tenant_doc_entries(tenant_id: str, doc_name: str, update_data: TenantDocUpdateSchema,
                                           db: AsyncSession):
        """
        Decrement the num_entries by a specified amount.
        If num_entries reaches 0, delete the TenantDoc record.
        """
        result = await db.execute(
            select(TenantDoc).where(TenantDoc.tenant_id == tenant_id, TenantDoc.doc_name == doc_name)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="TenantDoc not found")

        # Decrement num_entries
        doc.num_entries += update_data.num_entries  # Assuming update_data.num_entries is negative

        if doc.num_entries <= 0:
            # Delete the TenantDoc record
            await db.delete(doc)
            await db.commit()
            logging.info(
                f"TenantDoc with tenant_id {tenant_id} and doc_name {doc_name} deleted as num_entries reached 0.")
        else:
            # Update the num_entries
            await db.commit()
            await db.refresh(doc)
            logging.info(
                f"TenantDoc with tenant_id {tenant_id} and doc_name {doc_name} decremented to {doc.num_entries}.")

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
