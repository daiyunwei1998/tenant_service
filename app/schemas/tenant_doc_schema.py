# app/schemas/tenant_doc_schema.py

from pydantic import BaseModel
from datetime import datetime

class TenantDocCreateSchema(BaseModel):
    tenant_id: str
    doc_name: str
    num_entries: int = 0

class TenantDocUpdateSchema(BaseModel):
    num_entries: int

class TenantDocInfoSchema(BaseModel):
    id: int
    tenant_id: str
    doc_name: str
    created_time: datetime
    num_entries: int

    class Config:
        orm_mode = True
