# app/services/celery_service.py

import pika
import json
from celery import Celery
import os
import asyncio
from pathlib import Path
import logging

from app.core.config import settings
from app.repository.database_async import SessionLocalAsync
from app.models import TenantDoc
from app.repository.vector_store import OpenAIEmbeddingService, MilvusCollectionService, VectorStoreManager
from app.services.knowledge_base_service import KnowledgeBaseService

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from your RabbitMQ config
rabbitmq_host = os.getenv("RABBITMQ_HOST")
rabbitmq_username = os.getenv("RABBITMQ_USERNAME")
rabbitmq_password = os.getenv("RABBITMQ_PASSWORD")
redis_host = os.getenv("REDIS_HOST")
redis_password = os.getenv("REDIS_PASSWORD")

# Celery configuration to use RabbitMQ as the broker and Redis as the result backend
celery_app = Celery(
    "worker",
    broker=f"pyamqp://{rabbitmq_username}:{rabbitmq_password}@{rabbitmq_host}//",
    backend=f"redis://:{redis_password}@{redis_host}:6379/0",
)

# Dependency injection
openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model=settings.embedding_model)
milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
vector_store_manager = VectorStoreManager(openai_service, milvus_service)

def send_rabbitmq_message(queue_name, message):
    # Define connection parameters, including credentials
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

    connection_params = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=5672,
        virtual_host='/',
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )

    connection = None
    try:
        # Establish a connection to RabbitMQ
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        # Declare the queue (it will only be created if it doesn't already exist)
        channel.queue_declare(queue=queue_name, durable=True)

        # Publish the message to the queue
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )

        logger.info(f"Message sent to queue {queue_name}: {message}")

    except pika.exceptions.AMQPConnectionError as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")

    finally:
        # Always close the connection
        if connection and connection.is_open:
            connection.close()

@celery_app.task
async def process_file(file_path: str, tenant_id: str):
    """
    Celery task to process a file asynchronously.
    """

    async def async_process():
        async with SessionLocalAsync() as session:
            try:
                # Process the file with KnowledgeBaseService
                texts = KnowledgeBaseService.process_file(file_path)
                await vector_store_manager.process_tenant_data(tenant_id, texts, os.path.basename(file_path))

                # Add TenantDoc record
                doc_name = os.path.basename(file_path)
                num_entries = len(texts)  # Adjust based on actual data
                tenant_doc = TenantDoc(
                    tenant_id=tenant_id,
                    doc_name=doc_name,
                    num_entries=num_entries
                )
                session.add(tenant_doc)
                await session.commit()
                await session.refresh(tenant_doc)
                logger.info(f"TenantDoc created: {tenant_doc}")

                logger.info(f"Processing completed for tenant {tenant_id}, file: {file_path}")

                # Remove the file after processing
                file_to_delete = Path(file_path)
                if file_to_delete.exists():
                    file_to_delete.unlink()  # Removes the file
                    logger.info(f"File {file_path} deleted successfully after processing.")
                else:
                    logger.error(f"File {file_path} not found when attempting to delete.")

                # Send a structured message to RabbitMQ
                message = {
                    "tenantId": tenant_id,
                    "message": f"Task completed for {doc_name}, tenant {tenant_id}",
                    "file": doc_name,
                    "docId": tenant_doc.id  # Optionally include the TenantDoc ID
                }
                send_rabbitmq_message('chunking_complete_notification_queue', message)

                return message

            except Exception as e:
                await session.rollback()
                logger.error(f"Error processing file {file_path}: {str(e)}")
                return f"Failed to process file {file_path}: {str(e)}"

    try:
        # Run the asynchronous processing within the Celery task
        return asyncio.run(async_process())
    except Exception as e:
        logger.error(f"Unexpected error in Celery task: {str(e)}")
        return f"Unexpected error: {str(e)}"
