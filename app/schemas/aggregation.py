# app/schemas/aggregation.py

from pydantic import BaseModel

class MonthlyAggregation(BaseModel):
    tenant_id: str
    year: int
    month: int
    total_tokens_used_mysql: int
    total_price_mysql: float
    total_tokens_used_mongodb: int
    total_price_mongodb: float
    combined_total_tokens: int
    combined_total_price: float

    class Config:
        orm_mode = True
