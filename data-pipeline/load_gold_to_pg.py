"""Загрузка gold-витрин из Parquet в PostgreSQL.

Создаёт/обновляет таблицы:
  * gold_factors_wide     (year, region, x1, x2, ...)
  * gold_factors_rf       (year, x3, x77, ...)
  * gold_factor_meta      (factor_code, name, unit)
  * gold_region_meta      (region, type, is_active)
И VIEW:
  * gold_factors_subjects (только 85 действующих субъектов РФ)

Запуск:
    python load_gold_to_pg.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import polars as pl
from loguru import logger
from sqlalchemy import Boolean, Column, Float, Integer, MetaData, Table, Text, text

from pipeline.config import settings
from pipeline.db.session import engine
from pipeline.logging import setup_logging

BATCH_SIZE = 250  # безопасный батч с учётом лимита 65535 параметров psycopg


def _polars_to_sa_type(dtype: pl.DataType):
    if dtype.is_integer():
        return Integer
    if dtype.is_float():
        return Float
    if dtype == pl.Boolean:
        return Boolean
    return Text


def _load_parquet_to_table(
    parquet_path: Path,
    table_name: str,
    pk_cols: list[str],
) -> None:
    if not parquet_path.exists():
        logger.warning(f"Файл не найден, пропускаем: {parquet_path}")
        return

    df = pl.read_parquet(parquet_path)
    logger.info(
        f"Читаю {parquet_path}: {df.height} строк × {df.width} колонок -> {table_name}"
    )

    metadata = MetaData()
    columns = [
        Column(
            col_name,
            _polars_to_sa_type(dtype),
            primary_key=(col_name in pk_cols),
        )
        for col_name, dtype in df.schema.items()
    ]
    table = Table(table_name, metadata, *columns)
    rows = df.to_dicts()

    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        table.create(conn)

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.execute(table.insert(), batch)

    logger.success(f"Таблица {table_name}: загружено {len(rows)} строк")


def _create_subjects_view() -> None:
    view_sql = """
    CREATE OR REPLACE VIEW gold_factors_subjects AS
    SELECT w.*
    FROM gold_factors_wide w
    JOIN gold_region_meta r ON w.region = r.region
    WHERE r.is_active = TRUE;
    """
    with engine.begin() as conn:
        conn.execute(text(view_sql))
    logger.success("VIEW gold_factors_subjects создан (только активные субъекты РФ)")


def main() -> None:
    setup_logging()
    gold_root = settings.gold_dir

    _load_parquet_to_table(
        parquet_path=gold_root / "factor_meta.parquet",
        table_name="gold_factor_meta",
        pk_cols=["factor_code"],
    )
    _load_parquet_to_table(
        parquet_path=gold_root / "region_meta.parquet",
        table_name="gold_region_meta",
        pk_cols=["region"],
    )
    _load_parquet_to_table(
        parquet_path=gold_root / "factors_wide" / "data.parquet",
        table_name="gold_factors_wide",
        pk_cols=["year", "region"],
    )
    _load_parquet_to_table(
        parquet_path=gold_root / "factors_rf" / "data.parquet",
        table_name="gold_factors_rf",
        pk_cols=["year"],
    )

    _create_subjects_view()
    logger.success("Все Gold-витрины загружены в PostgreSQL.")


if __name__ == "__main__":
    main()