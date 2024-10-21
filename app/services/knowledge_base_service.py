import logging
from typing import List

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings

from app.core.config import settings


class KnowledgeBaseService:
    def __init__(self):
        # Initialize OpenAI Embeddings
        self.embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        logging.info("OpenAI Embeddings initialized.")


    def process_file(self, file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """
        Processes the given PDF file and returns a list of extracted text chunks.

        :param file_path: Path to the input PDF file.
        :param chunk_size: Maximum number of characters per chunk.
        :param chunk_overlap: Number of overlapping characters between chunks.
        :return: List of text chunks extracted from the PDF.
        """
        logging.info(f"Processing file: {file_path}")

        # Load and extract text from PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        logging.info(f"Loaded {len(documents)} pages from PDF.")

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        logging.info(f"Split into {len(chunks)} chunks.")

        # Extract text content from chunks
        chunk_texts = [chunk.page_content for chunk in chunks]

        return chunk_texts

