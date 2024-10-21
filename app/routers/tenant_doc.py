# app/routers/tenant_doc.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List


from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.tenant_doc_schema import TenantDocCreateSchema, TenantDocUpdateSchema, TenantDocInfoSchema
from app.services.tenant_doc_service import TenantDocService


router = APIRouter(
    prefix="/api/v1/tenant_docs",
    tags=["TenantDocs"]
)

@router.post("/", response_model=TenantDocInfoSchema)
async def create_tenant_doc(tenant_doc: TenantDocCreateSchema, db: AsyncSession = Depends(get_db)):
    return await TenantDocService.create_tenant_doc(tenant_doc, db)

@router.patch("/{tenant_id}/{doc_name}", response_model=TenantDocInfoSchema)
async def update_tenant_doc_entries(
    tenant_id: str,
    doc_name: str,
    update_data: TenantDocUpdateSchema,
    db: AsyncSession = Depends(get_db)
):
    return await TenantDocService.update_tenant_doc_entries(tenant_id, doc_name, update_data, db)

@router.delete("/{tenant_id}/{doc_name}", status_code=204)
async def delete_tenant_doc(tenant_id: str, doc_name: str, db: AsyncSession = Depends(get_db)):
    await TenantDocService.delete_tenant_doc(tenant_id, doc_name, db)
    return

@router.get("/{tenant_id}", response_model=List[TenantDocInfoSchema])
async def get_tenant_docs(tenant_id: str, db: AsyncSession = Depends(get_db)):
    docs = await TenantDocService.get_tenant_docs(tenant_id, db)
    if not docs:
        raise HTTPException(status_code=404, detail="No TenantDocs found for this tenant.")
    return docs

