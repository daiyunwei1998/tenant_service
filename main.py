# app/main.py
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from databases import Database

from app.core.config import settings
from app.dependencies import get_db
from app.exceptions.tenant_exceptions import DuplicateTenantNameException, DuplicateTenantAliasException
from app.models.tenant import Tenant, Base
from app.routers import usage_router
from app.schemas.tenant_schema import TenantCreateSchema, TenantInfoSchema, TenantUpdateSchema
from app.services.image_upload import upload_to_s3
from app.services.task_complete_message_handler import start_message_handler
from app.services.tenant_service import TenantService
from app.routers.file_upload import router as upload_router
from app.routers.knowlege_base import router as knowlege_base_router
from app.routers.tenant_doc import router as tenant_doc_router

app = FastAPI()

# Include existing routers
app.include_router(upload_router, prefix="/files")
app.include_router(knowlege_base_router)
app.include_router(tenant_doc_router)
app.include_router(usage_router.router)
app.include_router(aggregation_router.router) 

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup using only AsyncEngine
database = Database(settings.database_url)
engine = create_async_engine(settings.database_url, echo=True)

# Async sessionmaker
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Startup event to connect to the database and create tables
@app.on_event("startup")
async def startup():
    if not database.is_connected:
        await database.connect()
    await create_tables(engine)
    await asyncio.create_task(start_message_handler())

# Function to create tables asynchronously
async def create_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        from app.models import tenant, tenant_doc
        await conn.run_sync(Base.metadata.create_all)

# Shutdown event to disconnect from the database
@app.on_event("shutdown")
async def shutdown():
    if database.is_connected:
        await database.disconnect()

# Tenant Endpoints

@app.post("/api/v1/tenants/", response_model=TenantInfoSchema)
async def register_tenant(
        name: str = Form(...),
        alias: str = Form(...),
        logo: UploadFile = File(None),
        db: AsyncSession = Depends(get_db)
):
    try:
        tenant_data = TenantCreateSchema(name=name, alias=alias)

        # Delegate tenant registration to the service layer
        new_tenant = await TenantService.register_tenant(tenant_data, db)

        # Upload logo to S3 and get the path if logo is provided
        if logo:
            try:
                tenant_id = new_tenant.tenant_id
                logo_path = await upload_to_s3(logo, tenant_id)
                new_tenant.logo = logo_path
            except Exception as e:
                # If S3 upload fails, delete the tenant and raise an exception
                await TenantService.delete_tenant_internal(new_tenant.tenant_id, db)
                raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")

        await db.commit()
        await db.refresh(new_tenant)

        return new_tenant

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail={"error_code": "DUPLICATE_TENANT", "message": "Tenant with this name or alias already exists"}
        )
    except DuplicateTenantNameException as e:
        raise HTTPException(status_code=400, detail={"error_code": "DUPLICATE_TENANT_NAME", "message": e.message})

    except DuplicateTenantAliasException as e:
        raise HTTPException(status_code=400, detail={"error_code": "DUPLICATE_TENANT_ALIAS", "message": e.message})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.delete("/api/v1/tenants/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    await TenantService.delete_tenant_internal(tenant_id, db)
    return

@app.patch("/api/v1/tenants/{tenant_id}", response_model=TenantInfoSchema)
async def update_tenant(tenant_id: str, tenant_data: TenantUpdateSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    for field, value in tenant_data.dict(exclude_unset=True).items():
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    return tenant

@app.put("/api/v1/tenants/{tenant_id}/logo", response_model=TenantInfoSchema)
async def update_tenant_logo(tenant_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    relative_path = await upload_to_s3(file, tenant_id)
    tenant.logo = relative_path
    await db.commit()
    await db.refresh(tenant)
    return tenant

@app.get("/api/v1/tenants/check")
async def check_tenant(
        db: AsyncSession = Depends(get_db),
        name: str = Query(None, description="Tenant name to check"),
        alias: str = Query(None, description="Tenant alias to check"),
):
    tenant = await TenantService.get_tenant_by_alias_or_name(db, name=name, alias=alias)

    if tenant:
        return {"data": tenant}
    else:
        raise HTTPException(status_code=404, detail="Tenant not found")

@app.get("/api/v1/tenants/find")
async def get_tenant(
        db: AsyncSession = Depends(get_db),
        tenant_id: str = Query(None, description="Tenant id to check"),
        alias: str = Query(None, description="Tenant alias to check"),
        name: str = Query(None, description="Tenant name to check"),
):
    tenant = await TenantService.get_tenant_by_alias_or_name(db, name=name, alias=alias, tenant_id=tenant_id)

    if tenant:
        return {"data": tenant}
    else:
        raise HTTPException(status_code=404, detail="Tenant not found")
