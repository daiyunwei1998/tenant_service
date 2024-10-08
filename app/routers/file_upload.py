# app/routers/file_upload.py

import logging
from typing import List
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
import aiofiles
import threading

from app.services.parser_service import process_file  # Ensure this is the updated version

router = APIRouter()

# Directory where files will be stored
UPLOAD_DIRECTORY = Path.cwd() / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {'.txt', '.json', '.pdf'}

def submit_process_file(file_path: str, tenant_id: str):
    """
    Runs the process_file coroutine in a separate thread.
    """
    try:
        # Import asyncio within the thread
        import asyncio

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_file(file_path, tenant_id))
    except Exception as e:
        logging.error(f"Error in background processing: {str(e)}")
    finally:
        # Close the loop to free resources
        loop.close()

@router.post("/upload/")
def upload_file(tenant_id: str = Form(...), file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.endswith(tuple(ALLOWED_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        # Generate a unique filename including tenant_id and timestamp
        timestamped_filename = f"{tenant_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        file_location = UPLOAD_DIRECTORY / timestamped_filename

        # Write the file to the file system asynchronously
        # Note: Even though the endpoint is synchronous, aiofiles can be used with asyncio.run
        import asyncio

        async def save_file():
            async with aiofiles.open(file_location, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

        asyncio.run(save_file())

        # Start a new thread for background processing
        thread = threading.Thread(target=submit_process_file, args=(str(file_location), tenant_id), daemon=True)
        thread.start()
        logging.info(f"Started background thread for processing {file_location}, tenant {tenant_id}")

        return {
            "filename": file.filename,
            "location": str(file_location),
            "status": "processing_started"
        }

    except Exception as e:
        logging.error(f"Error in upload_file endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
