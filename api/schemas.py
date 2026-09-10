from typing import Literal

from pydantic import BaseModel, Field


class ProcessingResponse(BaseModel):
    """Response returned after a document processing run."""

    run_id: str = Field(
        ...,
        description="Unique identifier for the processing run.",
    )

    status: Literal[
        "completed",
        "completed_with_errors",
        "failed",
    ] = Field(
        ...,
        description="Overall processing status.",
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of documents submitted.",
    )

    successful: int = Field(
        ...,
        ge=0,
        description="Number of successfully processed documents.",
    )

    failed: int = Field(
        ...,
        ge=0,
        description="Number of documents that failed processing.",
    )

    report_url: str = Field(
        ...,
        description="API endpoint for retrieving the final CSV report.",
    )
