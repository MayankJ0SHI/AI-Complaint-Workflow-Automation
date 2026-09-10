from langchain_core.messages import HumanMessage, SystemMessage
from src.prompts.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt,
)
from src.models.document_schema import ComplaintCase
from src.llm.llm_client import LLMClient, ModelTier
from src.logger.logger import get_logger

logger = get_logger(__name__)


class ComplaintExtractionWorkflow:
    """
    Extract structured customer complaint information from document text.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, document_text: str) -> ComplaintCase:
        """
        Extract structured complaint information from the document.

        Args:
            document_text: Raw text extracted from the source document.

        Returns:
            Validated ComplaintCase object.

        Raises:
            ValueError: If the document text is empty.
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty.")

        logger.info(
            "Starting complaint extraction | characters=%d",
            len(document_text),
        )

        messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=build_extraction_prompt(document_text)),
        ]

        case = self.llm.invoke(
            messages=messages,
            tier=ModelTier.GENERIC,
            response_model=ComplaintCase,
        )

        logger.info(
            "Complaint extraction completed | " "customer=%s | category=%s | status=%s",
            case.customer_name,
            case.complaint_category.value,
            case.overall_case_status.value,
        )

        return case
