"""Глубокая диагностика DuckDB + parquet."""
import duckdb

p = "data/silver/rospotrebnadzor/form_1_rost_snizh/year=2018/data.parquet"

print("=" * 60)
print("1. SCHEMA")
print("=" * 60)
print(duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{p}')").df())

print("\n" + "=" * 60)
print("2. DISTINCT year")
print("=" * 60)
print(duckdb.sql(f"SELECT DISTINCT year FROM read_parquet('{p}') ORDER BY year").df())

print("\n" + "=" * 60)
print("3. COUNT(*) и COUNT(DISTINCT year)")
print("=" * 60)
print(duckdb.sql(f"""
    SELECT COUNT(*) AS total_rows,
           COUNT(DISTINCT year) AS n_years
    FROM read_parquet('{p}')
""").df())

print("\n" + "=" * 60)
print("4. MIN/MAX year")
print("=" * 60)
print(duckdb.sql(f"""
    SELECT MIN(year) AS min_year, MAX(year) AS max_year
    FROM read_parquet('{p}')
""").df())

print("\n" + "=" * 60)
print("5. Первые 3 строки")
print("=" * 60)
print(duckdb.sql(f"SELECT * FROM read_parquet('{p}') LIMIT 3").df())

print("\n" + "=" * 60)
print("6. Проверка через Polars для сравнения")
print("=" * 60)
import polars as pl
df_pl = pl.read_parquet(p)
print(f"Polars shape: {df_pl.shape}")
print(f"Polars years: {df_pl['year'].unique().sort().to_list()}")