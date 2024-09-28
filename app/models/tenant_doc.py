# app/models/tenant_doc.py

from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from app.models import Base
from datetime import datetime

class TenantDoc(Base):
    __tablename__ = 'tenant_docs'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(255), nullable=False)
    doc_name = Column(String(500), nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow)
    num_entries = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'doc_name', name='unique_tenant_doc'),
    )
