from src.app import create_application
from src.config.settings import settings
from src.logger.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting AI document processing application")

    batch_processor = create_application(
        input_dir=settings.input_dir,
        output_dir=settings.output_dir,
    )

    result = batch_processor.process_batch()

    print("\n" + "=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total documents : {result['total']}")
    print(f"Successful      : {result['successful']}")
    print(f"Failed          : {result['failed']}")
    print(f"Output directory: {settings.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()