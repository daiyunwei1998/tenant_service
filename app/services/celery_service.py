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

        print(f"Message sent to queue {queue_name}: {message}")

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Failed to connect to RabbitMQ: {e}")

    finally:
        # Always close the connection
        if connection and connection.is_open:
            connection.close()

@celery_app.task
def process_file(file_path: str, tenant_id: str):
    status = "success"
    number_of_entries = 0
    error_message = ""
    try:
        # Process the file with KnowledgeBaseService
        texts = KnowledgeBaseService.process_file(file_path)
        number_of_entries = len(texts)  # Calculate the number of entries processed

        vector_store_manager.process_tenant_data(tenant_id, texts, os.path.basename(file_path))

        logging.info(f"Processing completed for tenant {tenant_id}, file: {file_path}, entries processed: {number_of_entries}")

        # Set success message
        message_text = f"Task completed successfully for {os.path.basename(file_path)}, tenant {tenant_id}"

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
                file_to_delete.unlink()  # Removes the file
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

        # Send the message to RabbitMQ
        send_rabbitmq_message('chunking_complete_notification_queue', message)

        return message  # Optionally return the message
