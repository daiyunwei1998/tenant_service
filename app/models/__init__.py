# app/models/__init__.py

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models to ensure they are registered with Base.metadata
from app.models.tenant import Tenant
from app.models.tenant_doc import TenantDoc
