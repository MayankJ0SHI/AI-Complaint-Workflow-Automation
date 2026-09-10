import csv
from collections import defaultdict
from pathlib import Path

from langchain_core.documents import Document

from src.logger.logger import get_logger
from src.models.document_schema import ComplaintCase
from src.parser.document_parser import DocumentParser
from src.services.router import CaseWorkflowRouter

logger = get_logger(__name__)


class BatchProcessor:
    """
    Process all supported documents through the complete AI workflow.

    Workflow:

        Files
          ↓
        DocumentParser
          ↓
        Group pages by source file
          ↓
        CaseWorkflowRouter
          ↓
        Structured Case + Customer Email + Management Summary
          ↓
        Output files + final_report.csv
    """

    REPORT_FIELDS = [
        "source_file",
        "customer_name",
        "email",
        "phone_number",
        "complaint_category",
        "issue_description",
        "resolution_provided",
        "complaint",
        "escalation_required",
        "supporting_document_available",
        "overall_case_status",
        "structured_data_file",
        "customer_email_file",
        "case_summary_file",
        "processing_status",
        "error_message",
    ]

    def __init__(
        self,
        document_parser: DocumentParser,
        workflow_router: CaseWorkflowRouter,
        output_dir: str = "output",
    ) -> None:
        """
        Initialize the batch processor.

        Args:
            document_parser:
                Parser responsible for loading source documents.

            workflow_router:
                Router responsible for executing the complete
                complaint processing workflow.

            output_dir:
                Directory where all generated outputs are stored.
        """

        self.document_parser = document_parser
        self.workflow_router = workflow_router

        self.output_dir = Path(output_dir)

        self.structured_data_dir = self.output_dir / "structured_data"
        self.customer_emails_dir = self.output_dir / "customer_emails"
        self.case_summaries_dir = self.output_dir / "case_summaries"

        self.final_report_path = self.output_dir / "final_report.csv"

        self._create_output_directories()

    # ------------------------------------------------------------------
    # Output directories
    # ------------------------------------------------------------------

    def _create_output_directories(self) -> None:
        """Create all required output directories."""

        directories = [
            self.structured_data_dir,
            self.customer_emails_dir,
            self.case_summaries_dir,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        logger.info(
            "Output directories initialized | path=%s",
            self.output_dir,
        )

    # ------------------------------------------------------------------
    # Document grouping
    # ------------------------------------------------------------------

    def _group_documents_by_file(
        self,
        documents: list[Document],
    ) -> dict[str, list[Document]]:
        """
        Group LangChain documents by source filename.

        A multi-page PDF may produce multiple Document objects.
        All pages belonging to the same source file are grouped
        together and processed as one customer case.

        Args:
            documents:
                Documents returned by DocumentParser.

        Returns:
            Dictionary mapping source filenames to their pages.
        """

        grouped_documents: dict[str, list[Document]] = defaultdict(list)

        for document in documents:
            filename = document.metadata.get("filename")

            if not filename:
                logger.warning(
                    "Document does not contain filename metadata. " "Skipping document."
                )
                continue

            grouped_documents[filename].append(document)

        logger.info(
            "Documents grouped by source file | files=%d",
            len(grouped_documents),
        )

        return dict(grouped_documents)

    # ------------------------------------------------------------------
    # Document text
    # ------------------------------------------------------------------

    @staticmethod
    def _combine_document_text(
        documents: list[Document],
    ) -> str:
        """
        Combine all pages of a source document into one text.

        Args:
            documents:
                Pages/documents belonging to one source file.

        Returns:
            Combined document text.
        """

        return "\n\n".join(
            document.page_content.strip()
            for document in documents
            if document.page_content and document.page_content.strip()
        )

    # ------------------------------------------------------------------
    # Output persistence
    # ------------------------------------------------------------------

    def _save_outputs(
        self,
        filename: str,
        case: ComplaintCase,
        customer_email: str,
        management_summary: str,
    ) -> dict[str, str]:
        """
        Save generated workflow outputs.

        Args:
            filename:
                Original source filename.

            case:
                Structured complaint case.

            customer_email:
                Generated customer-facing email.

            management_summary:
                Generated management summary.

        Returns:
            Relative paths of all generated output files.
        """

        base_name = Path(filename).stem

        structured_output = self.structured_data_dir / f"{base_name}.json"

        email_output = self.customer_emails_dir / f"{base_name}.txt"

        summary_output = self.case_summaries_dir / f"{base_name}.txt"

        # Structured complaint data
        structured_output.write_text(
            case.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Customer email
        email_output.write_text(
            customer_email,
            encoding="utf-8",
        )

        # Management summary
        summary_output.write_text(
            management_summary,
            encoding="utf-8",
        )

        logger.info(
            "Output files saved | file=%s",
            filename,
        )

        return {
            "structured_data_file": structured_output.relative_to(
                self.output_dir
            ).as_posix(),
            "customer_email_file": email_output.relative_to(self.output_dir).as_posix(),
            "case_summary_file": summary_output.relative_to(self.output_dir).as_posix(),
        }

    # ------------------------------------------------------------------
    # Single document processing
    # ------------------------------------------------------------------

    def process_document(
        self,
        filename: str,
        documents: list[Document],
    ) -> dict[str, str]:
        """
        Process one source document through the complete workflow.

        Args:
            filename:
                Original source filename.

            documents:
                All pages/documents belonging to the source file.

        Returns:
            A dictionary representing one final-report CSV row.

        Raises:
            ValueError:
                If the document contains no readable text.
            Exception:
                Any exception raised by the workflow is propagated
                to the batch processor.
        """

        logger.info(
            "Processing document | file=%s | pages=%d",
            filename,
            len(documents),
        )

        document_text = self._combine_document_text(documents)

        if not document_text:
            raise ValueError(f"Document contains no readable text: {filename}")

        # --------------------------------------------------------------
        # Execute complete AI workflow
        # --------------------------------------------------------------

        result = self.workflow_router.execute(
            document_text=document_text,
        )

        case = result.case

        # --------------------------------------------------------------
        # Save generated outputs
        # --------------------------------------------------------------

        output_files = self._save_outputs(
            filename=filename,
            case=case,
            customer_email=result.customer_email,
            management_summary=result.management_summary,
        )

        # --------------------------------------------------------------
        # Create final report row
        # --------------------------------------------------------------

        report_row = {
            "source_file": filename,
            "customer_name": case.customer_name,
            "email": case.email,
            "phone_number": case.phone_number,
            "complaint_category": (case.complaint_category.value),
            "issue_description": case.issue_description,
            "resolution_provided": case.resolution_provided,
            "complaint": case.complaint,
            "escalation_required": (case.escalation_required),
            "supporting_document_available": (case.supporting_document_available),
            "overall_case_status": (case.overall_case_status.value),
            "structured_data_file": (output_files["structured_data_file"]),
            "customer_email_file": (output_files["customer_email_file"]),
            "case_summary_file": (output_files["case_summary_file"]),
            "processing_status": "success",
            "error_message": "",
        }

        logger.info(
            "Document processing completed | file=%s | status=success",
            filename,
        )

        return report_row

    # ------------------------------------------------------------------
    # Failed document report row
    # ------------------------------------------------------------------

    @staticmethod
    def _create_failed_report_row(
        filename: str,
        error: Exception,
    ) -> dict[str, str]:
        """
        Create a final-report row for a failed document.

        Keeping failed documents in the final report allows the batch
        to continue processing while preserving failure information.
        """

        return {
            "source_file": filename,
            "customer_name": "",
            "email": "",
            "phone_number": "",
            "complaint_category": "",
            "issue_description": "",
            "resolution_provided": "",
            "complaint": "",
            "escalation_required": "",
            "supporting_document_available": "",
            "overall_case_status": "",
            "structured_data_file": "",
            "customer_email_file": "",
            "case_summary_file": "",
            "processing_status": "failed",
            "error_message": str(error),
        }

    # ------------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------------

    def _create_report(
        self,
        report_rows: list[dict[str, str]],
    ) -> None:
        """
        Create the consolidated final_report.csv.

        Each processed source document corresponds to one row.
        """

        self.final_report_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.final_report_path.open(
            mode="w",
            newline="",
            encoding="utf-8",
        ) as csv_file:

            writer = csv.DictWriter(
                csv_file,
                fieldnames=self.REPORT_FIELDS,
                extrasaction="ignore",
            )

            writer.writeheader()
            writer.writerows(report_rows)

        logger.info(
            "Final report created | path=%s | rows=%d",
            self.final_report_path,
            len(report_rows),
        )

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def process_batch(self) -> dict[str, int]:
        """
        Process every supported document.

        Each source document is isolated from other documents.
        If one document fails, processing continues for the
        remaining documents.

        Returns:
            Batch processing statistics containing:

                total:
                    Total number of source documents.

                successful:
                    Number of successfully processed documents.

                failed:
                    Number of failed documents.
        """

        logger.info("Starting batch document processing")

        # --------------------------------------------------------------
        # Load documents
        # --------------------------------------------------------------

        documents = self.document_parser.load_documents()

        if not documents:
            logger.warning("No documents available for processing.")

            self._create_report([])

            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
            }

        # --------------------------------------------------------------
        # Group pages belonging to the same source file
        # --------------------------------------------------------------

        grouped_documents = self._group_documents_by_file(documents)

        total = len(grouped_documents)
        successful = 0
        failed = 0

        report_rows: list[dict[str, str]] = []

        logger.info(
            "Batch ready | source_files=%d",
            total,
        )

        # --------------------------------------------------------------
        # Process each source document independently
        # --------------------------------------------------------------

        for filename, file_documents in grouped_documents.items():

            try:
                report_row = self.process_document(
                    filename=filename,
                    documents=file_documents,
                )

                report_rows.append(report_row)
                successful += 1

            except Exception as exc:
                failed += 1

                logger.exception(
                    "Document processing failed | file=%s",
                    filename,
                )

                report_rows.append(
                    self._create_failed_report_row(
                        filename=filename,
                        error=exc,
                    )
                )

        # --------------------------------------------------------------
        # Generate consolidated report
        # --------------------------------------------------------------

        self._create_report(report_rows)

        logger.info(
            "Batch processing completed | " "total=%d | successful=%d | failed=%d",
            total,
            successful,
            failed,
        )

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
        }
