from typing import Pattern, Optional
import re

from pydantic import BaseModel, constr, Field, validator, field_validator


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

class TenantUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    alias: Optional[str] = Field(None, max_length=10)
    active_state: Optional[bool]
    usage_alert: Optional[int]  # You can include this here if you prefer

class TenantUsageAlertUpdateSchema(BaseModel):
    usage_alert: Optional[int] = Field(None, ge=0, description="Usage alert threshold")

    @field_validator('usage_alert')
    def check_usage_alert(cls, v):
        if v is not None and v < 0:
            raise ValueError("usage_alert must be non-negative")
        return v

class UsageAlertSchema(BaseModel):
    usage_alert: Optional[int]

    class Config:
        orm_mode = True