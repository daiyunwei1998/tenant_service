# app/models/central_usage.py

from sqlalchemy import Column, Integer, String, DateTime, Float, Index
from app.models import Base
from datetime import datetime


class CentralUsage(Base):
    __tablename__ = "tenant_usages"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    tokens_used = Column(Integer, nullable=False)
    per_token_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    def __repr__(self):
        return (f"<CentralUsage(id={self.id}, date={self.date}, tenant_id={self.tenant_id}, "
                f"tokens_used={self.tokens_used}, per_token_price={self.per_token_price}, "
                f"total_price={self.total_price})>")

# Optional: Create composite indexes for performance
Index('idx_tenant_date', CentralUsage.tenant_id, CentralUsage.date)
