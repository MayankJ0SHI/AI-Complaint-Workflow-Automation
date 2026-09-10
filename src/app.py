from src.llm.llm_client import LLMClient
from src.parser.document_parser import DocumentParser
from src.processors.batch_processor import BatchProcessor
from src.services.router import CaseWorkflowRouter
from src.logger.logger import get_logger

logger = get_logger(__name__)


def create_application(
    input_dir: str,
    output_dir: str = "output",
) -> BatchProcessor:
    """
    Create and configure the document processing application.

    Args:
        input_dir: Directory containing input documents.
        output_dir: Directory where generated outputs are stored.

    Returns:
        Configured BatchProcessor instance.
    """

    logger.info(
        "Initializing AI document processing application | "
        "input_dir=%s | output_dir=%s",
        input_dir,
        output_dir,
    )

    # ---------------------------------------------------------
    # LLM client
    # ---------------------------------------------------------
    llm_client = LLMClient()

    # ---------------------------------------------------------
    # Document parser
    # ---------------------------------------------------------
    document_parser = DocumentParser(
        folder_path=input_dir,
    )

    # ---------------------------------------------------------
    # Workflow router
    #
    # The router internally initializes:
    #   - ComplaintExtractionWorkflow
    #   - CustomerEmailWorkflow
    #   - ManagementSummaryWorkflow
    # ---------------------------------------------------------
    workflow_router = CaseWorkflowRouter(
        llm=llm_client,
    )

    # ---------------------------------------------------------
    # Batch processor
    # ---------------------------------------------------------
    batch_processor = BatchProcessor(
        document_parser=document_parser,
        workflow_router=workflow_router,
        output_dir=output_dir,
    )

    logger.info("AI document processing application initialized successfully")

    return batch_processor
