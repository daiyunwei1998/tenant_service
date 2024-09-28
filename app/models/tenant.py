# app/models/tenant.py

from sqlalchemy import Column, String, Boolean, Index
from sqlalchemy.dialects.mysql import BIGINT
from app.models import Base

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)  # MySQL-specific unsigned BIGINT
    tenant_id = Column(String(255), nullable=True, unique=True)
    logo = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    alias = Column(String(10), nullable=False, unique=True)  # Limit to 10 characters
    active_state = Column(Boolean, default=True, nullable=False)  # Active or inactive

    __table_args__ = (
        Index('ix_tenant_alias', 'alias'),  # Create index on alias field
    )
