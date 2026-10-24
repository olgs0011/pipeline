"""Разовый скрипт для проверки парсера. Удалить после верификации."""
from pathlib import Path
import polars as pl

from pipeline.logging import setup_logging
from pipeline.sources.rospotrebnadzor import parse_form_1_xls

setup_logging()

bronze_file = Path(
    "data/bronze/rospotrebnadzor/form_1_rost_snizh/2018/"
    "ф 1_рост-сниж_свод по РФ_январь-декабрь_2018.xls"
)

if not bronze_file.exists():
    raise SystemExit(f"Файл не найден: {bronze_file.resolve()}")

df: pl.DataFrame = parse_form_1_xls(bronze_file, period="2018")

print("\n=== Схема ===")
print(df.schema)

print(f"\n=== Размер: {df.height} строк ===")

print("\n=== Первые 15 строк ===")
print(df.head(15))

print("\n=== Уникальные годы ===")
print(df["year"].unique().sort())

print("\n=== Уникальные metric ===")
print(df["metric"].unique().sort())

print("\n=== Уникальные age_group ===")
print(df["age_group"].unique().sort())

print("\n=== Кол-во уникальных болезней ===")
print(df["disease_name"].n_unique())

print("\n=== Проверка: Брюшной тиф, 2018, cases, all ===")
print(
    df.filter(
        (pl.col("disease_name") == "Брюшной тиф")
        & (pl.col("year") == 2018)
        & (pl.col("metric") == "cases")
        & (pl.col("age_group") == "all")
    )
)

print("\n=== Проверка: Брюшной тиф, 2017, cases, all ===")
print(
    df.filter(
        (pl.col("disease_name") == "Брюшной тиф")
        & (pl.col("year") == 2017)
        & (pl.col("metric") == "cases")
        & (pl.col("age_group") == "all")
    )
)