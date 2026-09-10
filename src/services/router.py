from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from src.models.document_schema import ComplaintCase
from src.llm.llm_client import LLMClient
from src.logger.logger import get_logger
from src.services.email_generation import CustomerEmailWorkflow
from src.services.extraction import ComplaintExtractionWorkflow
from src.services.summary_generation import ManagementSummaryWorkflow

logger = get_logger(__name__)


@dataclass
class CaseWorkflowResult:
    """
    Result produced after processing a single customer case.
    """

    case: ComplaintCase
    customer_email: str
    management_summary: str


class CaseWorkflowRouter:
    """
    Orchestrates the complete customer case processing workflow.

    Workflow:

        Document
            |
            v
        Extraction
            |
            v
        ComplaintCase
          /      \
         /        \
        v          v
    Customer     Management
      Email       Summary

    Email and summary generation run in parallel because both depend
    only on the extracted ComplaintCase.
    """

    def __init__(self, llm: LLMClient):
        self.extraction_workflow = ComplaintExtractionWorkflow(llm)
        self.email_workflow = CustomerEmailWorkflow(llm)
        self.summary_workflow = ManagementSummaryWorkflow(llm)

    def execute(self, document_text: str) -> CaseWorkflowResult:
        """
        Process a single customer case document.

        Args:
            document_text: Raw text extracted from the source document.

        Returns:
            CaseWorkflowResult containing the structured case,
            customer email, and management summary.

        Raises:
            ValueError: If document text is empty.
            RuntimeError: If a downstream workflow fails.
        """

        logger.info("Starting case workflow")

        # ---------------------------------------------------------
        # Step 1: Extract structured case information
        # ---------------------------------------------------------
        case = self.extraction_workflow.execute(document_text)

        logger.info(
            "Extraction successful | customer=%s",
            case.customer_name,
        )

        # ---------------------------------------------------------
        # Step 2: Generate independent outputs in parallel
        # ---------------------------------------------------------
        customer_email = None
        management_summary = None

        with ThreadPoolExecutor(max_workers=2) as executor:
            email_future = executor.submit(
                self.email_workflow.execute,
                case,
            )

            summary_future = executor.submit(
                self.summary_workflow.execute,
                case,
            )

            futures = {
                email_future: "customer_email",
                summary_future: "management_summary",
            }

            for future in as_completed(futures):
                workflow_name = futures[future]

                try:
                    result = future.result()

                    if workflow_name == "customer_email":
                        customer_email = result
                    else:
                        management_summary = result

                    logger.info(
                        "Parallel workflow completed | workflow=%s",
                        workflow_name,
                    )

                except Exception:
                    logger.exception(
                        "Parallel workflow failed | workflow=%s",
                        workflow_name,
                    )
                    raise

        # ---------------------------------------------------------
        # Step 3: Validate final workflow result
        # ---------------------------------------------------------
        if customer_email is None:
            raise RuntimeError("Customer email workflow completed without a result.")

        if management_summary is None:
            raise RuntimeError(
                "Management summary workflow completed without a result."
            )

        logger.info(
            "Case workflow completed | customer=%s",
            case.customer_name,
        )

        return CaseWorkflowResult(
            case=case,
            customer_email=customer_email,
            management_summary=management_summary,
        )
