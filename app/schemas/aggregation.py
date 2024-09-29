# app/schemas/aggregation.py

from pydantic import BaseModel
from typing import Optional

class MonthlyAggregation(BaseModel):
    tenant_id: str
    year: int
    month: int
    total_tokens_used: int
    total_replies: int
    average_tokens_per_reply: float

    class Config:
        orm_mode = True
