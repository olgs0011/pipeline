"""Чтение базы индикаторов ЕМИСС из RDA-файла.

Источник: R-пакет fedstatAPIr (CRAN).
Файл базы: data/reference/fedstat_indicators_names_database.rda
"""
from pathlib import Path

import pyreadr

# Путь относительно корня проекта (data-pipeline)
ROOT = Path(__file__).resolve().parent
RDA_PATH = ROOT / "data" / "reference" / "fedstat_indicators_names_database.rda"
CSV_OUT = ROOT / "data" / "reference" / "fedstat_indicators.csv"

print(f"Читаем: {RDA_PATH}")
print(f"Существует: {RDA_PATH.exists()}")

result = pyreadr.read_r(str(RDA_PATH))
print(f"\nКлючи в файле: {list(result.keys())}")

df = result["fedstat_indicators_names_database"]

print(f"\n=== Размер: {df.shape} ===")
print(f"=== Колонки: {list(df.columns)} ===")
print(f"\n=== Первые 5 строк ===")
print(df.head())

print(f"\n=== Уникальные department ===")
print(df["department"].value_counts())

df.to_csv(CSV_OUT, index=False, encoding="utf-8")
print(f"\n✅ Сохранено в {CSV_OUT} ({len(df)} строк)")