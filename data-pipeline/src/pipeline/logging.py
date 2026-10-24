"""Настройка логирования через loguru."""
import logging
import sys

from loguru import logger

from pipeline.config import settings


def setup_logging() -> None:
    """Инициализирует loguru: пишет в stderr, глушит шумные логгеры Prefect."""
    logger.remove()

    # Глушим внутренние логгеры Prefect
    logging.getLogger("prefect._internal.concurrency").setLevel(logging.CRITICAL)
    logging.getLogger("prefect.events").setLevel(logging.CRITICAL)

    logger.add(
        sys.stderr,
        level="DEBUG", #ПРАВИЛИ
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        filter=lambda record: "prefect._internal.concurrency" not in record["name"],
    )