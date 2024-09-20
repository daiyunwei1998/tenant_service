from sqlalchemy import Column, String, BigInteger, Boolean
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import Index

Base = declarative_base()


class SerializerMixin:
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)  # MySQL-specific unsigned BIGINT
    tenant_id = Column(String(255), nullable=True)
    logo = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    alias = Column(String(10), nullable=False, unique=True)  # Limit to 10 characters
    active_state = Column(Boolean, default=True, nullable=False)  # Active or inactive

    __table_args__ = (
        Index('ix_tenant_alias', 'alias'),  # Create index on alias field
    )