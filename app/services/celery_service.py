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

@celery_app.task
def process_file(file_path: str, tenant_id: str):
    try:
        # Process the file with KnowledgeBaseService
        texts = KnowledgeBaseService.process_file(file_path)
        vector_store_manager.process_tenant_data(tenant_id, texts)

        logging.info(f"Processing completed for tenant {tenant_id}, file: {file_path}")

        # Remove the file after processing
        file_to_delete = Path(file_path)
        if file_to_delete.exists():
            file_to_delete.unlink()  # Removes the file
            logging.info(f"File {file_path} deleted successfully after processing.")
        else:
            logging.error(f"File {file_path} not found when attempting to delete.")

        return f"Task completed for {file_path}"

    except Exception as e:
        logging.error(f"Error processing file {file_path}: {str(e)}")
        return f"Failed to process file {file_path}: {str(e)}"