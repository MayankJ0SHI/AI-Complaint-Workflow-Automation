from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from src.models.document_schema import (
    CaseStatus,
    ComplaintCase,
    ComplaintCategory,
)
from src.processors.batch_processor import BatchProcessor
from src.services.router import CaseWorkflowResult
import json

@pytest.fixture
def complaint_case() -> ComplaintCase:
    return ComplaintCase(
        customer_name="John Doe",
        email="john@example.com",
        phone_number="9876543210",
        complaint_category=ComplaintCategory.SERVICE,
        issue_description="Customer experienced a delayed service.",
        resolution_provided="Refund initiated.",
        complaint=True,
        escalation_required=False,
        supporting_document_available=True,
        overall_case_status=CaseStatus.RESOLVED,
    )


@pytest.fixture
def workflow_result(complaint_case: ComplaintCase) -> CaseWorkflowResult:
    return CaseWorkflowResult(
        case=complaint_case,
        customer_email="Dear John,\n\nWe have resolved your complaint.",
        management_summary="Customer complaint resolved successfully.",
    )


@pytest.fixture
def parser() -> MagicMock:
    return MagicMock()


@pytest.fixture
def router() -> MagicMock:
    return MagicMock()


@pytest.fixture
def processor(
    parser: MagicMock,
    router: MagicMock,
    tmp_path: Path,
) -> BatchProcessor:
    return BatchProcessor(
        document_parser=parser,
        workflow_router=router,
        output_dir=str(tmp_path / "output"),
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_initializes_output_directories(
    processor: BatchProcessor,
) -> None:
    assert processor.structured_data_dir.exists()
    assert processor.customer_emails_dir.exists()
    assert processor.case_summaries_dir.exists()
    assert processor.final_report_path.parent.exists()


def test_output_directories_are_inside_output_directory(
    processor: BatchProcessor,
) -> None:
    assert processor.structured_data_dir.parent == processor.output_dir
    assert processor.customer_emails_dir.parent == processor.output_dir
    assert processor.case_summaries_dir.parent == processor.output_dir


# ---------------------------------------------------------------------------
# Document grouping
# ---------------------------------------------------------------------------


def test_group_documents_by_file(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(
            page_content="Page 1",
            metadata={"filename": "complaint.pdf"},
        ),
        Document(
            page_content="Page 2",
            metadata={"filename": "complaint.pdf"},
        ),
        Document(
            page_content="Another complaint",
            metadata={"filename": "complaint_002.txt"},
        ),
    ]

    grouped = processor._group_documents_by_file(documents)

    assert len(grouped) == 2
    assert "complaint.pdf" in grouped
    assert "complaint_002.txt" in grouped
    assert len(grouped["complaint.pdf"]) == 2
    assert len(grouped["complaint_002.txt"]) == 1


def test_group_documents_skips_documents_without_filename(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(
            page_content="Valid document",
            metadata={"filename": "valid.txt"},
        ),
        Document(
            page_content="Missing filename",
            metadata={},
        ),
    ]

    grouped = processor._group_documents_by_file(documents)

    assert len(grouped) == 1
    assert "valid.txt" in grouped
    assert len(grouped["valid.txt"]) == 1


def test_group_documents_returns_empty_dictionary_for_empty_input(
    processor: BatchProcessor,
) -> None:
    result = processor._group_documents_by_file([])

    assert result == {}


# ---------------------------------------------------------------------------
# Document text combination
# ---------------------------------------------------------------------------


def test_combine_document_text(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(page_content="First page"),
        Document(page_content="Second page"),
        Document(page_content="Third page"),
    ]

    result = processor._combine_document_text(documents)

    assert result == "First page\n\nSecond page\n\nThird page"


def test_combine_document_text_strips_whitespace(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(page_content="  First page  "),
        Document(page_content="\nSecond page\n"),
    ]

    result = processor._combine_document_text(documents)

    assert result == "First page\n\nSecond page"


def test_combine_document_text_ignores_empty_pages(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(page_content="First page"),
        Document(page_content=""),
        Document(page_content="   "),
        Document(page_content="Second page"),
    ]

    result = processor._combine_document_text(documents)

    assert result == "First page\n\nSecond page"


def test_combine_document_text_returns_empty_string_when_no_text(
    processor: BatchProcessor,
) -> None:
    documents = [
        Document(page_content=""),
        Document(page_content="   "),
    ]

    result = processor._combine_document_text(documents)

    assert result == ""


# ---------------------------------------------------------------------------
# Output persistence
# ---------------------------------------------------------------------------


def test_save_outputs_creates_expected_files(
    processor: BatchProcessor,
    complaint_case: ComplaintCase,
) -> None:
    result = processor._save_outputs(
        filename="complaint_001.txt",
        case=complaint_case,
        customer_email="Customer email",
        management_summary="Management summary",
    )

    structured_file = (
        processor.structured_data_dir / "complaint_001.json"
    )
    email_file = (
        processor.customer_emails_dir / "complaint_001.txt"
    )
    summary_file = (
        processor.case_summaries_dir / "complaint_001.txt"
    )

    assert structured_file.exists()
    assert email_file.exists()
    assert summary_file.exists()

    assert result == {
        "structured_data_file": "structured_data/complaint_001.json",
        "customer_email_file": "customer_emails/complaint_001.txt",
        "case_summary_file": "case_summaries/complaint_001.txt",
    }


def test_save_outputs_writes_correct_content(
    processor: BatchProcessor,
    complaint_case: ComplaintCase,
) -> None:
    processor._save_outputs(
        filename="complaint_001.txt",
        case=complaint_case,
        customer_email="Customer email",
        management_summary="Management summary",
    )

    structured_file = (
        processor.structured_data_dir / "complaint_001.json"
    )
    email_file = (
        processor.customer_emails_dir / "complaint_001.txt"
    )
    summary_file = (
        processor.case_summaries_dir / "complaint_001.txt"
    )

    structured_content = structured_file.read_text(encoding="utf-8")
    structured_data = json.loads(structured_content)

    assert structured_data["customer_name"] == "John Doe"
    assert structured_data["email"] == "john@example.com"
    assert structured_data["complaint_category"] == "service"
    assert structured_data["complaint"] is True
    assert structured_data["overall_case_status"] == "resolved"

    assert email_file.read_text(encoding="utf-8") == "Customer email"
    assert summary_file.read_text(encoding="utf-8") == "Management summary"


# ---------------------------------------------------------------------------
# Single document processing
# ---------------------------------------------------------------------------


def test_process_document_success(
    processor: BatchProcessor,
    router: MagicMock,
    workflow_result: CaseWorkflowResult,
) -> None:
    router.execute.return_value = workflow_result

    documents = [
        Document(
            page_content="Customer complaint content",
            metadata={"filename": "complaint_001.txt"},
        )
    ]

    result = processor.process_document(
        filename="complaint_001.txt",
        documents=documents,
    )

    router.execute.assert_called_once_with(
        document_text="Customer complaint content"
    )

    assert result["source_file"] == "complaint_001.txt"
    assert result["customer_name"] == "John Doe"
    assert result["email"] == "john@example.com"
    assert result["phone_number"] == "9876543210"
    assert result["complaint_category"] == "service"
    assert result["issue_description"] == (
        "Customer experienced a delayed service."
    )
    assert result["resolution_provided"] == "Refund initiated."
    assert result["complaint"] is True
    assert result["escalation_required"] is False
    assert result["supporting_document_available"] is True
    assert result["overall_case_status"] == "resolved"
    assert result["processing_status"] == "success"
    assert result["error_message"] == ""


def test_process_document_combines_multiple_pages(
    processor: BatchProcessor,
    router: MagicMock,
    workflow_result: CaseWorkflowResult,
) -> None:
    router.execute.return_value = workflow_result

    documents = [
        Document(page_content="Page one"),
        Document(page_content="Page two"),
    ]

    processor.process_document(
        filename="complaint.pdf",
        documents=documents,
    )

    router.execute.assert_called_once_with(
        document_text="Page one\n\nPage two"
    )


def test_process_document_rejects_empty_document(
    processor: BatchProcessor,
    router: MagicMock,
) -> None:
    documents = [
        Document(page_content=""),
        Document(page_content="   "),
    ]

    with pytest.raises(
        ValueError,
        match="Document contains no readable text",
    ):
        processor.process_document(
            filename="empty.txt",
            documents=documents,
        )

    router.execute.assert_not_called()


def test_process_document_propagates_workflow_error(
    processor: BatchProcessor,
    router: MagicMock,
) -> None:
    router.execute.side_effect = RuntimeError("LLM failed")

    documents = [
        Document(page_content="Complaint text"),
    ]

    with pytest.raises(RuntimeError, match="LLM failed"):
        processor.process_document(
            filename="complaint.txt",
            documents=documents,
        )


# ---------------------------------------------------------------------------
# Failed report row
# ---------------------------------------------------------------------------


def test_create_failed_report_row(
    processor: BatchProcessor,
) -> None:
    error = RuntimeError("LLM service unavailable")

    result = processor._create_failed_report_row(
        filename="complaint_001.txt",
        error=error,
    )

    assert result["source_file"] == "complaint_001.txt"
    assert result["processing_status"] == "failed"
    assert result["error_message"] == "LLM service unavailable"

    assert result["customer_name"] == ""
    assert result["email"] == ""
    assert result["phone_number"] == ""
    assert result["complaint_category"] == ""
    assert result["structured_data_file"] == ""
    assert result["customer_email_file"] == ""
    assert result["case_summary_file"] == ""


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------


def test_create_report_creates_csv(
    processor: BatchProcessor,
) -> None:
    rows = [
        {
            "source_file": "complaint_001.txt",
            "customer_name": "John Doe",
            "email": "john@example.com",
            "phone_number": "9876543210",
            "complaint_category": "service",
            "issue_description": "Delayed service",
            "resolution_provided": "Refund",
            "complaint": True,
            "escalation_required": False,
            "supporting_document_available": True,
            "overall_case_status": "resolved",
            "structured_data_file": "structured_data/complaint_001.json",
            "customer_email_file": "customer_emails/complaint_001.txt",
            "case_summary_file": "case_summaries/complaint_001.txt",
            "processing_status": "success",
            "error_message": "",
        }
    ]

    processor._create_report(rows)

    assert processor.final_report_path.exists()

    content = processor.final_report_path.read_text(
        encoding="utf-8"
    )

    assert "source_file" in content
    assert "customer_name" in content
    assert "complaint_001.txt" in content
    assert "John Doe" in content


def test_create_report_with_no_rows(
    processor: BatchProcessor,
) -> None:
    processor._create_report([])

    assert processor.final_report_path.exists()

    content = processor.final_report_path.read_text(
        encoding="utf-8"
    )

    assert "source_file" in content
    assert "processing_status" in content


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def test_process_batch_success(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
    workflow_result: CaseWorkflowResult,
) -> None:
    parser.load_documents.return_value = [
        Document(
            page_content="Complaint one",
            metadata={"filename": "complaint_001.txt"},
        ),
        Document(
            page_content="Complaint two",
            metadata={"filename": "complaint_002.txt"},
        ),
    ]

    router.execute.return_value = workflow_result

    result = processor.process_batch()

    assert result == {
        "total": 2,
        "successful": 2,
        "failed": 0,
    }

    assert router.execute.call_count == 2
    assert processor.final_report_path.exists()


def test_process_batch_continues_after_document_failure(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
    workflow_result: CaseWorkflowResult,
) -> None:
    parser.load_documents.return_value = [
        Document(
            page_content="Complaint one",
            metadata={"filename": "complaint_001.txt"},
        ),
        Document(
            page_content="Complaint two",
            metadata={"filename": "complaint_002.txt"},
        ),
    ]

    router.execute.side_effect = [
        RuntimeError("First document failed"),
        workflow_result,
    ]

    result = processor.process_batch()

    assert result == {
        "total": 2,
        "successful": 1,
        "failed": 1,
    }

    assert router.execute.call_count == 2

    report = processor.final_report_path.read_text(
        encoding="utf-8"
    )

    assert "complaint_001.txt" in report
    assert "complaint_002.txt" in report
    assert "First document failed" in report
    assert "failed" in report
    assert "success" in report


def test_process_batch_handles_all_documents_failing(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
) -> None:
    parser.load_documents.return_value = [
        Document(
            page_content="Complaint one",
            metadata={"filename": "complaint_001.txt"},
        ),
        Document(
            page_content="Complaint two",
            metadata={"filename": "complaint_002.txt"},
        ),
    ]

    router.execute.side_effect = RuntimeError("Workflow failed")

    result = processor.process_batch()

    assert result == {
        "total": 2,
        "successful": 0,
        "failed": 2,
    }

    assert processor.final_report_path.exists()

    report = processor.final_report_path.read_text(
        encoding="utf-8"
    )

    assert "complaint_001.txt" in report
    assert "complaint_002.txt" in report


def test_process_batch_with_no_documents(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
) -> None:
    parser.load_documents.return_value = []

    result = processor.process_batch()

    assert result == {
        "total": 0,
        "successful": 0,
        "failed": 0,
    }

    assert processor.final_report_path.exists()
    router.execute.assert_not_called()


def test_process_batch_groups_pages_into_one_case(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
    workflow_result: CaseWorkflowResult,
) -> None:
    parser.load_documents.return_value = [
        Document(
            page_content="Page one",
            metadata={"filename": "complaint.pdf"},
        ),
        Document(
            page_content="Page two",
            metadata={"filename": "complaint.pdf"},
        ),
    ]

    router.execute.return_value = workflow_result

    result = processor.process_batch()

    assert result == {
        "total": 1,
        "successful": 1,
        "failed": 0,
    }

    router.execute.assert_called_once_with(
        document_text="Page one\n\nPage two"
    )


def test_process_batch_ignores_documents_without_filename(
    processor: BatchProcessor,
    parser: MagicMock,
    router: MagicMock,
) -> None:
    parser.load_documents.return_value = [
        Document(
            page_content="No filename",
            metadata={},
        )
    ]

    result = processor.process_batch()

    assert result == {
        "total": 0,
        "successful": 0,
        "failed": 0,
    }

    router.execute.assert_not_called()