from typing import Pattern
import re

from pydantic import BaseModel, constr


class TenantCreateSchema(BaseModel):
    logo:str = ""
    name: str
    alias: constr(min_length=1, max_length=10)

    alias_pattern: Pattern = re.compile(r'^[a-zA-Z0-9]+$')

    class Config:
        from_attributes = True


class TenantUpdateSchema(BaseModel):
    logo: str = ""
    name: str = None
    alias: constr(min_length=1, max_length=10) = None

    alias_pattern: Pattern = re.compile(r'^[a-zA-Z0-9]+$')

    class Config:
        from_attributes = True


class TenantInfoSchema(BaseModel):
    tenant_id: str
    logo: str
    name: str
    alias: str
    active_state: bool

    class Config:
        from_attributes = True
