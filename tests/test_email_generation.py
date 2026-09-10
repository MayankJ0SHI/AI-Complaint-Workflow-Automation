from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)
from src.models.model_schema import ModelTier
from src.services.email_generation import CustomerEmailWorkflow


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
def email_workflow(mock_llm):
    """Create customer email workflow with mocked LLM."""

    return CustomerEmailWorkflow(llm=mock_llm)


def test_execute_rejects_none_case(email_workflow):
    """None should not be accepted as a complaint case."""

    with pytest.raises(
        ValueError,
        match="Complaint case cannot be None",
    ):
        email_workflow.execute(None)


def test_execute_returns_generated_email(
    email_workflow,
    mock_llm,
):
    """Workflow should return the generated customer email."""

    mock_llm.invoke.return_value = (
        "Dear Rahul,\n\n"
        "We apologize for the duplicate charge. "
        "A refund has been initiated.\n\n"
        "Regards,\nCustomer Support"
    )

    case = create_valid_complaint_case()

    result = email_workflow.execute(case)

    assert isinstance(result, str)
    assert "Dear Rahul" in result
    assert "refund" in result


def test_execute_strips_generated_email(
    email_workflow,
    mock_llm,
):
    """Leading and trailing whitespace should be removed."""

    mock_llm.invoke.return_value = (
        "\n\n  Dear Rahul,\n\n"
        "Your refund has been initiated.\n\n  "
    )

    result = email_workflow.execute(
        create_valid_complaint_case()
    )

    assert result == (
        "Dear Rahul,\n\n"
        "Your refund has been initiated."
    )


def test_execute_calls_llm_with_basic_tier(
    email_workflow,
    mock_llm,
):
    """Customer email generation should use the BASIC model tier."""

    mock_llm.invoke.return_value = "Generated email"

    case = create_valid_complaint_case()

    email_workflow.execute(case)

    mock_llm.invoke.assert_called_once()

    call_kwargs = mock_llm.invoke.call_args.kwargs

    assert call_kwargs["tier"] == ModelTier.BASIC


def test_execute_does_not_request_structured_output(
    email_workflow,
    mock_llm,
):
    """Customer email generation should return normal text."""

    mock_llm.invoke.return_value = "Generated email"

    email_workflow.execute(
        create_valid_complaint_case()
    )

    call_kwargs = mock_llm.invoke.call_args.kwargs

    assert "response_model" not in call_kwargs


def test_execute_builds_system_and_human_messages(
    email_workflow,
    mock_llm,
):
    """Workflow should send system and human messages to the LLM."""

    mock_llm.invoke.return_value = "Generated email"

    email_workflow.execute(
        create_valid_complaint_case()
    )

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert len(messages) == 2

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)

    assert messages[0].content
    assert messages[1].content


def test_execute_includes_case_information_in_prompt(
    email_workflow,
    mock_llm,
):
    """Customer case information should be available to the prompt builder."""

    mock_llm.invoke.return_value = "Generated email"

    case = create_valid_complaint_case()

    email_workflow.execute(case)

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    human_message = messages[1]

    assert "Rahul Sharma" in human_message.content
    assert "rahul@example.com" in human_message.content
    assert "charged twice" in human_message.content
    assert "billing" in human_message.content


@patch(
    "src.services.email_generation.build_customer_email_prompt"
)
def test_execute_uses_email_prompt_builder(
    mock_build_prompt,
    email_workflow,
    mock_llm,
):
    """Workflow should use the centralized email prompt builder."""

    mock_llm.invoke.return_value = "Generated email"

    mock_build_prompt.return_value = (
        "Generated customer email prompt"
    )

    case = create_valid_complaint_case()

    email_workflow.execute(case)

    mock_build_prompt.assert_called_once()

    case_data = mock_build_prompt.call_args.args[0]

    assert "Rahul Sharma" in case_data
    assert "rahul@example.com" in case_data
    assert "billing" in case_data

    messages = mock_llm.invoke.call_args.kwargs["messages"]

    assert messages[1].content == (
        "Generated customer email prompt"
    )


def test_execute_propagates_llm_error(
    email_workflow,
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
        email_workflow.execute(
            create_valid_complaint_case()
        )