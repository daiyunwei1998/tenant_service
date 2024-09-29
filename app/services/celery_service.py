import pika
import json
from celery import Celery
import os
from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool
from pathlib import Path
import logging
import traceback

from app.core.config import settings
from app.repository.vector_store import OpenAIEmbeddingService, MilvusCollectionService, VectorStoreManager
from app.services.knowledge_base_service import KnowledgeBaseService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
rabbitmq_host = os.getenv("RABBITMQ_HOST")
rabbitmq_username = os.getenv("RABBITMQ_USERNAME")
rabbitmq_password = os.getenv("RABBITMQ_PASSWORD")
redis_host = os.getenv("REDIS_HOST")
redis_password = os.getenv("REDIS_PASSWORD")

# Celery configuration
celery_app = Celery(
    "worker",
    broker=f"pyamqp://{rabbitmq_username}:{rabbitmq_password}@{rabbitmq_host}//",
    backend=f"redis://:{redis_password}@{redis_host}:6379/0",
)

# Configure Celery to use gevent
celery_app.conf.update(
    worker_pool_restarts=True,
    worker_pool='gevent',
    worker_concurrency=10,  # Adjust based on your needs
)

# Dependency injection
openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model=settings.embedding_model)
milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
vector_store_manager = VectorStoreManager(openai_service, milvus_service)

def send_rabbitmq_message(queue_name, message):
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
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info(f"Message sent to queue {queue_name}: {message}")
    except pika.exceptions.AMQPConnectionError as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")
    finally:
        if connection and connection.is_open:
            connection.close()

@celery_app.task
def process_file(file_path: str, tenant_id: str):
    logging.info(f"Starting to process file: {file_path} for tenant: {tenant_id}")
    status = "success"
    number_of_entries = 0
    error_message = ""
    try:
        texts = KnowledgeBaseService.process_file(file_path)
        number_of_entries = len(texts)
        logging.info(f"Processed {number_of_entries} entries from file: {file_path}")

        vector_store_manager.process_tenant_data(
            tenant_id, texts, os.path.basename(file_path)
        )
        logging.info(f"Vector store processing completed for tenant {tenant_id}, file: {file_path}")

        message_text = f"Task completed successfully for {os.path.basename(file_path)}, tenant {tenant_id}"
    except Exception as e:
        status = "failure"
        error_message = str(e)
        number_of_entries = 0
        logging.error(f"Error processing file {file_path}: {error_message}")
        logging.error(traceback.format_exc())
        message_text = f"Task failed for {os.path.basename(file_path)}, tenant {tenant_id}: {error_message}"
    finally:
        file_to_delete = Path(file_path)
        if file_to_delete.exists():
            try:
                file_to_delete.unlink()
                logging.info(f"File {file_path} deleted successfully after processing.")
            except Exception as delete_error:
                logging.error(f"Failed to delete file {file_path}: {str(delete_error)}")
        else:
            logging.error(f"File {file_path} not found when attempting to delete.")

        message = {
            "tenantId": tenant_id,
            "file": os.path.basename(file_path),
            "status": status,
            "number_of_entries": number_of_entries,
            "message": message_text
        }
        if status == "failure":
            message["error"] = error_message

        send_rabbitmq_message('chunking_complete_notification_queue', message)
        logging.info(f"Task completed for file: {file_path}, tenant: {tenant_id}, status: {status}")
        return message

if __name__ == "__main__":
    logging.info("Starting Celery worker...")
    celery_app.worker_main(["worker", "--loglevel=info"])