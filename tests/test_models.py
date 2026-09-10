import pytest
from pydantic import ValidationError

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)


def valid_complaint_data() -> dict:
    """Return valid data for a ComplaintCase."""

    return {
        "customer_name": "Rahul Sharma",
        "email": "rahul@example.com",
        "phone_number": "+91-9876543210",
        "complaint_category": ComplaintCategory.BILLING,
        "issue_description": "Customer was charged twice for the same order.",
        "resolution_provided": "Duplicate charge was identified and refund was initiated.",
        "complaint": True,
        "escalation_required": False,
        "supporting_document_available": True,
        "overall_case_status": CaseStatus.IN_PROGRESS,
    }


def test_complaint_case_accepts_valid_data():
    """ComplaintCase should accept valid structured data."""

    case = ComplaintCase(
        **valid_complaint_data()
    )

    assert case.customer_name == "Rahul Sharma"
    assert case.email == "rahul@example.com"
    assert case.complaint_category == ComplaintCategory.BILLING
    assert case.complaint is True
    assert case.overall_case_status == CaseStatus.IN_PROGRESS


def test_complaint_case_supports_optional_customer_details():
    """Customer name, email and phone should allow null values."""

    data = valid_complaint_data()

    data["customer_name"] = None
    data["email"] = None
    data["phone_number"] = None

    case = ComplaintCase(**data)

    assert case.customer_name is None
    assert case.email is None
    assert case.phone_number is None


def test_complaint_case_default_values():
    """Enum fields should use their documented defaults."""

    data = valid_complaint_data()

    data.pop("complaint_category")
    data.pop("overall_case_status")

    case = ComplaintCase(**data)

    assert case.complaint_category == ComplaintCategory.UNKNOWN
    assert case.overall_case_status == CaseStatus.UNKNOWN


def test_complaint_case_rejects_missing_required_fields():
    """Required fields should not be omitted."""

    data = valid_complaint_data()

    del data["issue_description"]

    with pytest.raises(ValidationError):
        ComplaintCase(**data)


def test_complaint_case_rejects_extra_fields():
    """Unexpected fields should be rejected."""

    data = valid_complaint_data()

    data["unexpected_field"] = "not allowed"

    with pytest.raises(ValidationError):
        ComplaintCase(**data)


def test_complaint_category_enum_values():
    """Complaint categories should contain the expected values."""

    assert ComplaintCategory.PRODUCT.value == "product"
    assert ComplaintCategory.SERVICE.value == "service"
    assert ComplaintCategory.BILLING.value == "billing"
    assert ComplaintCategory.DELIVERY.value == "delivery"
    assert ComplaintCategory.TECHNICAL.value == "technical"
    assert ComplaintCategory.ACCOUNT.value == "account"
    assert ComplaintCategory.SUPPORT.value == "support"
    assert ComplaintCategory.OTHER.value == "other"
    assert ComplaintCategory.UNKNOWN.value == "unknown"


def test_case_status_enum_values():
    """Case status should contain the expected values."""

    assert CaseStatus.OPEN.value == "open"
    assert CaseStatus.IN_PROGRESS.value == "in_progress"
    assert CaseStatus.RESOLVED.value == "resolved"
    assert CaseStatus.CLOSED.value == "closed"
    assert CaseStatus.ESCALATED.value == "escalated"
    assert CaseStatus.UNKNOWN.value == "unknown"