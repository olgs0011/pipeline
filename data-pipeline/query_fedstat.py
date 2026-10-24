"""Витрина ЕМИСС через DuckDB поверх parquet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import duckdb
from pipeline.config import settings


def main() -> None:
    fedstat_dir = settings.silver_dir / "fedstat"
    if not fedstat_dir.exists():
        print(f"❌ Папка не найдена: {fedstat_dir}")
        return

    files = sorted(fedstat_dir.glob("x*/data.parquet"))
    print(f"Найдено {len(files)} файлов ЕМИСС\n")

    con = duckdb.connect()
    file_list = ", ".join(f"'{f.as_posix()}'" for f in files)
    con.execute(f"""
        CREATE VIEW fedstat AS
        SELECT * FROM read_parquet([{file_list}], union_by_name=true)
    """)

    # 1. Общая сводка
    print("=" * 70)
    print("ОБЩАЯ СВОДКА ПО ЕМИСС")
    print("=" * 70)
    print(con.sql("""
        SELECT
            count(*) AS rows,
            count(DISTINCT factor_code) AS factors,
            count(DISTINCT year) AS years,
            count(DISTINCT region) AS regions,
            min(year) AS min_year,
            max(year) AS max_year
        FROM fedstat
    """).df())

    # 2. Список факторов с количеством строк
    print("\n" + "=" * 70)
    print("ВСЕ ФАКТОРЫ В SILVER")
    print("=" * 70)
    print(con.sql("""
        SELECT
            factor_code,
            count(*) AS rows,
            min(year) AS min_year,
            max(year) AS max_year
        FROM fedstat
        GROUP BY factor_code
        ORDER BY CAST(regexp_extract(factor_code, '\\d+', 0) AS INTEGER)
    """).df())

    # 3. Топ-10 регионов по Джини 2022
    print("\n" + "=" * 70)
    print("ТОП-10 РЕГИОНОВ ПО ДЖИНИ (2022) — x117")
    print("=" * 70)
    print(con.sql("""
        SELECT region, value
        FROM fedstat
        WHERE factor_code = 'x117' AND year = 2022
        ORDER BY value DESC
        LIMIT 10
    """).df())

    # 4. Динамика Джини по РФ
    print("\n" + "=" * 70)
    print("ДИНАМИКА ДЖИНИ ПО РФ (2015-2022) — x117")
    print("=" * 70)
    print(con.sql("""
        SELECT year, value
        FROM fedstat
        WHERE factor_code = 'x117'
          AND region LIKE 'Российская Федерация%'
        ORDER BY year
    """).df())

    # 5. Топ регионов по площади жилья
    print("\n" + "=" * 70)
    print("ПЛОЩАДЬ ЖИЛЬЯ НА ЧЕЛОВЕКА (2022), топ-10 — x128")
    print("=" * 70)
    print(con.sql("""
        SELECT region, value
        FROM fedstat
        WHERE factor_code = 'x128' AND year = 2022
        ORDER BY value DESC
        LIMIT 10
    """).df())


if __name__ == "__main__":
    main()