# app/models/usage.py

from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

def get_usage_model(tenant_id: str):
    """
    Dynamically creates a SQLAlchemy model for a given tenant.

    :param tenant_id: The tenant identifier to customize the table name.
    :return: A SQLAlchemy declarative model.
    """
    table_name = f"{tenant_id}_usage"

    class Usage(Base):
        __tablename__ = table_name
        id = Column(Integer, primary_key=True, index=True)
        date = Column(DateTime, nullable=False)
        tenant_id = Column(String, nullable=False, index=True)
        tokens_used = Column(Integer, nullable=False)
        per_token_price = Column(Float, nullable=False)
        total_price = Column(Float, nullable=False)

        def __repr__(self):
            return (f"<Usage(id={self.id}, date={self.date}, tenant_id={self.tenant_id}, "
                    f"tokens_used={self.tokens_used}, per_token_price={self.per_token_price}, "
                    f"total_price={self.total_price})>")

    return Usage
