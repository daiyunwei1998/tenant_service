import pika
import json
from celery import Celery
import os

from pathlib import Path
import logging

from app.core.config import settings
from app.repository.vector_store import OpenAIEmbeddingService, MilvusCollectionService, VectorStoreManager
from app.services.knowledge_base_service import KnowledgeBaseService

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
openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model = settings.embedding_model)
milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
vector_store_manager = VectorStoreManager(openai_service, milvus_service)

def send_rabbitmq_message(queue_name, message):
    # Establish a connection to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()

    # Declare the queue (it will only be created if it doesn't already exist)
    channel.queue_declare(queue=queue_name, durable=True)

    # Publish the message to the queue
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        )
    )

    # Close the connection
    connection.close()

@celery_app.task
def process_file(file_path: str, tenant_id: str):
    try:
        # Process the file with KnowledgeBaseService
        texts = KnowledgeBaseService.process_file(file_path)
        vector_store_manager.process_tenant_data(tenant_id, texts, os.path.basename(file_path))

        logging.info(f"Processing completed for tenant {tenant_id}, file: {file_path}")

        # Remove the file after processing
        file_to_delete = Path(file_path)
        if file_to_delete.exists():
            file_to_delete.unlink()  # Removes the file
            logging.info(f"File {file_path} deleted successfully after processing.")
        else:
            logging.error(f"File {file_path} not found when attempting to delete.")

        # Send a structured message to RabbitMQ
        message = {
            "tenantId": tenant_id,
            "message": f"Task completed for {os.path.basename(file_path)}, tenant {tenant_id}",
            "file": os.path.basename(file_path),
        }
        send_rabbitmq_message('chunking_complete_notification_queue', message)

        return message

    except Exception as e:
        logging.error(f"Error processing file {file_path}: {str(e)}")
        return f"Failed to process file {file_path}: {str(e)}"
