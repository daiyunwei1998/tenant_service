# app/schemas/billing_schema.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BillingBaseSchema(BaseModel):
    usage_alert: Optional[int] = Field(None, description="Token usage threshold for alerts")
    total_usage: Optional[int] = Field(0, description="Total tokens used in the billing period")
    total_price: Optional[float] = Field(0.0, description="Total price for the billing period")

class BillingCreateSchema(BillingBaseSchema):
    tenant_id: str

class BillingUpdateSchema(BaseModel):
    usage_alert: Optional[int] = Field(None, description="Token usage threshold for alerts")

class BillingInfoSchema(BillingBaseSchema):
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
