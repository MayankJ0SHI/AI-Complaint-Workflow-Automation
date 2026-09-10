from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.parser.document_parser import DocumentParser


def test_document_parser_rejects_missing_folder(tmp_path):
    """DocumentParser should raise FileNotFoundError for a missing folder."""

    missing_folder = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        DocumentParser(folder_path=str(missing_folder))


def test_document_parser_detects_supported_files(tmp_path):
    """DocumentParser should discover TXT, PDF and DOCX files."""

    (tmp_path / "complaint.txt").write_text(
        "Customer is facing a billing issue.",
        encoding="utf-8",
    )

    (tmp_path / "complaint.pdf").touch()
    (tmp_path / "complaint.docx").touch()
    (tmp_path / "unsupported.csv").write_text(
        "some,data",
        encoding="utf-8",
    )

    parser = DocumentParser(folder_path=str(tmp_path))

    filenames = {
        path.name
        for path in parser.filepaths
    }

    assert filenames == {
        "complaint.txt",
        "complaint.pdf",
        "complaint.docx",
    }


def test_is_valid_file_accepts_supported_extensions(tmp_path):
    """Supported document extensions should be recognized."""

    parser = DocumentParser(folder_path=str(tmp_path))

    txt_file = tmp_path / "test.txt"
    pdf_file = tmp_path / "test.pdf"
    docx_file = tmp_path / "test.docx"

    txt_file.touch()
    pdf_file.touch()
    docx_file.touch()

    assert parser._is_valid_file(txt_file) is True
    assert parser._is_valid_file(pdf_file) is True
    assert parser._is_valid_file(docx_file) is True


def test_is_valid_file_rejects_unsupported_extension(tmp_path):
    """Unsupported file extensions should be rejected."""

    parser = DocumentParser(folder_path=str(tmp_path))

    csv_file = tmp_path / "test.csv"
    csv_file.touch()

    assert parser._is_valid_file(csv_file) is False


def test_is_valid_file_rejects_directories(tmp_path):
    """Directories should not be treated as documents."""

    parser = DocumentParser(folder_path=str(tmp_path))

    directory = tmp_path / "documents"
    directory.mkdir()

    assert parser._is_valid_file(directory) is False


def test_get_loader_for_txt_file(tmp_path):
    """TXT files should use TextLoader."""

    txt_file = tmp_path / "complaint.txt"
    txt_file.write_text(
        "Customer complaint.",
        encoding="utf-8",
    )

    parser = DocumentParser(folder_path=str(tmp_path))

    loader = parser._get_loader_for_file(txt_file)

    assert loader is not None
    assert loader.__class__.__name__ == "TextLoader"


def test_get_loader_for_pdf_file(tmp_path):
    """PDF files should use PyPDFLoader."""

    pdf_file = tmp_path / "complaint.pdf"
    pdf_file.touch()

    parser = DocumentParser(folder_path=str(tmp_path))

    loader = parser._get_loader_for_file(pdf_file)

    assert loader is not None
    assert loader.__class__.__name__ == "PyPDFLoader"


def test_get_loader_for_docx_file(tmp_path):
    """DOCX files should use Docx2txtLoader."""

    docx_file = tmp_path / "complaint.docx"
    docx_file.touch()

    parser = DocumentParser(folder_path=str(tmp_path))

    loader = parser._get_loader_for_file(docx_file)

    assert loader is not None
    assert loader.__class__.__name__ == "Docx2txtLoader"


def test_get_loader_for_unsupported_file_returns_none(tmp_path):
    """Unsupported files should not receive a document loader."""

    csv_file = tmp_path / "complaint.csv"
    csv_file.touch()

    parser = DocumentParser(folder_path=str(tmp_path))

    loader = parser._get_loader_for_file(csv_file)

    assert loader is None


def test_load_documents_from_txt_file(tmp_path):
    """TXT documents should be loaded with enriched metadata."""

    txt_file = tmp_path / "complaint_001.txt"

    content = (
        "Customer Rahul Sharma reported that he was charged twice "
        "for the same order."
    )

    txt_file.write_text(
        content,
        encoding="utf-8",
    )

    parser = DocumentParser(folder_path=str(tmp_path))

    documents = parser.load_documents()

    assert len(documents) == 1

    document = documents[0]

    assert isinstance(document, Document)
    assert document.page_content == content

    assert document.metadata["filename"] == "complaint_001.txt"
    assert document.metadata["file_type"] == ".txt"
    assert document.metadata["source"] == str(txt_file)
    assert document.metadata["folder"] == str(tmp_path)
    assert document.metadata["doc_length"] == len(content)


def test_load_documents_supports_multiple_documents(tmp_path):
    """Multiple valid TXT documents should all be loaded."""

    first_file = tmp_path / "complaint_001.txt"
    second_file = tmp_path / "complaint_002.txt"

    first_file.write_text(
        "First customer complaint.",
        encoding="utf-8",
    )

    second_file.write_text(
        "Second customer complaint.",
        encoding="utf-8",
    )

    parser = DocumentParser(folder_path=str(tmp_path))

    documents = parser.load_documents()

    assert len(documents) == 2

    filenames = {
        document.metadata["filename"]
        for document in documents
    }

    assert filenames == {
        "complaint_001.txt",
        "complaint_002.txt",
    }


def test_load_documents_returns_empty_list_when_no_valid_files(tmp_path):
    """An empty input directory should return an empty document list."""

    parser = DocumentParser(folder_path=str(tmp_path))

    documents = parser.load_documents()

    assert documents == []


def test_load_documents_continues_when_one_file_fails(tmp_path):
    """A failed document should not prevent other documents from loading."""

    valid_file = tmp_path / "valid.txt"
    failing_file = tmp_path / "failing.txt"

    valid_file.write_text(
        "Valid complaint.",
        encoding="utf-8",
    )

    failing_file.write_text(
        "This document will fail.",
        encoding="utf-8",
    )

    parser = DocumentParser(folder_path=str(tmp_path))

    valid_document = Document(
        page_content="Valid complaint.",
        metadata={},
    )

    mock_loader = MagicMock()
    mock_loader.load.side_effect = [
        [valid_document],
        RuntimeError("Simulated loader failure"),
    ]

    with patch.object(
        parser,
        "_get_loader_for_file",
        return_value=mock_loader,
    ):
        documents = parser.load_documents()

    assert len(documents) == 1
    assert documents[0].page_content == "Valid complaint."