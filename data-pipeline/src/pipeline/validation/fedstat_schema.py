"""Pandera-схема для данных ЕМИСС (long-format)."""
import pandera.polars as pa
import polars as pl
from loguru import logger


class FedstatSilverSchema(pa.DataFrameModel):
    """Каждая строка = одно значение показателя.

    year      — год наблюдения (2015..2025)
    region    — название региона (строка)
    period_value_id — ID значения фильтра «Период» (год/полугодие)
    value     — числовое значение
    """

    year: int = pa.Field(ge=1900, le=2100)
    region: str = pa.Field(nullable=False, str_length={"min_value": 2})
    period_value_id: int = pa.Field(nullable=True)
    value: float = pa.Field(nullable=True, ge=-1e12, le=1e12)

    class Config:
        coerce = True
        strict = False   # допускаем доп. колонки


def validate_fedstat(df: pl.DataFrame) -> bool:
    if df.is_empty():
        logger.error("Fedstat: пустой DataFrame")
        return False
    try:
        FedstatSilverSchema.validate(df, lazy=False)
        logger.success(f"Fedstat-валидация OK: {df.height} строк")
        return True
    except Exception as e:
        logger.error(f"Fedstat-валидация упала: {e}")
        return False