# app/main.py
import asyncio
import logging
from io import BytesIO

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from databases import Database
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.dependencies import get_db
from app.exceptions.tenant_exceptions import DuplicateTenantNameException, DuplicateTenantAliasException
from app.models.tenant import Tenant, Base
from app.routers import usage_router
from app.schemas.billing_history_schema import BillingHistoryInfoSchema, BillingHistoryCreateSchema
from app.schemas.billing_schema import BillingInfoSchema, BillingUpdateSchema, BillingCreateSchema
from app.schemas.tenant_schema import TenantCreateSchema, TenantInfoSchema, TenantUpdateSchema, \
    TenantUsageAlertUpdateSchema, UsageAlertSchema
from app.services.billing_service import BillingService
from app.services.image_upload import upload_to_s3
from app.services.tenant_service import TenantService
from app.routers.file_upload import router as upload_router
from app.routers.knowlege_base import router as knowlege_base_router
from app.routers.tenant_doc import router as tenant_doc_router

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Include existing routers
app.include_router(upload_router, prefix="/files")
app.include_router(knowlege_base_router)
app.include_router(tenant_doc_router)
app.include_router(usage_router.router)

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
        logging.error(IntegrityError)
        raise HTTPException(
            status_code=400,
            detail={"error_code": "IntegrityError", "message": "Error creating tenant"}
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


@app.patch("/api/v1/tenants/{tenant_id}/usage-alert", response_model=TenantInfoSchema)
async def update_usage_alert(
        tenant_id: str,
        usage_alert_data: TenantUsageAlertUpdateSchema,
        db: AsyncSession = Depends(get_db)
):
    """
    Update the usage_alert for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **usage_alert**: The new usage alert threshold (optional).
    """
    updated_tenant = await TenantService.update_usage_alert(
        tenant_id=tenant_id,
        usage_alert=usage_alert_data.usage_alert,
        db=db
    )
    return updated_tenant

@app.get("/api/v1/tenants/{tenant_id}/usage-alert", response_model=UsageAlertSchema)
async def get_usage_alert(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the usage_alert value for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **Response**: JSON object containing the `usage_alert` value.
    """
    usage_alert = await TenantService.get_usage_alert(tenant_id, db)
    return {"usage_alert": usage_alert}


@app.patch("/api/v1/tenants/{tenant_id}/billing", response_model=BillingInfoSchema)
async def set_or_update_billing(
        tenant_id: str,
        billing_update: BillingUpdateSchema,
        db: AsyncSession = Depends(get_db)
):
    """
    Create or update billing information for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **usage_alert**: (Optional) The token usage threshold for alerts.
    """
    # Check if billing exists
    try:
        billing = await BillingService.get_billing(db, tenant_id)
        # If exists, update it
        updated_billing = await BillingService.update_billing(db, tenant_id, billing_update)
        return updated_billing
    except HTTPException as e:
        if e.status_code == 404:
            # If billing does not exist, create it
            billing_create = BillingCreateSchema(tenant_id=tenant_id, usage_alert=billing_update.usage_alert)
            try:
                new_billing = await BillingService.set_billing(db, billing_create)
                return new_billing
            except HTTPException as ce:
                raise ce
        else:
            raise e

@app.get("/api/v1/tenants/{tenant_id}/billing", response_model=BillingInfoSchema)
async def get_billing(
        tenant_id: str,
        db: AsyncSession = Depends(get_db)
):
    """
    Retrieve billing information for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **Response**: JSON object containing billing information.
    """
    billing = await BillingService.get_billing(db, tenant_id)
    return billing

# Billing History Endpoints

@app.get("/api/v1/tenants/{tenant_id}/billing-history", response_model=list[BillingHistoryInfoSchema])
async def get_billing_history(
        tenant_id: str,
        db: AsyncSession = Depends(get_db)
):
    """
    Retrieve billing history for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **Response**: JSON array containing billing history records.
    """
    billing_history = await BillingService.get_billing_history(db, tenant_id)
    return billing_history

@app.get("/api/v1/tenants/{tenant_id}/billing-history/{billing_id}/invoice")
async def download_invoice(
    tenant_id: str,
    billing_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Download the invoice PDF for a specific billing record.

    - **tenant_id**: The unique identifier of the tenant.
    - **billing_id**: The unique identifier of the billing history record.
    - **Response**: Returns the invoice PDF file.
    """
    # Fetch the billing history record
    billing_history = await BillingService.get_billing_history_record(db, tenant_id, billing_id)
    if not billing_history or not billing_history.invoice_url:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Generate the PDF invoice
    pdf_content = await BillingService.generate_invoice(billing_history)

    # Return the PDF as a StreamingResponse
    return StreamingResponse(
        BytesIO(pdf_content),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=Invoice_{billing_history.period.replace(" ", "_")}.pdf'
        }
    )
@app.post(
    "/api/v1/tenants/{tenant_id}/billing-history",
    response_model=BillingHistoryInfoSchema,
    status_code=201,
    summary="Create a billing history record for a tenant"
)
async def create_billing_history(
    tenant_id: str,
    billing_data: BillingHistoryCreateSchema,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new billing history record for a specific tenant.

    - **tenant_id**: The unique identifier of the tenant.
    - **billing_data**: Billing history details.
    """
    if tenant_id != billing_data.tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id in path and body do not match")

    # Optionally, verify that the tenant exists
    #tenant = await TenantService.get_tenant_by_id(db, tenant_id)
    #if not tenant:
    #    raise HTTPException(status_code=404, detail="Tenant not found")

    new_billing_history = await BillingService.create_billing_history(db, billing_data)
    return new_billing_history