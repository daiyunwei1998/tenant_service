from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List, Optional

from app.core.config import settings
# Assuming the VectorStoreManager and other dependencies are already defined
from app.repository.vector_store import VectorStoreManager, OpenAIEmbeddingService, MilvusCollectionService

# Create a router instance for knowledge_base
router = APIRouter(
    prefix="/api/v1/knowledge_base",
    tags=["knowledge_base"]
)

# VectorStoreManager dependency (assuming injected or initialized earlier)
openai_service = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model = settings.embedding_model)
milvus_service = MilvusCollectionService(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
vector_store_manager = VectorStoreManager(openai_service, milvus_service)


# Pydantic models for request/response bodies
class UpdateContentRequest(BaseModel):
    newContent: str


class DocNamesResponse(BaseModel):
    tenantId: str
    docNames: List[str]


class UpdateResponse(BaseModel):
    tenantId: str
    entryId: int
    message: str


class EntriesByDocNameResponse(BaseModel):
    tenantId: str
    docName: str
    entries: List[dict]


# 1. Get a list of unique doc_name with paging
@router.get("/{tenantId}/doc-names", response_model=DocNamesResponse)
async def get_unique_doc_names_with_paging(
    tenantId: str = Path(..., description="The unique ID of the tenant"),
    limit: int = Query(100, description="Limit the number of doc_name entries returned"),
    last_doc_name: Optional[str] = Query(None, description="The last doc_name from the previous page for paging")
):
    try:
        # Fetch paginated doc_names using the limit and last_doc_name marker
        doc_names = vector_store_manager.get_doc_names_with_paging(tenantId, limit=limit, last_doc_name=last_doc_name)
        return {"tenantId": tenantId, "docNames": doc_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# 2. Update an entry's content identified by ID
@router.put("/{tenantId}/entries/{entryId}", response_model=UpdateResponse)
async def update_entry_by_id(
    update_request: UpdateContentRequest,
    tenantId: str = Path(..., description="The unique ID of the tenant"),
    entryId: int = Path(..., description="The unique ID of the entry to be updated"),

):
    try:
        vector_store_manager.update_entry_by_id(tenantId, entryId, update_request.newContent)
        return {
            "tenantId": tenantId,
            "entryId": entryId,
            "message": "Entry content updated successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3. Get a list of entries (content, id) by doc_name
@router.get("/{tenantId}/entries", response_model=EntriesByDocNameResponse)
async def get_entries_by_doc_name(
    tenantId: str = Path(..., description="The unique ID of the tenant"),
    docName: str = Query(..., description="The name of the document to filter entries")
):
    try:
        entries = vector_store_manager.get_entries_by_doc_name(tenantId, docName)
        return {
            "tenantId": tenantId,
            "docName": docName,
            "entries": entries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

