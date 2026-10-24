"""Обработка формы №1 Роспотребнадзора: bronze → silver.

Читает .xls из bronze, парсит в long-format, валидирует Pandera,
сохраняет Parquet в silver и пишет метаданные в Postgres.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Добавляем src в пути поиска модулей
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import polars as pl
from loguru import logger
from sqlalchemy import select

from pipeline.config import settings
from pipeline.db.models import FileRecord, Run
from pipeline.db.session import session_scope
from pipeline.logging import setup_logging
from pipeline.sources.rospotrebnadzor import parse_form_1_xls
from pipeline.validation.schemas import validate_form_1

SOURCE_ID = "rospotrebnadzor"
DATASET_ID = "form_1_rost_snizh"
PIPELINE_VERSION = "0.2.0"

BRONZE_DIR = (
    settings.bronze_dir
    / SOURCE_ID
    / DATASET_ID
    / "2018"
)
BRONZE_FILE = BRONZE_DIR / "ф 1_рост-сниж_свод по РФ_январь-декабрь_2018.xls"

PERIOD = "2018"
REGION = "РФ"
SILVER_DIR = settings.silver_dir / SOURCE_ID / DATASET_ID / f"year={PERIOD}"


def _silver_parquet_path() -> Path:
    return SILVER_DIR / "data.parquet"


def _record_run(
    run_id,
    file_id,
    stage: str,
    started_at: datetime,
    status: str,
    error: str | None = None,
) -> None:
    """Пишет запись о запуске стадии пайплайна."""
    with session_scope() as session:
        session.add(
            Run(
                id=run_id,
                file_id=file_id,
                stage=stage,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status=status,
                error=error,
                pipeline_version=PIPELINE_VERSION,
            )
        )


def _upsert_file_record(
    bronze_path: Path,
    silver_path: Path,
    file_size: int,
) -> "FileRecord":
    """Создаёт или обновляет FileRecord. Возвращает ORM-объект (detached)."""
    bronze_str = str(bronze_path)
    with session_scope() as session:
        file_rec = session.execute(
            select(FileRecord).where(FileRecord.bronze_path == bronze_str)
        ).scalar_one_or_none()

        if file_rec is None:
            file_rec = FileRecord(
                id=uuid4(),
                dataset_id=DATASET_ID,
                url=bronze_str,                # локальный источник как url
                period=PERIOD,
                region=REGION,
                year=int(PERIOD),
                version=1,
                checksum_sha256="pending",     # обновим ниже
                size_bytes=file_size,
                bronze_path=bronze_str,
                silver_path=str(silver_path),
                status="silver_ready",
                downloaded_at=datetime.now(timezone.utc),
            )
            session.add(file_rec)
        else:
            file_rec.silver_path = str(silver_path)
            file_rec.status = "silver_ready"
            file_rec.region = REGION
            file_rec.year = int(PERIOD)

        session.flush()
        return file_rec


def process_bronze_file() -> None:
    setup_logging()

    if not BRONZE_FILE.exists():
        logger.error(f"Файл не найден: {BRONZE_FILE.resolve()}")
        return

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    logger.info(f"Обработка файла: {BRONZE_FILE}")
    logger.info(f"Размер: {BRONZE_FILE.stat().st_size} байт")

    # 1. Парсинг
    try:
        df: pl.DataFrame = parse_form_1_xls(BRONZE_FILE, period=PERIOD)
    except Exception as e:
        logger.exception(f"Ошибка парсинга: {e}")
        _record_run(run_id, None, "bronze_to_silver", started_at, "FAILED", str(e))
        return

    if df.is_empty():
        logger.error("Датасет пуст после парсинга.")
        _record_run(run_id, None, "bronze_to_silver", started_at, "FAILED", "empty df")
        return

    # 2. Валидация
    if not validate_form_1(df):
        logger.error("Валидация не пройдена, прерывание.")
        _record_run(run_id, None, "bronze_to_silver", started_at, "FAILED", "validation failed")
        return

    # 3. Сохранение в silver
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    silver_file = _silver_parquet_path()
    df.write_parquet(silver_file, compression="snappy")
    logger.success(f"Parquet сохранён: {silver_file}")

    # 4. Метаданные в Postgres
    file_rec = _upsert_file_record(
        bronze_path=BRONZE_FILE,
        silver_path=silver_file,
        file_size=BRONZE_FILE.stat().st_size,
    )

    _record_run(
        run_id=run_id,
        file_id=file_rec.id,
        stage="bronze_to_silver",
        started_at=started_at,
        status="SUCCESS",
    )

    logger.success(
        f"Готово. Записей: {df.height}, болезней: {df['disease_name'].n_unique()}, "
        f"лет: {sorted(df['year'].unique().to_list())}"
    )


if __name__ == "__main__":
    process_bronze_file()