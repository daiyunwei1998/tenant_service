import boto3
from fastapi import UploadFile, HTTPException
from botocore.exceptions import NoCredentialsError

from app.core.config import settings

s3 = boto3.client('s3')

BUCKET_NAME = settings.s3_bucket_name


async def upload_to_s3(file: UploadFile, tenant_id: int) -> str:
    try:
        # Define a unique file path within the S3 bucket
        file_key = f"tenant_logos/{tenant_id}/{file.filename}"

        # Upload file to S3
        s3.upload_fileobj(
            file.file,
            BUCKET_NAME,
            file_key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Return the relative path (e.g., tenant_logos/tenant_123/logo.png)
        return file_key

    except NoCredentialsError:
        raise HTTPException(status_code=500, detail="AWS credentials not found")
