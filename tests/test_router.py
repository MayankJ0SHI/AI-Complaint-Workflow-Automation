from unittest.mock import MagicMock, patch

import pytest

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)
from src.services.router import (
    CaseWorkflowResult,
    CaseWorkflowRouter,
)


def create_valid_complaint_case() -> ComplaintCase:
    """Create a valid complaint case for testing."""

    return ComplaintCase(
        customer_name="Rahul Sharma",
        email="rahul@example.com",
        phone_number="+91-9876543210",
        complaint_category=ComplaintCategory.BILLING,
        issue_description="Customer was charged twice for the same order.",
        resolution_provided="Refund was initiated for the duplicate charge.",
        complaint=True,
        escalation_required=False,
        supporting_document_available=True,
        overall_case_status=CaseStatus.IN_PROGRESS,
    )


@pytest.fixture
def mock_llm():
    """Return a mocked LLM client."""

    return MagicMock()


@pytest.fixture
def router(mock_llm):
    """Create the workflow router with mocked LLM."""

    return CaseWorkflowRouter(llm=mock_llm)


def test_router_initializes_all_workflows(mock_llm):
    """Router should initialize extraction, email and summary workflows."""

    router = CaseWorkflowRouter(llm=mock_llm)

    assert router.extraction_workflow is not None
    assert router.email_workflow is not None
    assert router.summary_workflow is not None


def test_execute_runs_extraction_first(
    router,
):
    """Extraction should happen before downstream workflows."""

    case = create_valid_complaint_case()
    execution_order = []

    router.extraction_workflow.execute = MagicMock(
        side_effect=lambda document_text: (
            execution_order.append("extraction"),
            case,
        )[1]
    )

    router.email_workflow.execute = MagicMock(
        side_effect=lambda extracted_case: (
            execution_order.append("email"),
            "Customer email",
        )[1]
    )

    router.summary_workflow.execute = MagicMock(
        side_effect=lambda extracted_case: (
            execution_order.append("summary"),
            "Management summary",
        )[1]
    )

    result = router.execute(
        "Customer reported a billing issue."
    )

    assert execution_order[0] == "extraction"

    assert "email" in execution_order
    assert "summary" in execution_order


def test_execute_passes_extracted_case_to_downstream_workflows(
    router,
):
    """Both downstream workflows should receive the extracted ComplaintCase."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    router.execute(
        "Customer reported a billing issue."
    )

    router.email_workflow.execute.assert_called_once_with(case)
    router.summary_workflow.execute.assert_called_once_with(case)


def test_execute_returns_case_workflow_result(
    router,
):
    """Successful execution should return CaseWorkflowResult."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    result = router.execute(
        "Customer reported a billing issue."
    )

    assert isinstance(result, CaseWorkflowResult)

    assert result.case is case
    assert result.customer_email == "Customer email"
    assert result.management_summary == "Management summary"


def test_execute_passes_document_text_to_extraction(
    router,
):
    """Original document text should be passed to extraction."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    document_text = (
        "Rahul Sharma reported a duplicate billing charge."
    )

    router.execute(document_text)

    router.extraction_workflow.execute.assert_called_once_with(
        document_text
    )


def test_execute_propagates_extraction_error(
    router,
):
    """Extraction failures should stop the workflow."""

    router.extraction_workflow.execute = MagicMock(
        side_effect=RuntimeError(
            "Extraction failed"
        )
    )

    router.email_workflow.execute = MagicMock()
    router.summary_workflow.execute = MagicMock()

    with pytest.raises(
        RuntimeError,
        match="Extraction failed",
    ):
        router.execute(
            "Invalid complaint document"
        )

    router.email_workflow.execute.assert_not_called()
    router.summary_workflow.execute.assert_not_called()


def test_execute_propagates_email_error(
    router,
):
    """Customer email failures should propagate to the caller."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        side_effect=RuntimeError(
            "Email generation failed"
        )
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    with pytest.raises(
        RuntimeError,
        match="Email generation failed",
    ):
        router.execute(
            "Customer complaint"
        )


def test_execute_propagates_summary_error(
    router,
):
    """Management summary failures should propagate to the caller."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        side_effect=RuntimeError(
            "Summary generation failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Summary generation failed",
    ):
        router.execute(
            "Customer complaint"
        )


def test_execute_raises_when_email_returns_none(
    router,
):
    """Missing customer email should invalidate the final result."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value=None
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    with pytest.raises(
        RuntimeError,
        match="Customer email workflow completed without a result",
    ):
        router.execute(
            "Customer complaint"
        )


def test_execute_raises_when_summary_returns_none(
    router,
):
    """Missing management summary should invalidate the final result."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        return_value=None
    )

    with pytest.raises(
        RuntimeError,
        match="Management summary workflow completed without a result",
    ):
        router.execute(
            "Customer complaint"
        )


@patch(
    "src.services.router.ThreadPoolExecutor"
)
def test_execute_uses_thread_pool_for_parallel_workflows(
    mock_executor,
    router,
):
    """Email and summary generation should use a two-worker pool."""

    case = create_valid_complaint_case()

    router.extraction_workflow.execute = MagicMock(
        return_value=case
    )

    router.email_workflow.execute = MagicMock(
        return_value="Customer email"
    )

    router.summary_workflow.execute = MagicMock(
        return_value="Management summary"
    )

    real_executor = __import__(
        "concurrent.futures",
        fromlist=["ThreadPoolExecutor"],
    ).ThreadPoolExecutor

    mock_executor.side_effect = real_executor

    result = router.execute(
        "Customer complaint"
    )

    assert result.customer_email == "Customer email"
    assert result.management_summary == "Management summary"

    mock_executor.assert_called_once_with(
        max_workers=2
    )