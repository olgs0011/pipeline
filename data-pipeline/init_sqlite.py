"""Инициализация базы данных SQLite для рабочего ПК."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from loguru import logger
from pipeline.db.models import Base
from pipeline.db.session_sqlite import engine
from pipeline.logging import setup_logging


def main() -> None:
    setup_logging()
    logger.info(f"Создание таблиц в SQLite: {engine.url}")
    Base.metadata.create_all(engine)
    logger.success("Таблицы успешно созданы в SQLite.")


if __name__ == "__main__":
    main()