import logging

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List, Optional

from app.core.config import settings
# Assuming the VectorStoreManager and other dependencies are already defined
from app.repository.vector_store import VectorStoreManager, OpenAIEmbeddingService, MilvusCollectionService
from app.routers.tenant_doc import get_tenant_docs

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
    docNames: List[str] = []


class UpdateResponse(BaseModel):
    tenantId: str
    entryId: int
    message: str


class EntriesByDocNameResponse(BaseModel):
    tenantId: str
    docName: str
    entries: List[dict]

# Update an entry's content identified by ID
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


# Get a list of entries (content, id) by doc_name
@router.get("/{tenantId}/entries", response_model=EntriesByDocNameResponse)
async def get_entries_by_doc_name(
    tenantId: str = Path(..., description="The unique ID of the tenant"),
    docName: str = Query(..., description="The name of the document to filter entries")
):
    try:
        entries = vector_store_manager.get_entries_by_doc_name(tenantId, docName)
        logging.info({
            "tenantId": tenantId,
            "docName": docName,
            "entries": entries
        })
        return {
            "tenantId": tenantId,
            "docName": docName,
            "entries": entries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

