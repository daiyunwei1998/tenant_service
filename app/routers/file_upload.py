from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks
from pathlib import Path
from datetime import datetime
from app.services.celery_service import process_file  # Adjust the import path if necessary

router = APIRouter()

# Directory where files will be stored
UPLOAD_DIRECTORY = Path.cwd() / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {'.txt', '.json', '.pdf'}

@router.post("/upload/")
async def upload_file(background_tasks: BackgroundTasks, tenant_id: str = Form(...), file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.endswith(tuple(ALLOWED_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        # Generate a unique filename including tenant_id and timestamp
        timestamped_filename = f"{tenant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        file_location = UPLOAD_DIRECTORY / timestamped_filename

        # Write the file to the file system
        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())

        # Add process_file to background tasks
        background_tasks.add_task(process_file, str(file_location), tenant_id)

        return {
            "filename": file.filename,
            "location": str(file_location),
            "status": "processing_started"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
