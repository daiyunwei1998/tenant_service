from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.tenant import Tenant
from app.schemas.tenant_schema import TenantCreateSchema


class TenantService:

    @staticmethod
    async def check_duplicate(tenant_data: TenantCreateSchema, db: AsyncSession):
        """Check if the tenant with the given name or alias already exists."""
        existing_tenant = await db.execute(
            select(Tenant).where(
                (Tenant.name == tenant_data.name) | (Tenant.alias == tenant_data.alias)
            )
        )
        existing_tenant = existing_tenant.scalar_one_or_none()

        if existing_tenant:
            raise HTTPException(
                status_code=400,
                detail="Tenant with this name or alias already exists"
            )

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
