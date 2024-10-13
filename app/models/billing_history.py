# app/models/billing_history.py

from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models import Base


class BillingHistory(Base):
    __tablename__ = "billing_history"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    period = Column(String, nullable=False)  # e.g., "Aug 2024"
    tokens_used = Column(Integer, default=0)
    total_price = Column(Float, default=0.0)
    invoice_url = Column(String, nullable=True)  # URL to the invoice PDF
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="billing_histories")
