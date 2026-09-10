from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)
from src.models.model_schema import ModelTier
from src.services.extraction import ComplaintExtractionWorkflow


def create_valid_complaint_case() -> ComplaintCase:
    """Create a valid ComplaintCase for testing."""

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
def extraction_workflow(mock_llm):
    """Create extraction workflow with a mocked LLM."""

    return ComplaintExtractionWorkflow(llm=mock_llm)


def test_execute_rejects_empty_document_text(extraction_workflow):
    """Empty document text should raise ValueError."""

    with pytest.raises(
        ValueError,
        match="Document text cannot be empty",
    ):
        extraction_workflow.execute("")


def test_execute_rejects_whitespace_only_document(extraction_workflow):
    """Whitespace-only document text should raise ValueError."""

    with pytest.raises(
        ValueError,
        match="Document text cannot be empty",
    ):
        extraction_workflow.execute("   \n\t  ")


def test_execute_returns_complaint_case(
    extraction_workflow,
    mock_llm,
):
    """Successful extraction should return a ComplaintCase."""

    expected_case = create_valid_complaint_case()

    mock_llm.invoke.return_value = expected_case

    document_text = (
        "Rahul Sharma reported that he was charged twice "
        "for the same order."
    )

    result = extraction_workflow.execute(document_text)

    assert isinstance(result, ComplaintCase)
    assert result == expected_case


def test_execute_calls_llm_with_expected_tier_and_schema(
    extraction_workflow,
    mock_llm,
):
    """Extraction should request structured ComplaintCase output."""

    expected_case = create_valid_complaint_case()

    mock_llm.invoke.return_value = expected_case

    document_text = "Customer reported a billing issue."

    extraction_workflow.execute(document_text)

    mock_llm.invoke.assert_called_once()

    call_kwargs = mock_llm.invoke.call_args.kwargs

    assert call_kwargs["tier"] == ModelTier.GENERIC
    assert call_kwargs["response_model"] is ComplaintCase


def test_execute_builds_system_and_human_messages(
    extraction_workflow,
    mock_llm,
):
    """Extraction should send system and human messages to the LLM."""

    mock_llm.invoke.return_value = create_valid_complaint_case()

    document_text = "Customer reported a billing issue."

    extraction_workflow.execute(document_text)

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert len(messages) == 2

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)

    assert messages[0].content
    assert messages[1].content

    assert document_text in messages[1].content


def test_execute_passes_document_text_to_extraction_prompt(
    extraction_workflow,
    mock_llm,
):
    """The original document text should be included in the LLM prompt."""

    mock_llm.invoke.return_value = create_valid_complaint_case()

    document_text = (
        "Customer Priya reported that her package "
        "was delivered to the wrong address."
    )

    extraction_workflow.execute(document_text)

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    human_message = messages[1]

    assert document_text in human_message.content


def test_execute_returns_exact_llm_result(
    extraction_workflow,
    mock_llm,
):
    """The workflow should return the structured result from the LLM unchanged."""

    expected_case = create_valid_complaint_case()

    mock_llm.invoke.return_value = expected_case

    result = extraction_workflow.execute(
        "Customer reported a duplicate billing charge."
    )

    assert result is expected_case


def test_execute_propagates_llm_errors(
    extraction_workflow,
    mock_llm,
):
    """LLM failures should be propagated to the caller."""

    mock_llm.invoke.side_effect = RuntimeError(
        "LLM service unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="LLM service unavailable",
    ):
        extraction_workflow.execute(
            "Customer reported a billing issue."
        )


@patch(
    "src.services.extraction.build_extraction_prompt"
)
def test_execute_uses_extraction_prompt_builder(
    mock_build_prompt,
    extraction_workflow,
    mock_llm,
):
    """The workflow should use the centralized extraction prompt builder."""

    expected_case = create_valid_complaint_case()

    mock_llm.invoke.return_value = expected_case

    mock_build_prompt.return_value = (
        "Generated extraction prompt"
    )

    document_text = "Original complaint document."

    extraction_workflow.execute(document_text)

    mock_build_prompt.assert_called_once_with(
        document_text
    )

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert messages[1].content == "Generated extraction prompt"