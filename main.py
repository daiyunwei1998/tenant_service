import logging

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.future import select
from databases import Database
from sqlalchemy import delete as sqlalchemy_delete, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.tenant import Tenant, Base
from app.schemas.tenant_schema import TenantCreateSchema, TenantInfoSchema, TenantUpdateSchema
from app.services.image_upload import upload_to_s3
from app.services.tenant_service import TenantService
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

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


# Create Tenant
@app.post("/tenants/", response_model=TenantInfoSchema)
async def register_tenant(tenant_data: TenantCreateSchema, db: AsyncSession = Depends(get_db)):
    try:
        # Delegate the tenant registration to the service
        new_tenant = await TenantService.register_tenant(tenant_data, db)
        return new_tenant
    except Exception as e:
        # Catch any other general exceptions
        raise HTTPException(status_code=400, detail=f"Failed to register tenant: {str(e)}")


# Delete Tenant
@app.delete("/tenants/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(sqlalchemy_delete(Tenant).where(Tenant.tenant_id == tenant_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await db.commit()
    return JSONResponse(status_code=200, content={"message": "Tenant deleted"})


# Update Tenant
@app.patch("/tenants/{tenant_id}", response_model=TenantInfoSchema)
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
@app.put("/tenants/{tenant_id}/logo", response_model=TenantInfoSchema)
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
@app.get("/tenants/{tenant_id}", response_model=TenantInfoSchema)
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant

# Get Tenant by alias
@app.get("/tenants/{alias}", response_model=TenantInfoSchema)
async def get_tenant(alias: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.alias == alias))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant