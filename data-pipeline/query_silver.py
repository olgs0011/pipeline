"""SQL-запросы к silver через DuckDB поверх parquet.

ВАЖНО: hive_partitioning = false — иначе DuckDB перезатирает колонку `year`
значением из партиции `year=2018` в пути (см. баг от 2026-10-08).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import duckdb
from pipeline.config import settings


def main() -> None:
    silver_glob = str(
        settings.silver_dir
        / "rospotrebnadzor"
        / "form_1_rost_snizh"
        / "**/*.parquet"
    )

    con = duckdb.connect()
    con.execute(
        f"CREATE VIEW form1 AS "
        f"SELECT * FROM read_parquet('{silver_glob}', hive_partitioning = false)"
    )

    print("=== Распределение по year ===")
    print(
        con.sql(
            """
            SELECT year, count(*) AS rows
            FROM form1
            GROUP BY year
            ORDER BY year
            """
        ).df()
    )

    print("\n=== Общая статистика по year x metric x age_group ===")
    print(
        con.sql(
            """
            SELECT year, metric, age_group,
                   count(*) AS rows,
                   round(sum(value), 2) AS total
            FROM form1
            GROUP BY year, metric, age_group
            ORDER BY year DESC, metric, age_group
            """
        ).df()
    )

    print("\n=== Топ-10 болезней по cases (2018, все возрасты) ===")
    print(
        con.sql(
            """
            SELECT disease_name, icd_code, value
            FROM form1
            WHERE year = 2018 AND metric = 'cases' AND age_group = 'all'
            ORDER BY value DESC
            LIMIT 10
            """
        ).df()
    )

    print("\n=== Пневмония (внебольничная): динамика 2017 -> 2018 ===")
    print(
        con.sql(
            """
            SELECT year, metric, age_group, value
            FROM form1
            WHERE disease_name = 'Пневмония (внебольничная)'
            ORDER BY metric, age_group, year
            """
        ).df()
    )

    print("\n=== Сумма случаев ОРВИ за 2017+2018 (metric=cases, all) ===")
    print(
        con.sql(
            """
            SELECT year, sum(value) AS total_rvi
            FROM form1
            WHERE disease_name LIKE 'Острые инфекции верхних%'
              AND metric = 'cases' AND age_group = 'all'
            GROUP BY year
            ORDER BY year
            """
        ).df()
    )


if __name__ == "__main__":
    main()