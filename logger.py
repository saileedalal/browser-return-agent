"""
logger.py
---------
Single place that sets up logging for the whole project.
Every action the agent performs (open browser, login, found order, errors...)
gets logged here with a timestamp, to both the console and a log file.
"""

import logging
import config


def get_logger(name: str = "return_agent") -> logging.Logger:
    """
    Returns a configured logger instance.
    Safe to call multiple times (from different modules) - handlers are
    only added once.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Logger already configured (e.g. imported from another module) - reuse it.
        return logger

    logger.setLevel(logging.INFO)

    # Format: timestamp - log level - message
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Log to file
    file_handler = logging.FileHandler(config.LOG_FILE_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
