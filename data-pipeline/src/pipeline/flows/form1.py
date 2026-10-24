"""Prefect flow: полный пайплайн формы №1 Роспотребнадзора.

  discover → download → parse → validate → silver → postgres
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import polars as pl
from loguru import logger
from prefect import flow, task
from sqlalchemy import select

from pipeline.config import settings
from pipeline.db.models import FileRecord, Run
from pipeline.db.session import session_scope
from pipeline.ingestion.downloader import download
from pipeline.sources.base import DiscoveredFile
from pipeline.sources.rospotrebnadzor import (
    RospotrebnadzorSource,
    parse_form_1_xls,
)
from pipeline.validation.schemas import validate_form_1

SOURCE_ID = "rospotrebnadzor"
DATASET_ID = "form_1_rost_snizh"
PIPELINE_VERSION = "0.3.0"


# --------------------------------------------------------------- tasks


@task(name="discover")
def task_discover() -> list[DiscoveredFile]:
    src = RospotrebnadzorSource()
    files = src.discover()
    logger.info(f"Discover: {len(files)} файлов")
    return files


@task(name="download")
def task_download(f: DiscoveredFile) -> Path:
    """Скачивает файл в bronze. Возвращает путь к локальному файлу."""
    result = download(
        url=f.url,
        source=SOURCE_ID,
        dataset=DATASET_ID,
        period=f.period,
    )
    return result.bronze_path


@task(name="parse")
def task_parse(bronze_path: Path, period: str | None) -> pl.DataFrame:
    return parse_form_1_xls(bronze_path, period=period)


@task(name="validate")
def task_validate(df: pl.DataFrame) -> bool:
    return validate_form_1(df)


@task(name="save_silver")
def task_save_silver(df: pl.DataFrame, year: int) -> Path:
    silver_dir = (
        settings.silver_dir / SOURCE_ID / DATASET_ID / f"year={year}"
    )
    silver_dir.mkdir(parents=True, exist_ok=True)
    silver_file = silver_dir / "data.parquet"
    df.write_parquet(silver_file, compression="snappy")
    logger.success(f"Parquet: {silver_file} ({df.height} строк)")
    return silver_file


@task(name="record_metadata")
def task_record_metadata(
    bronze_path: Path,
    silver_path: Path,
    year: int,
    region: str,
) -> str:
    """Записывает FileRecord + Run, возвращает id Run."""
    run_id = uuid4()
    started = datetime.now(timezone.utc)

    with session_scope() as session:
        bronze_str = str(bronze_path)
        file_rec = session.execute(
            select(FileRecord).where(FileRecord.bronze_path == bronze_str)
        ).scalar_one_or_none()

        if file_rec is None:
            file_rec = FileRecord(
                id=uuid4(),
                dataset_id=DATASET_ID,
                url=bronze_str,
                period=str(year),
                region=region,
                year=year,
                version=1,
                checksum_sha256="pending",
                size_bytes=bronze_path.stat().st_size,
                bronze_path=bronze_str,
                silver_path=str(silver_path),
                status="silver_ready",
                downloaded_at=datetime.now(timezone.utc),
            )
            session.add(file_rec)
        else:
            file_rec.silver_path = str(silver_path)
            file_rec.status = "silver_ready"
            file_rec.year = year
            file_rec.region = region

        session.flush()
        file_id = file_rec.id

        session.add(
            Run(
                id=run_id,
                file_id=file_id,
                stage="full_pipeline",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                status="SUCCESS",
                pipeline_version=PIPELINE_VERSION,
            )
        )

    return str(run_id)


# --------------------------------------------------------------- flow


@flow(name="form_1_rost_snizh_flow", log_prints=True)
def form_1_flow(period: str = "2018") -> None:
    """Полный пайплайн формы №1.

    Алгоритм:
      1. discover() — найти файлы на сайте Роспотребнадзора.
      2. Если нашёл — обработать каждый.
      3. Если 0 — fallback на локальный bronze-файл (для разработки).
    """
    logger.info(f"Старт flow form_1, period={period}")

    files = task_discover()

    if files:
        logger.info(f"Найдено {len(files)} файлов на сайте, обрабатываем.")
        for f in files:
            _process_one(
                period=f.period or period,
                year=f.year or int(period),
                region=f.region or "РФ",
                discovered=f,
            )
        return

    # Fallback: локальный файл
    logger.info("Discover пуст, используем локальный bronze-файл (dev mode).")
    bronze_local = (
        settings.bronze_dir / SOURCE_ID / DATASET_ID / period
        / f"ф 1_рост-сниж_свод по РФ_январь-декабрь_{period}.xls"
    )
    if not bronze_local.exists():
        logger.error(f"Локальный файл не найден: {bronze_local}")
        return

    _process_one(
        period=period,
        year=int(period),
        region="РФ",
        discovered=None,
        bronze_local=bronze_local,
    )


def _process_one(
    period: str,
    year: int,
    region: str,
    discovered: DiscoveredFile | None,
    bronze_local: Path | None = None,
) -> None:
    """Обработка одного файла: download (если нужно) → parse → validate → silver → pg."""
    if discovered is not None:
        logger.info(f"Скачиваем: {discovered.url}")
        bronze = task_download(discovered)
    else:
        assert bronze_local is not None
        bronze = bronze_local

    df = task_parse(bronze, period)
    if df.is_empty():
        logger.warning(f"Пустой df для {bronze}, пропускаем.")
        return

    if not task_validate(df):
        logger.error(f"Валидация не пройдена для {bronze}, пропускаем.")
        return

    silver = task_save_silver(df, year)
    run_id = task_record_metadata(bronze, silver, year, region)
    logger.success(f"Готово: {bronze.name} → run_id={run_id}")


if __name__ == "__main__":
    form_1_flow()