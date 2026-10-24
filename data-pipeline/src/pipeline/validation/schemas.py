"""Pandera-схемы для валидации silver-слоя."""
from __future__ import annotations

import pandera.polars as pa
import polars as pl
from loguru import logger


class Form1SilverSchema(pa.DataFrameModel):
    """Схема silver для формы №1 Роспотребнадзора (long-format).

    Каждая строка — одно значение:
        (year, icd_code, disease_name, metric, age_group) -> value
    """

    year: int = pa.Field(ge=2000, le=2100)
    icd_code: str = pa.Field(nullable=True, str_length={"max_value": 32})
    disease_name: str = pa.Field(nullable=False, str_length={"min_value": 2})
    metric: str = pa.Field(isin=["cases", "per_100k"])
    age_group: str = pa.Field(isin=["all", "0-17", "0-14"])
    value: float = pa.Field(nullable=False, ge=0.0)

    class Config:
        coerce = True
        strict = True


def validate_form_1(df: pl.DataFrame) -> bool:
    """Возвращает True, если df соответствует Form1SilverSchema.

    При ошибке пишет подробности в лог.
    """
    if df.is_empty():
        logger.error("Валидация формы №1: датафрейм пустой.")
        return False

    try:
        Form1SilverSchema.validate(df, lazy=False)
        logger.success(
            f"Валидация формы №1 пройдена: {df.height} строк, "
            f"{df['disease_name'].n_unique()} болезней, "
            f"{df['year'].n_unique()} лет."
        )
        return True
    except pa.errors.SchemaError as e:
        logger.error(f"Ошибка валидации схемы формы №1:\n{e}")
        return False
    except Exception as e:
        logger.exception(f"Неожиданная ошибка валидации: {e}")
        return False