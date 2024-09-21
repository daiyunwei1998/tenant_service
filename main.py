import logging

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.future import select
from databases import Database
from sqlalchemy import delete as sqlalchemy_delete, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.exceptions.tenant_exceptions import DuplicateTenantNameException, DuplicateTenantAliasException
from app.models.tenant import Tenant, Base
from app.schemas.tenant_schema import TenantCreateSchema, TenantInfoSchema, TenantUpdateSchema
from app.services.image_upload import upload_to_s3
from app.services.tenant_service import TenantService
from fastapi.middleware.cors import CORSMiddleware
from app.routers.file_upload import  router as upload_router
app = FastAPI()
app.include_router(upload_router, prefix="/files")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,  # Allow credentials (e.g., cookies, authorization headers)
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers (Authorization, Content-Type, etc.)
)

# Database setup
database = Database(settings.database_url)
engine = create_async_engine(settings.database_url)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency for creating async database sessions
async def get_db():
    async with SessionLocal() as session:
        yield session


# Startup event to connect to the database and create tables
@app.on_event("startup")
async def startup():
    if not database.is_connected:
        await database.connect()
    await create_tables(engine)


async def create_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        # Run synchronous inspection and table creation logic in the run_sync method
        await conn.run_sync(sync_table_creation)

# Define the synchronous table creation function
def sync_table_creation(conn):
    inspector = inspect(conn)
    for table_name in Base.metadata.tables:
        # Check if the table already exists
        if not inspector.has_table(table_name):
            logging.info(f"Creating table {table_name}...")
            Base.metadata.create_all(bind=conn)
        else:
            logging.info(f"Table {table_name} already exists, skipping creation.")

# Shutdown event to disconnect from the database
@app.on_event("shutdown")
async def shutdown():
    if database.is_connected:
        await database.disconnect()


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

    except IntegrityError as e:
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
# Delete Tenant
@app.delete("/api/v1/tenants/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(sqlalchemy_delete(Tenant).where(Tenant.tenant_id == tenant_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await db.commit()
    return JSONResponse(status_code=200, content={"message": "Tenant deleted"})


# Update Tenant
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


# Update Tenant Logo
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


# Get Tenant by ID
@app.get("/api/v1/tenants/{tenant_id}", response_model=TenantInfoSchema)
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant

# Get Tenant by alias
@app.get("/api/v1/tenants/{alias}", response_model=TenantInfoSchema)
async def get_tenant(alias: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.alias == alias))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant