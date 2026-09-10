import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler


class Logger:
    """
    Centralized application logger.

    Logs are written to:
        <project_root>/logs/YYYY_MM_DD.log

    Logs are written to both:
        1. Console
        2. Rotating log file

    File rotation:
        - Maximum file size: 5 MB
        - Backup files: 5
    """

    LOG_DIR_NAME = "logs"
    MAX_BYTES = 5 * 1024 * 1024
    BACKUP_COUNT = 5
    LOG_LEVEL = logging.INFO

    CONSOLE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

    FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

        self.logger.setLevel(self.LOG_LEVEL)
        self.logger.propagate = False

        self._configure()

    @staticmethod
    def _get_project_root() -> Path:
        """
        Returns the project root directory.

        Assumes this file is located at:

            project_root/
                src/
                    utils/
                        logger.py

        Therefore:
            logger.py -> utils -> src -> project_root
        """

        return Path(__file__).resolve().parents[2]

    def _get_log_file(self) -> Path:
        """
        Returns today's log file path.
        """

        project_root = self._get_project_root()

        log_dir = project_root / self.LOG_DIR_NAME
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y_%m_%d")

        return log_dir / f"{timestamp}.log"

    def _configure(self) -> None:
        """
        Configure console and rotating file handlers.
        """

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        log_file = self._get_log_file()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.LOG_LEVEL)

        console_formatter = logging.Formatter(self.CONSOLE_FORMAT)

        console_handler.setFormatter(console_formatter)

        # Rotating file handler
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding="utf-8",
        )

        file_handler.setLevel(self.LOG_LEVEL)

        file_formatter = logging.Formatter(self.FILE_FORMAT)

        file_handler.setFormatter(file_formatter)

        # Attach handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        """
        Returns the configured logging.Logger instance.
        """

        return self.logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Convenience function for getting a configured logger.

    Example:
        logger = get_logger(__name__)
    """

    return Logger(name).get_logger()
