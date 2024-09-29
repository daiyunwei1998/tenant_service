# app/schemas/usage.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UsageCreate(BaseModel):
    date: datetime = Field(..., description="The date of the billing entry")
    tokens_used: int = Field(..., ge=0, description="Number of tokens used")
    per_token_price: float = Field(..., ge=0.0, description="Price per token")

    class Config:
        schema_extra = {
            "example": {
                "date": "2024-04-26T00:00:00Z",
                "tokens_used": 1500,
                "per_token_price": 0.01
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


class TotalUsage(BaseModel):
    tenant_id: str
    total_tokens_past_day: int
    total_price_past_day: float
