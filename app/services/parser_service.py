# app/services/parser_service.py

import aio_pika
import json
import os
from pathlib import Path
import logging
import aiofiles.os  # For asynchronous file operations

from fastapi import HTTPException

from app.core.config import settings
from app.dependencies import get_session  # Import the helper function
from app.repository.vector_store import OpenAIEmbeddingService, MilvusCollectionService, VectorStoreManager
from app.schemas.tenant_doc_schema import TenantDocCreateSchema
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.tenant_doc_service import TenantDocService

# Initialize services
openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model=settings.embedding_model)
milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
vector_store_manager = VectorStoreManager(openai_service, milvus_service)

# Load environment variables from your RabbitMQ config
rabbitmq_host = os.getenv("RABBITMQ_HOST")
rabbitmq_username = os.getenv("RABBITMQ_USERNAME")
rabbitmq_password = os.getenv("RABBITMQ_PASSWORD")

async def send_rabbitmq_message_async(queue_name, message):
    connection_url = f"amqp://{rabbitmq_username}:{rabbitmq_password}@{rabbitmq_host}/"
    try:
        connection = await aio_pika.connect_robust(connection_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name
            )
            logging.info(f"Message sent to queue {queue_name}: {message}")
    except aio_pika.exceptions.AMQPConnectionError as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")

async def process_file(file_path: str, tenant_id: str):
    status = "success"
    number_of_entries = 0
    error_message = ""
    try:
        logging.info("process_file worker")
        # Process the file with KnowledgeBaseService
        kb_service = KnowledgeBaseService()
        texts = kb_service.process_file(file_path)

        number_of_entries = len(texts)  # Calculate the number of entries processed
        file_name = os.path.basename(file_path)
        vector_store_manager.process_tenant_data(tenant_id, texts, file_name)

        logging.info(f"Processing completed for tenant {tenant_id}, file: {file_path}, entries processed: {number_of_entries}")

        # Set success message
        message_text = f"Task completed successfully for {os.path.basename(file_path)}, tenant {tenant_id}"

        # Obtain the db session using the helper function
        db = await get_session()
        tenant_doc_data = TenantDocCreateSchema(
            tenant_id=tenant_id,
            doc_name=file_name,
            num_entries=number_of_entries
        )
        try:
            # Call create_tenant_doc with the session
            await TenantDocService.create_tenant_doc(tenant_doc_data, db)
            logging.info(f"Tenant document created in database for tenant '{tenant_id}' and doc '{file_name}'.")
        except HTTPException as he:
            if he.status_code == 400:
                logging.warning(f"TenantDoc with tenant_id '{tenant_id}' and doc_name '{file_name}' already exists.")
            else:
                logging.error(f"Failed to create TenantDoc: {he.detail}")

    except Exception as e:
        status = "failure"
        error_message = str(e)
        number_of_entries = 0  # Ensure number_of_entries is zero on failure
        logging.error(f"Error processing file {file_path}: {error_message}")

        # Set failure message
        message_text = f"Task failed for {os.path.basename(file_path)}, tenant {tenant_id}: {error_message}"

    finally:
        # Remove the file after processing or if an error occurred
        file_to_delete = Path(file_path)
        if file_to_delete.exists():
            try:
                await aiofiles.os.remove(file_path)  # Asynchronous file deletion
                logging.info(f"File {file_path} deleted successfully after processing.")
            except Exception as delete_error:
                logging.error(f"Failed to delete file {file_path}: {str(delete_error)}")
        else:
            logging.error(f"File {file_path} not found when attempting to delete.")

        # Prepare the message to send to RabbitMQ
        message = {
            "tenantId": tenant_id,
            "file": os.path.basename(file_path),
            "status": status,
            "number_of_entries": number_of_entries,
            "message": message_text  # Include the message field
        }

        # Optionally include error details if failed
        if status == "failure":
            message["error"] = error_message

        # Send the message to RabbitMQ asynchronously
        await send_rabbitmq_message_async('chunking_complete_notification_queue', message)

        return message  # Optionally return the message
