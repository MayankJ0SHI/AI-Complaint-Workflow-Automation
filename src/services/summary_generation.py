from langchain_core.messages import HumanMessage, SystemMessage

from src.prompts.prompts import (
    MANAGEMENT_SUMMARY_SYSTEM_PROMPT,
    build_management_summary_prompt,
)
from src.models.document_schema import ComplaintCase
from src.llm.llm_client import LLMClient, ModelTier
from src.logger.logger import get_logger

logger = get_logger(__name__)


class ManagementSummaryWorkflow:
    """
    Generate an internal management summary from structured
    customer complaint information.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, case: ComplaintCase) -> str:
        """
        Generate an internal case management summary.

        Args:
            case: Validated ComplaintCase extracted from the source document.

        Returns:
            Internal management case summary.

        Raises:
            ValueError: If case data is not provided.
        """
        if case is None:
            raise ValueError("Complaint case cannot be None.")

        logger.info(
            "Starting management summary generation | " "customer=%s | status=%s",
            case.customer_name,
            case.overall_case_status.value,
        )

        case_data = case.model_dump_json(indent=2)

        messages = [
            SystemMessage(content=MANAGEMENT_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=build_management_summary_prompt(case_data)),
        ]

        summary = self.llm.invoke(
            messages=messages,
            tier=ModelTier.BASIC,
        )

        logger.info(
            "Management summary generation completed | customer=%s",
            case.customer_name,
        )

        return summary.strip()
