# app/schemas/usage.py

from pydantic import BaseModel
from datetime import datetime

class UsageRead(BaseModel):
    id: int
    date: datetime
    tenant_id: str
    tokens_used: int
    per_token_price: float
    total_price: float

    class Config:
        orm_mode = True

class UsageCreate(BaseModel):
    date: datetime
    tokens_used: int
    per_token_price: float

class MonthlySummary(BaseModel):
    tenant_id: str
    year: int
    month: int
    total_tokens_used: int
    total_price: float

    class Config:
        orm_mode = True

class DailySummary(BaseModel):
    date: datetime
    tokens_used: int
    total_price: float

    class Config:
        orm_mode = True
