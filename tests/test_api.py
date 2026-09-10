import csv
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "ai-document-processing-api",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/process - validation
# ---------------------------------------------------------------------------


def test_process_requires_at_least_one_file() -> None:
    response = client.post("/api/v1/process")

    assert response.status_code == 422


def test_process_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.csv",
                b"customer,complaint\nJohn,Delayed service",
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported file type: .csv" in response.json()["detail"]


def test_process_rejects_empty_file() -> None:
    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "empty.txt",
                b"",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Uploaded file is empty: empty.txt"
    )


# ---------------------------------------------------------------------------
# POST /api/v1/process - successful processing
# ---------------------------------------------------------------------------


@patch("api.routes.processing.create_application")
def test_process_documents_success(
    mock_create_application: MagicMock,
    tmp_path: Path,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.txt",
                b"Customer John has a delayed service complaint.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"
    assert data["total"] == 1
    assert data["successful"] == 1
    assert data["failed"] == 0

    assert len(data["run_id"]) == 32
    assert data["run_id"].isalnum()

    assert data["report_url"].startswith(
        "/api/v1/report/"
    )

    mock_create_application.assert_called_once()
    mock_batch_processor.process_batch.assert_called_once()


@patch("api.routes.processing.create_application")
def test_process_documents_multiple_files(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 2,
        "successful": 2,
        "failed": 0,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files=[
            (
                "files",
                (
                    "complaint_001.txt",
                    b"Complaint one",
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "complaint_002.txt",
                    b"Complaint two",
                    "text/plain",
                ),
            ),
        ],
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert data["status"] == "completed"

    mock_batch_processor.process_batch.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/process - partial/all failures
# ---------------------------------------------------------------------------


@patch("api.routes.processing.create_application")
def test_process_documents_completed_with_errors(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 3,
        "successful": 2,
        "failed": 1,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.txt",
                b"Complaint content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed_with_errors"
    assert data["total"] == 3
    assert data["successful"] == 2
    assert data["failed"] == 1


@patch("api.routes.processing.create_application")
def test_process_documents_all_failed(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 2,
        "successful": 0,
        "failed": 2,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.txt",
                b"Complaint content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "failed"
    assert data["total"] == 2
    assert data["successful"] == 0
    assert data["failed"] == 2


# ---------------------------------------------------------------------------
# POST /api/v1/process - application failure
# ---------------------------------------------------------------------------


@patch("api.routes.processing.create_application")
def test_process_documents_returns_500_on_application_error(
    mock_create_application: MagicMock,
) -> None:
    mock_create_application.side_effect = RuntimeError(
        "Application initialization failed"
    )

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.txt",
                b"Complaint content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 500

    detail = response.json()["detail"]

    assert detail.startswith("Document processing failed.")
    assert "run_id=" in detail


@patch("api.routes.processing.create_application")
def test_process_documents_returns_500_on_batch_error(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.side_effect = RuntimeError(
        "Batch processing failed"
    )

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.txt",
                b"Complaint content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 500

    detail = response.json()["detail"]

    assert detail.startswith("Document processing failed.")
    assert "run_id=" in detail


# ---------------------------------------------------------------------------
# File upload validation
# ---------------------------------------------------------------------------


@patch("api.routes.processing.create_application")
def test_process_accepts_pdf(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.pdf",
                b"%PDF-1.4 fake pdf content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200


@patch("api.routes.processing.create_application")
def test_process_accepts_docx(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "complaint.docx",
                b"fake docx content",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Filename handling / security
# ---------------------------------------------------------------------------


@patch("api.routes.processing.create_application")
def test_process_sanitizes_filename(
    mock_create_application: MagicMock,
) -> None:
    mock_batch_processor = MagicMock()

    mock_batch_processor.process_batch.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
    }

    mock_create_application.return_value = mock_batch_processor

    response = client.post(
        "/api/v1/process",
        files={
            "files": (
                "../../malicious.txt",
                b"Complaint content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200

    run_id = response.json()["run_id"]

    input_directory = (
        Path("data/runtime") / run_id
    )

    assert (input_directory / "malicious.txt").exists()
    assert not (input_directory / "../../malicious.txt").exists()


# ---------------------------------------------------------------------------
# GET /api/v1/report/{run_id}
# ---------------------------------------------------------------------------


def test_get_report_invalid_run_id() -> None:
    response = client.get(
        "/api/v1/report/invalid-run-id!"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid run ID."


def test_get_report_not_found() -> None:
    response = client.get(
        "/api/v1/report/doesnotexist123"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Report not found for run_id=doesnotexist123"
    )


def test_get_report_success(
    tmp_path: Path,
) -> None:
    run_id = "test123456"

    report_directory = (
        Path("output/runs") / run_id
    )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        report_directory / "final_report.csv"
    )

    report_path.write_text(
        "source_file,processing_status\n"
        "complaint.txt,success\n",
        encoding="utf-8",
    )

    try:
        response = client.get(
            f"/api/v1/report/{run_id}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "text/csv"
        )
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="final_report.csv"'
        )

        assert "complaint.txt" in response.text
        assert "success" in response.text

    finally:
        if report_path.exists():
            report_path.unlink()

        if report_directory.exists():
            report_directory.rmdir()


def test_get_report_rejects_directory_as_report(
    tmp_path: Path,
) -> None:
    run_id = "directorytest123"

    report_directory = (
        Path("output/runs") / run_id
    )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        report_directory / "final_report.csv"
    )

    report_path.mkdir()

    try:
        response = client.get(
            f"/api/v1/report/{run_id}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            f"Report is not a valid file for run_id={run_id}"
        )

    finally:
        report_path.rmdir()
        report_directory.rmdir()