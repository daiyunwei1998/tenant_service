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

class BillingHistoryCreateSchema(BaseModel):
    tenant_id: str = Field(..., description="ID of the tenant")
    period: str = Field(..., description="Billing period, e.g., '2024-09'")
    tokens_used: int = Field(..., description="Number of tokens used")
    total_price: float = Field(..., description="Total price for the billing period")
    invoice_url: Optional[str] = Field(None, description="URL to the invoice PDF")