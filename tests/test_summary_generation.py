from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)
from src.models.model_schema import ModelTier
from src.services.summary_generation import ManagementSummaryWorkflow


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
def summary_workflow(mock_llm):
    """Create management summary workflow with mocked LLM."""

    return ManagementSummaryWorkflow(llm=mock_llm)


def test_execute_rejects_none_case(summary_workflow):
    """None should not be accepted as a complaint case."""

    with pytest.raises(
        ValueError,
        match="Complaint case cannot be None",
    ):
        summary_workflow.execute(None)


def test_execute_returns_generated_summary(
    summary_workflow,
    mock_llm,
):
    """Workflow should return the generated management summary."""

    mock_llm.invoke.return_value = (
        "Billing complaint involving a duplicate charge. "
        "Refund initiated and case remains in progress."
    )

    result = summary_workflow.execute(
        create_valid_complaint_case()
    )

    assert isinstance(result, str)
    assert "Billing complaint" in result
    assert "Refund initiated" in result


def test_execute_strips_generated_summary(
    summary_workflow,
    mock_llm,
):
    """Leading and trailing whitespace should be removed."""

    mock_llm.invoke.return_value = (
        "\n\n  Billing complaint summary.\n\n  "
    )

    result = summary_workflow.execute(
        create_valid_complaint_case()
    )

    assert result == "Billing complaint summary."


def test_execute_calls_llm_with_basic_tier(
    summary_workflow,
    mock_llm,
):
    """Management summary generation should use the BASIC model tier."""

    mock_llm.invoke.return_value = "Generated summary"

    summary_workflow.execute(
        create_valid_complaint_case()
    )

    mock_llm.invoke.assert_called_once()

    call_kwargs = mock_llm.invoke.call_args.kwargs

    assert call_kwargs["tier"] == ModelTier.BASIC


def test_execute_does_not_request_structured_output(
    summary_workflow,
    mock_llm,
):
    """Management summaries should be generated as normal text."""

    mock_llm.invoke.return_value = "Generated summary"

    summary_workflow.execute(
        create_valid_complaint_case()
    )

    call_kwargs = mock_llm.invoke.call_args.kwargs

    assert "response_model" not in call_kwargs


def test_execute_builds_system_and_human_messages(
    summary_workflow,
    mock_llm,
):
    """Workflow should send system and human messages to the LLM."""

    mock_llm.invoke.return_value = "Generated summary"

    summary_workflow.execute(
        create_valid_complaint_case()
    )

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert len(messages) == 2

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)

    assert messages[0].content
    assert messages[1].content


def test_execute_includes_case_information_in_prompt(
    summary_workflow,
    mock_llm,
):
    """Structured case information should be included in the prompt."""

    mock_llm.invoke.return_value = "Generated summary"

    summary_workflow.execute(
        create_valid_complaint_case()
    )

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    human_message = messages[1]

    assert "Rahul Sharma" in human_message.content
    assert "rahul@example.com" in human_message.content
    assert "charged twice" in human_message.content
    assert "billing" in human_message.content
    assert "in_progress" in human_message.content


@patch(
    "src.services.summary_generation.build_management_summary_prompt"
)
def test_execute_uses_summary_prompt_builder(
    mock_build_prompt,
    summary_workflow,
    mock_llm,
):
    """Workflow should use the centralized summary prompt builder."""

    mock_llm.invoke.return_value = "Generated summary"

    mock_build_prompt.return_value = (
        "Generated management summary prompt"
    )

    case = create_valid_complaint_case()

    summary_workflow.execute(case)

    mock_build_prompt.assert_called_once()

    case_data = mock_build_prompt.call_args.args[0]

    assert "Rahul Sharma" in case_data
    assert "rahul@example.com" in case_data
    assert "billing" in case_data

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert messages[1].content == (
        "Generated management summary prompt"
    )


def test_execute_propagates_llm_error(
    summary_workflow,
    mock_llm,
):
    """LLM errors should propagate to the caller."""

    mock_llm.invoke.side_effect = RuntimeError(
        "LLM service unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="LLM service unavailable",
    ):
        summary_workflow.execute(
            create_valid_complaint_case()
        )