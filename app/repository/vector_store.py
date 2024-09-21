import json
from typing import List
from openai import OpenAI
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from app.core.config import settings
import logging


class OpenAIEmbeddingService:
    """Service class for handling OpenAI embedding generation."""
    def __init__(self, api_key: str, model:str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using OpenAI API."""
        try:
            texts = [text.replace("\n", " ") for text in texts]
            response = self.client.embeddings.create(input=texts, model=self.model)
            return [data.embedding for data in response.data]
        except Exception as e:
            raise RuntimeError(f"Failed to generate embeddings: {e}")

from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

class MilvusCollectionService:
    """Service class for handling Milvus collections."""
    def __init__(self, host: str, port: int):
        connections.connect("default", host=host, port=port)

    def create_collection(self, name: str, schema: CollectionSchema) -> Collection:
        """Creates a new collection if it does not exist and returns the collection."""
        if not utility.has_collection(name):  # Check if the collection exists
            collection = Collection(name=name, schema=schema)
            print(f"Collection '{name}' created successfully.")
        else:
            collection = Collection(name=name)  # Load the existing collection
            print(f"Collection '{name}' already exists.")
        return collection

    def insert_data(self, collection: Collection, embeddings: List[List[float]], contents: List[str]):
        """Inserts data (embeddings and content) into the specified collection."""
        try:
            data_to_insert = [embeddings, contents]
            collection.insert(data_to_insert)
            collection.flush()  # Ensures data is written to disk
        except Exception as e:
            raise RuntimeError(f"Failed to insert data into collection: {e}")

    def create_index(self, collection: Collection, field_name: str = "embedding"):
        """Creates an index on the embedding field of the collection."""
        try:
            index_params = {
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {
                    "M": 16,
                    "efConstruction": 200
                }
            }
            collection.create_index(field_name=field_name, index_params=index_params)
        except Exception as e:
            raise RuntimeError(f"Failed to create index: {e}")



class VectorStoreManager:
    """High-level class responsible for managing tenant vector stores."""

    def __init__(self, openai_service: OpenAIEmbeddingService, milvus_service: MilvusCollectionService):
        self.openai_service = openai_service
        self.milvus_service = milvus_service

    def process_tenant_data(self, tenant_id: str, content: List[str], collection_name_prefix: str = "tenant_"):
        """
        Processes tenant data (list of strings) and stores it in a tenant-specific Milvus collection.

        Args:
            tenant_id (str): The unique ID of the tenant.
            content (List[str]): A list of strings (texts) for which embeddings will be generated.
            collection_name_prefix (str): A prefix for the tenant-specific collection name.
        """
        # Validate content
        if not isinstance(content, list) or not content:
            raise ValueError("Content must be a non-empty list of strings.")

        # Generate embeddings for the provided content
        embeddings = self.openai_service.get_embeddings(content)

        # Define the schema for this tenant's collection
        schema = self._define_schema(tenant_id)

        # Create or get the tenant-specific collection
        tenant_collection_name = tenant_id
        collection = self.milvus_service.create_collection(tenant_collection_name, schema)

        # Insert data into the collection
        self.milvus_service.insert_data(collection, embeddings, content)

        # Create an index for faster search queries
        self.milvus_service.create_index(collection)

    def _define_schema(self, tenant_id: str) -> CollectionSchema:
        """Defines the schema for a Milvus collection."""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535)
        ]
        return CollectionSchema(fields, description=f"{tenant_id} knowledge base")



# Example usage inside the main block, which is executed only when the script is run directly
if __name__ == "__main__":
    # Inject necessary dependencies
    openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY)
    milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
    vector_store_manager = VectorStoreManager(openai_service, milvus_service)

    # Example tenant data
    tenant_id = "tenant_123"
    content_list = [
        "This is the first document for tenant 123.",
        "This is another piece of text content.",
        "Final text content for embedding generation."
    ]

    # Process and insert data into the vector store for a specific tenant
    vector_store_manager.process_tenant_data(tenant_id, content_list)

    print(f"Data processed and inserted successfully for tenant: {tenant_id}")