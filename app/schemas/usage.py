# app/schemas/usage.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UsageCreate(BaseModel):
    date: datetime
    tokens_used: int
    per_token_price: float

    class Config:
        schema_extra = {
            "example": {
                "date": "2024-09-15T00:00:00Z",
                "tokens_used": 1500,
                "per_token_price": 0.000005
            }
        }

class UsageRead(BaseModel):
    id: int
    date: datetime
    tenant_id: str
    tokens_used: int
    per_token_price: float
    total_price: float

    class Config:
        orm_mode = True
        from_attributes = True  # Enable attribute access from ORM models

class TotalUsage(BaseModel):
    tenant_id: str
    total_tokens_past_day: int
    total_price_past_day: float

class MonthlySummary(BaseModel):
    tenant_id: str
    year: int
    month: int
    total_tokens_used: int
    total_price: float

    class Config:
        orm_mode = True
