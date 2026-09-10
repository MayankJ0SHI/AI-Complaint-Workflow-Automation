from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComplaintCategory(str, Enum):
    """
    Standardized complaint categories.

    UNKNOWN is used when the source document does not
    contain enough information to determine the category.
    """

    PRODUCT = "product"
    SERVICE = "service"
    BILLING = "billing"
    DELIVERY = "delivery"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    SUPPORT = "support"
    OTHER = "other"
    UNKNOWN = "unknown"


class CaseStatus(str, Enum):
    """
    Overall status of the customer case.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"
    UNKNOWN = "unknown"


class ComplaintCase(BaseModel):
    """
    Structured representation of a customer complaint/case
    extracted from a source document.

    This model acts as the contract between the LLM extraction
    workflow and downstream workflows such as email generation,
    management summaries, and reporting.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    customer_name: str | None = Field(
        default=None,
        description=(
            "Full name of the customer. "
            "Return null if the customer name is not present "
            "or cannot be determined from the source document."
        ),
    )

    email: str | None = Field(
        default=None,
        description=(
            "Customer email address exactly as stated in the "
            "source document. Return null if unavailable."
        ),
    )

    phone_number: str | None = Field(
        default=None,
        description=(
            "Customer phone number exactly as stated in the "
            "source document. Return null if unavailable."
        ),
    )

    complaint_category: ComplaintCategory = Field(
        default=ComplaintCategory.UNKNOWN,
        description=(
            "Category of the customer's complaint. "
            "Choose the closest applicable category based only "
            "on information present in the source document."
        ),
    )

    issue_description: str = Field(
        description=(
            "Concise description of the customer's reported issue. "
            "Do not add information that is not present in the "
            "source document."
        ),
    )

    resolution_provided: str = Field(
        description=(
            "Description of any resolution, corrective action, "
            "or assistance already provided to the customer. "
            "If no resolution was provided, state that no resolution "
            "was documented."
        ),
    )

    complaint: bool = Field(
        description=(
            "Whether the document represents a customer complaint. "
            "Return true only when the source document indicates "
            "a complaint."
        ),
    )

    escalation_required: bool = Field(
        description=(
            "Whether escalation is required based on explicit "
            "information or instructions in the source document. "
            "Do not infer escalation solely from the severity of "
            "the issue."
        ),
    )

    supporting_document_available: bool = Field(
        description=(
            "Whether the source document indicates that supporting "
            "documents, attachments, evidence, or related files "
            "are available."
        ),
    )

    overall_case_status: CaseStatus = Field(
        default=CaseStatus.UNKNOWN,
        description=(
            "Current overall status of the customer case based "
            "only on the source document."
        ),
    )
