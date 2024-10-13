# app/schemas/billing_history_schema.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BillingHistoryInfoSchema(BaseModel):
    id: int
    tenant_id: str
    period: str
    tokens_used: int
    total_price: float
    invoice_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
