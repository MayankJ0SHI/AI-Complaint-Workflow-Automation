from fastapi import FastAPI

from api.routes.processing import router as processing_router
from src.logger.logger import get_logger

logger = get_logger(__name__)


app = FastAPI(
    title="AI Document Processing API",
    description=(
        "GenAI-powered document processing and " "business workflow automation API."
    ),
    version="1.0.0",
)


app.include_router(processing_router)


@app.get(
    "/health",
    tags=["Health"],
)
def health_check() -> dict[str, str]:
    """Check whether the API service is running."""
    return {
        "status": "healthy",
        "service": "ai-document-processing-api",
    }


logger.info("FastAPI application initialized")
