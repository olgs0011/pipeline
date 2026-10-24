"""Обработка одного фактора ЕМИСС: API → silver parquet → Postgres.

Запуск:
    python process_fedstat.py x117         # только x117
    python process_fedstat.py x117 x1 x3   # несколько
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import polars as pl
from loguru import logger
from sqlalchemy import select

from pipeline.config import settings
from pipeline.db.models import FactorSource, FileRecord, Run
from pipeline.db.session import session_scope
#from pipeline.db.session import session_scope   #from pipeline.db.session_sqlite import session_scope (без докера!)
from pipeline.logging import setup_logging
from pipeline.sources.fedstat import FedstatClient
from pipeline.validation.fedstat_schema import validate_fedstat

SOURCE_ID = "fedstat"
PIPELINE_VERSION = "0.3.0"
YEARS = list(range(2015, 2026))   # 2015..2025


def _silver_dir(factor_code: str) -> Path:
    return settings.silver_dir / SOURCE_ID / factor_code


def _record_run(run_id, file_id, stage, started_at, status, error=None):
    with session_scope() as session:
        session.add(Run(
            id=run_id,
            file_id=file_id,
            stage=stage,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status=status,
            error=error,
            pipeline_version=PIPELINE_VERSION,
        ))


def process_factor(factor_code: str) -> None:
    """Скачивает данные для одного фактора, валидирует, сохраняет в silver."""
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    # 1. Достаём indicator_id из factor_sources
    with session_scope() as session:
        fs = session.execute(
            select(FactorSource).where(
                FactorSource.factor_code == factor_code,
                FactorSource.source_id == SOURCE_ID,
            )
        ).scalar_one_or_none()
        if fs is None:
            logger.error(f"Нет маппинга для {factor_code} в factor_sources")
            return
        indicator_id = int(fs.external_id)
        filter_json = fs.filter_json or {}

    logger.info(f"[{factor_code}] indicator_id={indicator_id}, filters={filter_json}")

    # 2. Запрос к ЕМИСС
    try:
        with FedstatClient() as client:
            df = client.fetch_data(
                indicator_id=indicator_id,
                years=YEARS,
                extra_filters=filter_json,
                all_regions=True,
                concurrency=10,
            )
    except Exception as e:
        logger.exception(f"[{factor_code}] Ошибка API: {e}")
        _record_run(run_id, None, "fedstat_fetch", started_at, "FAILED", str(e))
        return

    if df.is_empty():
        logger.error(f"[{factor_code}] Пустой ответ")
        _record_run(run_id, None, "fedstat_fetch", started_at, "FAILED", "empty")
        return

    # 3. Добавим factor_code в DataFrame
    df = df.with_columns(pl.lit(factor_code).alias("factor_code"))

    # 4. Валидация
    if not validate_fedstat(df):
        _record_run(run_id, None, "fedstat_validate", started_at, "FAILED", "validation")
        return

    # 5. Сохранение в silver
    silver_dir = _silver_dir(factor_code)
    silver_dir.mkdir(parents=True, exist_ok=True)
    silver_file = silver_dir / "data.parquet"
    df.write_parquet(silver_file, compression="snappy")
    logger.success(f"[{factor_code}] Parquet: {silver_file} ({df.height} строк)")

    # 6. Метаданные в Postgres
    with session_scope() as session:
        existing = session.execute(
            select(FileRecord).where(FileRecord.silver_path == str(silver_file))
        ).scalar_one_or_none()

        if existing is None:
            file_rec = FileRecord(
                id=uuid4(),
                dataset_id="fedstat_indicators",
                url=f"https://www.fedstat.ru/indicator/{indicator_id}#{factor_code}",
                period=None,
                region="все регионы РФ",
                year=None,
                version=1,
                checksum_sha256=f"fedstat_{indicator_id}_{factor_code}",
                size_bytes=silver_file.stat().st_size,
                bronze_path=None,
                silver_path=str(silver_file),
                status="silver_ready",
                downloaded_at=datetime.now(timezone.utc),
                meta={
                    "factor_code": factor_code,
                    "indicator_id": indicator_id,
                    "filter_json": filter_json,
                    "years": YEARS,
                    "all_regions": True,
                },
            )
            session.add(file_rec)
            session.flush()
            file_id = file_rec.id
        else:
            file_id = existing.id
            existing.status = "silver_ready"

    _record_run(run_id, file_id, "fedstat_full", started_at, "SUCCESS")
    logger.success(f"[{factor_code}] Готово ({df.height} строк)")


def main(codes: list[str]) -> None:
    setup_logging()
    for code in codes:
        logger.info(f"=== Обработка {code} ===")
        try:
            process_factor(code)
        except Exception as e:
            logger.exception(f"[{code}] Необработанная ошибка: {e}")


if __name__ == "__main__":
    codes = sys.argv[1:] or ["x117"]
    main(codes)