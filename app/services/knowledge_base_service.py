import logging
import os
import json
from typing import List

from app.core.config import settings
import unstructured_client
from unstructured_client.models import operations, shared


class KnowledgeBaseService:
    def __init__(self):
        self.client = unstructured_client.UnstructuredClient(
            api_key_auth=settings.UNSTRUCTURED_API_KEY,
            server_url=settings.UNSTRUCTURED_API_URL,
        )
        logging.info("UnstructuredClient initialized.")

    def process_file(self, file_path: str) -> List[str]:
        """
        Processes the given file and returns a list of extracted text segments.

        :param file_path: Path to the input file.
        :return: List of text segments extracted from the file.
        """
        elements = self.parser(file_path)
        texts = [element.get('text', '') for element in elements]
        logging.info(f"Extracted texts: {texts}")
        return texts

    def parser(self, file_path: str) -> List[dict]:
        """
        Parses the file using the UnstructuredClient and returns the parsed elements.

        :param file_path: Path to the input file.
        :return: List of parsed elements as dictionaries.
        """
        logging.info(f"Starting parsing of {file_path}")

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            req = operations.PartitionRequest(
                partition_parameters=shared.PartitionParameters(
                    files=shared.Files(
                        content=data,
                        file_name=os.path.basename(file_path),
                    ),
                    strategy=shared.Strategy.HI_RES,
                    languages=['eng'],
                    split_pdf_page=True,  # If True, splits the PDF file into smaller chunks of pages.
                    split_pdf_allow_failed=True,  # If True, the partitioning continues even if some pages fail.
                    split_pdf_concurrency_level=15  # Set the number of concurrent requests to the maximum value: 15.
                ),
            )

            res = self.client.general.partition(request=req)
            element_dicts = [element for element in res.elements]

            logging.info(f"Parsed elements: {element_dicts}")
            return element_dicts

        except Exception as e:
            logging.error(f"Error parsing file {file_path}: {e}")
            raise


# Example usage:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    kb_service = KnowledgeBaseService()
    input_file = "PATH_TO_INPUT_FILE"  # Replace with your input file path
    output_file = "PATH_TO_OUTPUT_FILE"  # Replace with your desired output file path

    try:
        extracted_texts = kb_service.process_file(input_file)

        # Optionally, write the extracted texts to an output file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extracted_texts, f, indent=2)

        logging.info(f"Successfully processed and saved extracted texts to {output_file}")

    except Exception as e:
        logging.error(f"Failed to process file: {e}")
