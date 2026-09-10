from langchain_core.messages import HumanMessage, SystemMessage

from src.prompts.prompts import (
    CUSTOMER_EMAIL_SYSTEM_PROMPT,
    build_customer_email_prompt,
)
from src.models.document_schema import ComplaintCase
from src.llm.llm_client import LLMClient
from src.models.model_schema import ModelTier
from src.logger.logger import get_logger

logger = get_logger(__name__)


class CustomerEmailWorkflow:
    """
    Generate a professional customer-facing response email
    from structured complaint case information.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, case: ComplaintCase) -> str:
        """
        Generate a customer response email.

        Args:
            case: Validated ComplaintCase extracted from the source document.

        Returns:
            Customer-facing email content.

        Raises:
            ValueError: If case data is not provided.
        """
        if case is None:
            raise ValueError("Complaint case cannot be None.")

        logger.info(
            "Starting customer email generation | " "customer=%s | status=%s",
            case.customer_name,
            case.overall_case_status.value,
        )

        case_data = case.model_dump_json(indent=2)

        messages = [
            SystemMessage(content=CUSTOMER_EMAIL_SYSTEM_PROMPT),
            HumanMessage(content=build_customer_email_prompt(case_data)),
        ]

        email = self.llm.invoke(
            messages=messages,
            tier=ModelTier.BASIC,
        )

        logger.info(
            "Customer email generation completed | customer=%s",
            case.customer_name,
        )

        return email.strip()
