from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.schemas import ProcessingResponse
from src.app import create_application
from src.logger.logger import get_logger

router = APIRouter(
    prefix="/api/v1",
    tags=["Document Processing"],
)

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
}

BASE_INPUT_DIR = Path("data/runtime")
BASE_OUTPUT_DIR = Path("output/runs")


@router.post(
    "/process",
    response_model=ProcessingResponse,
)
async def process_documents(
    files: list[UploadFile] = File(...),
) -> ProcessingResponse:
    """
    Upload and process complaint documents.

    Supported formats:
    - TXT
    - PDF
    - DOCX
    """

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one document must be uploaded.",
        )

    run_id = uuid4().hex

    input_dir = BASE_INPUT_DIR / run_id
    output_dir = BASE_OUTPUT_DIR / run_id

    input_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        for uploaded_file in files:
            if not uploaded_file.filename:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file must have a filename.",
                )

            filename = Path(uploaded_file.filename).name
            extension = Path(filename).suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported file type: {extension}. "
                        f"Allowed types: "
                        f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
                    ),
                )

            destination = input_dir / filename

            content = await uploaded_file.read()

            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file is empty: {filename}",
                )

            destination.write_bytes(content)

            logger.info(
                "Uploaded document | run_id=%s | file=%s | size=%d bytes",
                run_id,
                filename,
                len(content),
            )

        logger.info(
            "Starting processing run | run_id=%s | files=%d",
            run_id,
            len(files),
        )

        batch_processor = create_application(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
        )

        result = batch_processor.process_batch()

        if result["failed"] == result["total"]:
            status = "failed"
        elif result["failed"] > 0:
            status = "completed_with_errors"
        else:
            status = "completed"

        report_url = f"/api/v1/report/{run_id}"

        logger.info(
            "Processing run completed | "
            "run_id=%s | total=%d | successful=%d | failed=%d",
            run_id,
            result["total"],
            result["successful"],
            result["failed"],
        )

        return ProcessingResponse(
            run_id=run_id,
            status=status,
            total=result["total"],
            successful=result["successful"],
            failed=result["failed"],
            report_url=report_url,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Processing run failed | run_id=%s",
            run_id,
        )

        raise HTTPException(
            status_code=500,
            detail=("Document processing failed. " f"run_id={run_id}"),
        ) from exc

    finally:
        for uploaded_file in files:
            await uploaded_file.close()


@router.get(
    "/report/{run_id}",
    response_class=FileResponse,
)
def get_report(run_id: str) -> FileResponse:
    """
    Return the final CSV report for a processing run.
    """

    if not run_id.isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid run ID.",
        )

    report_path = BASE_OUTPUT_DIR / run_id / "final_report.csv"

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report not found for run_id={run_id}",
        )

    if not report_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Report is not a valid file for run_id={run_id}",
        )

    logger.info(
        "Serving final report | run_id=%s",
        run_id,
    )

    return FileResponse(
        path=report_path,
        media_type="text/csv",
        filename="final_report.csv",
    )
