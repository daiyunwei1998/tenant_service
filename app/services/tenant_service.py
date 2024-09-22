import logging

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.exceptions.tenant_exceptions import DuplicateTenantNameException, DuplicateTenantAliasException
from app.models.tenant import Tenant
from app.schemas.tenant_schema import TenantCreateSchema
from sqlalchemy import delete as sqlalchemy_delete, or_



class TenantService:

    @staticmethod
    async def check_duplicate(tenant_data: TenantCreateSchema, db: AsyncSession):
        """Check if the tenant with the given name or alias already exists."""

        # Check for duplicate name
        existing_tenant_name = await db.execute(
            select(Tenant).where(Tenant.name == tenant_data.name)
        )
        existing_tenant_name = existing_tenant_name.scalar_one_or_none()

        if existing_tenant_name:
            raise DuplicateTenantNameException()

        # Check for duplicate alias
        existing_tenant_alias = await db.execute(
            select(Tenant).where(Tenant.alias == tenant_data.alias)
        )
        existing_tenant_alias = existing_tenant_alias.scalar_one_or_none()

        if existing_tenant_alias:
            raise DuplicateTenantAliasException()


    @staticmethod
    async def register_tenant(tenant_data: TenantCreateSchema, db: AsyncSession):
        # Check for duplicate tenant
        await TenantService.check_duplicate(tenant_data, db)

        # Create the tenant
        new_tenant = Tenant(**tenant_data.model_dump(exclude={"alias_pattern"}))

        # SQLAlchemy will automatically manage the transaction
        db.add(new_tenant)
        await db.flush()  # populate the id

        # Generate tenant_id and update it
        tenant_id_value = f"tenant_{new_tenant.id}"
        new_tenant.tenant_id = tenant_id_value

        await db.commit()  # Manually commit the transaction

        # Refresh the instance to load the changes
        await db.refresh(new_tenant)

        return new_tenant

    @staticmethod
    async def update_tenant_logo_url(db: AsyncSession, tenant_id: str, logo_path: str):
        # Fetch tenant by ID
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Update tenant's logo
        tenant.logo = logo_path
        await db.commit()
        await db.refresh(tenant)  # Refresh the instance with new data

        return tenant

    @staticmethod
    async def delete_tenant_internal(tenant_id: str, db: AsyncSession):
        try:
            result = await db.execute(sqlalchemy_delete(Tenant).where(Tenant.tenant_id == tenant_id))
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Tenant not found")
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete tenant: {str(e)}")

    @staticmethod
    async def get_tenant_by_alias_or_name(db: AsyncSession,  name: str = None, alias: str = None, tenant_id:str = None):
        # Validate at least one query parameter is provided
        if not name and not alias and not tenant_id:
            raise HTTPException(status_code=400, detail="You must provide either a name or alias to check.")

        # Build the query
        query = select(Tenant)

        if name and alias:
            query = query.where(or_(Tenant.name == name, Tenant.alias == alias))
        elif name:
            query = query.where(Tenant.name == name)
        elif alias:
            query = query.where(Tenant.alias == alias)
        elif tenant_id:
            query = query.where(Tenant.tenant_id == tenant_id)

        # Execute the query
        result = await db.execute(query)
        tenant = result.scalar_one_or_none()

        return tenant