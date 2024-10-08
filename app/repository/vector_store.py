import json
from typing import List, Optional
from openai import OpenAI
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from app.core.config import settings


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

    def load_collection(self, collection: Collection):
        """Loads the collection into memory and waits for it to be ready."""
        try:
            collection.load()
            utility.wait_for_loading_complete(collection.name)
            print(f"Collection '{collection.name}' loaded into memory and ready to query.")
        except Exception as e:
            raise RuntimeError(f"Failed to load collection: {e}")

    def insert_data(self, collection: Collection, embeddings: List[List[float]], contents: List[str], doc_name:str):
        """Inserts data (embeddings and content) into the specified collection."""
        try:
            doc_names = [doc_name] * len(contents)
            data_to_insert = [embeddings, contents, doc_names]
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

    def get_unique_doc_names(self, collection: Collection) -> List[str]:
        """Retrieve a list of unique doc_name entries in the collection."""
        try:
            # Query to get unique doc_name
            results = collection.query(expr="", output_fields=["doc_name"])
            unique_doc_names = set([result["doc_name"] for result in results])
            return list(unique_doc_names)
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve doc names: {e}")

    def update_entry_by_id(self, collection: Collection, entry_id: int, new_content: str,
                           openai_service: OpenAIEmbeddingService):
        """Update content and recalculate embedding by id."""
        try:
            # Query to get the current entry
            results = collection.query(expr=f"id == {entry_id}", output_fields=["embedding", "content"])

            if len(results) == 0:
                raise RuntimeError(f"No entry found with id: {entry_id}")

            # Generate new embedding for the updated content
            new_embedding = openai_service.get_embeddings([new_content])[0]

            # Update the entry in the collection
            collection.update([entry_id], {"embedding": new_embedding, "content": new_content})
            collection.flush()

            print(f"Entry with id {entry_id} updated successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to update entry by id: {e}")

    def get_entries_by_doc_name(self, collection: Collection, doc_name: str) -> List[dict]:
        """Retrieve entries (content, id) by doc_name."""
        try:
            # Query to get entries by doc_name
            results = collection.query(expr=f"doc_name == '{doc_name}'", output_fields=["id", "content"])
            return [{"id": result["id"], "content": result["content"]} for result in results]
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve entries by doc_name: {e}")

    def get_doc_names_with_paging(self, collection: Collection, limit: int = 100,
                                  last_doc_name: Optional[str] = None) -> List[str]:
        """Retrieve a paginated list of unique doc_name entries."""
        try:
            self.load_collection(collection)
            # Build the expression for pagination if `last_doc_name` is provided
            if last_doc_name:
                expr = f"doc_name > '{last_doc_name}'"
            else:
                expr = ""  # No expression for the first page

            # Query the collection with a limit and optional expression
            results = collection.query(expr=expr, output_fields=["doc_name"], limit=limit)

            # Extract the doc_names from the query results
            doc_names = [result["doc_name"] for result in results]
            return doc_names
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve paginated doc names: {e}")


class VectorStoreManager:
    """High-level class responsible for managing tenant vector stores."""

    def __init__(self, openai_service: OpenAIEmbeddingService, milvus_service: MilvusCollectionService):
        self.openai_service = openai_service
        self.milvus_service = milvus_service

    def process_tenant_data(self, tenant_id: str, content: List[str], doc_name:str, collection_name_prefix: str = "tenant_", ):
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
        self.milvus_service.insert_data(collection, embeddings, content, doc_name)

        # Create an index for faster search queries
        self.milvus_service.create_index(collection)

    def get_unique_doc_names(self, tenant_id: str) -> List[str]:
        """Get a list of unique doc_name entries for a tenant."""
        tenant_collection_name = tenant_id
        collection = self.milvus_service.create_collection(tenant_collection_name, self._define_schema(tenant_id))
        return self.milvus_service.get_unique_doc_names(collection)

    def update_entry_by_id(self, tenant_id: str, entry_id: int, new_content: str):
        """Update an entry's content by id and recalculate embedding."""
        tenant_collection_name = tenant_id
        collection = self.milvus_service.create_collection(tenant_collection_name, self._define_schema(tenant_id))
        self.milvus_service.update_entry_by_id(collection, entry_id, new_content, self.openai_service)

    def get_entries_by_doc_name(self, tenant_id: str, doc_name: str) -> List[dict]:
        """Get a list of entries (content, id) by doc_name."""
        tenant_collection_name = tenant_id
        collection = self.milvus_service.create_collection(tenant_collection_name, self._define_schema(tenant_id))
        return self.milvus_service.get_entries_by_doc_name(collection, doc_name)

    def get_doc_names_with_paging(self, tenant_id: str, limit: int, last_doc_name: Optional[str] = None) -> List[str]:
        """Get a paginated list of doc_name entries for a tenant."""
        tenant_collection_name = tenant_id
        collection = self.milvus_service.create_collection(tenant_collection_name, self._define_schema(tenant_id))
        return self.milvus_service.get_doc_names_with_paging(collection, limit, last_doc_name)

    def _define_schema(self, tenant_id: str) -> CollectionSchema:
        """Defines the schema for a Milvus collection."""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="doc_name", dtype=DataType.VARCHAR, max_length=500)
        ]
        return CollectionSchema(fields,enable_dynamic_field=True, description=f"{tenant_id} knowledge base")



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

    # Get a list of unique doc_name
    doc_names = vector_store_manager.get_unique_doc_names(tenant_id)
    print(f"Unique doc_names: {doc_names}")

    # Update an entry by id
    entry_id = 1
    new_content = "Updated content for entry 1."
    vector_store_manager.update_entry_by_id(tenant_id, entry_id, new_content)

    # Get entries by doc_name
    doc_name = "document_1"
    entries = vector_store_manager.get_entries_by_doc_name(tenant_id, doc_name)
    print(f"Entries for doc_name '{doc_name}': {entries}")