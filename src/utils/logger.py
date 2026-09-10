# utils/logger.py
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Returns a configured logger instance.
    - Logs to both console and rotating file.
    - File logs are stored in logs/YYYY_MM_DD.log
    - Rotates when file size exceeds 5 MB, keeps 5 backups.
    """

    # Ensure logs directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Daily log file
    timestamp = datetime.now().strftime("%Y_%m_%d")
    log_file = os.path.join(log_dir, f"{timestamp}.log")

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if logger is reused
    if not logger.handlers:
        # Console handler (force UTF-8 encoding if supported)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        # Rotating file handler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

        # Attach handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
