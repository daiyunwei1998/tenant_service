import os
from app.core.config import settings
from openparse import processing, DocumentParser

OPEN_AI_KEY = settings.OPENAI_API_KEY

class KnowledgeBaseService:
    @staticmethod
    def process_file(file_name: str):
        return KnowledgeBaseService.parser(basic_doc_path=file_name)

    @staticmethod
    def parser(basic_doc_path: str):
        semantic_pipeline = processing.SemanticIngestionPipeline(
            openai_api_key=OPEN_AI_KEY,
            model=settings.embedding_model,
            min_tokens=64,
            max_tokens=1024,
        )
        parser = DocumentParser(
            processing_pipeline=semantic_pipeline,
        )
        parsed_content = parser.parse(basic_doc_path).model_dump()
        texts = [node['text'] for node in parsed_content['nodes']]
        return texts