"""Сборка gold-витрин из silver-данных.

Читает все data/silver/fedstat/*/data.parquet, делает две витрины:

  * gold/factors_wide/data.parquet  — wide по регионам (year, region, x1, x2, ...)
  * gold/factors_rf/data.parquet    — wide по РФ (year, x1, x2, ...)
  * gold/factor_meta.parquet        — справочник (factor_code, name, unit)

Запуск:
    python build_marts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import duckdb
import polars as pl
from loguru import logger

from pipeline.config import settings
from pipeline.logging import setup_logging
from pipeline.reference.factors_list import FACTORS


MIN_REGIONS_FOR_WIDE = 50   # если в факторе >= столько уникальных регионов — идёт в wide


def _read_silver(silver_root: Path) -> tuple[list[str], list[str], dict[str, int]]:
    """Возвращает (wide_factors, rf_factors, {factor: n_regions})."""
    wide: list[str] = []
    rf: list[str] = []
    stats: dict[str, int] = {}

    for d in sorted(silver_root.iterdir()):
        if not d.is_dir():
            continue
        f = d / "data.parquet"
        if not f.exists():
            logger.warning(f"[{d.name}] нет data.parquet — пропускаем")
            continue

        # читаем только колонку region (быстро)
        try:
            df = pl.read_parquet(f, columns=["region"])
        except Exception as e:
            logger.warning(f"[{d.name}] не читается: {e}")
            continue

        n_regions = df["region"].n_unique()
        stats[d.name] = n_regions

        if n_regions >= MIN_REGIONS_FOR_WIDE:
            wide.append(d.name)
        else:
            rf.append(d.name)

    return wide, rf, stats


def _pivot_wide(
    silver_root: Path,
    factors: list[str],
    out_path: Path,
    key_cols: list[str],
) -> None:
    """Собирает wide-таблицу из указанных факторов.

    key_cols — ['year', 'region'] или ['year'].
    """
    if not factors:
        logger.warning(f"Нет факторов для {out_path.name}, пропускаем")
        return

    # список путей через запятую для duckdb
    paths = [str(silver_root / f / "data.parquet") for f in factors]
    paths_sql = ", ".join(f"'{p}'" for p in paths)

    # ключ группировки
    key_sql = ", ".join(key_cols)

    # собираем список агрегатных выражений (по одному на фактор)
    agg_sql = ",\n    ".join(
        f"MAX(CASE WHEN factor_code = '{f}' THEN value END) AS \"{f}\""
        for f in factors
    )

    con = duckdb.connect()
    query = f"""
        COPY (
            SELECT
                {key_sql},
                {agg_sql}
            FROM read_parquet([{paths_sql}], union_by_name=true)
            GROUP BY {key_sql}
            ORDER BY {key_sql}
        ) TO '{out_path}' (FORMAT PARQUET, COMPRESSION SNAPPY)
    """
    logger.info(f"Собираю {out_path.name}: {len(factors)} факторов")
    con.execute(query)
    con.close()

    # посчитаем строки
    n = pl.read_parquet(out_path).height
    logger.success(f"{out_path}: {n} строк, {len(factors)} факторов")


def _build_factor_meta(out_path: Path) -> None:
    """Справочник факторов из reference/factors_list.py."""
    rows = [
        {"factor_code": code, "name": name, "unit": unit or ""}
        for code, name, unit in FACTORS
    ]
    df = pl.DataFrame(rows)
    df.write_parquet(out_path, compression="snappy")
    logger.success(f"{out_path}: {df.height} факторов")

def _classify_region(region: str) -> tuple[str, bool]:
    """Возвращает (type, is_active) для названия региона из ЕМИСС."""
    low = region.strip().lower()

    # 1. РФ и макрорегионы
    if (
        low == "рф"
        or "российская федерация" in low
        or "районы крайнего севера" in low
        or "арктической зоны" in low
        or "коренных малочисленных народов" in low
    ):
        return "country", False

    # 2. Федеральные округа (действующие и исторические)
    if "федеральный округ" in low:
        return "federal_district", False

    # 3. Разрезы областей без входящих АО
    if (
        "(без ао)" in low
        or "кроме ненецкого" in low
        or "кроме ханты-мансийского" in low
    ):
        return "subject_part", False

    # 4. Упразднённые автономные округа
    if any(
        k in low
        for k in (
            "агинский бурятский",
            "коми-пермяцкий",
            "корякский округ",
            "таймырский",
            "усть-ордынский",
            "эвенкийский",
        )
    ):
        return "former_subject", False

    # 5. Действующие субъекты РФ (85 шт.)
    if any(
        k in low
        for k in (
            "область",
            "край",
            "республика",
            "город федерального значения",
            "автономный округ",
        )
    ):
        return "subject", True

    # 6. Остальное — города (региональные центры)
    return "city", False


def _build_region_meta(wide_parquet: Path, out_path: Path) -> None:
    """Собирает справочник регионов из уникальных значений factors_wide."""
    regions = (
        pl.read_parquet(wide_parquet, columns=["region"])["region"]
        .unique()
        .sort()
        .to_list()
    )
    rows = []
    for r in regions:
        r_type, is_active = _classify_region(r)
        rows.append({"region": r, "type": r_type, "is_active": is_active})

    df = pl.DataFrame(rows)
    df.write_parquet(out_path, compression="snappy")

    active_cnt = df.filter(pl.col("is_active")).height
    logger.success(
        f"{out_path}: {df.height} регионов (активных субъектов: {active_cnt})"
    )

def main() -> None:
    setup_logging()

    silver_root = settings.silver_dir / "fedstat"
    gold_root = settings.gold_dir  # см. ниже — если нет settings.gold_dir, заменим
    gold_root.mkdir(parents=True, exist_ok=True)

    logger.info(f"Silver: {silver_root}")
    logger.info(f"Gold:   {gold_root}")

    wide, rf, stats = _read_silver(silver_root)
    logger.info(f"С регионами: {len(wide)} факторов")
    logger.info(f"Только РФ:  {len(rf)} факторов")

    # ── 1. Витрина по регионам ──
    wide_dir = gold_root / "factors_wide"
    wide_dir.mkdir(parents=True, exist_ok=True)
    _pivot_wide(
        silver_root=silver_root,
        factors=wide,
        out_path=wide_dir / "data.parquet",
        key_cols=["year", "region"],
    )

    # ── 2. Витрина по РФ ──
    rf_dir = gold_root / "factors_rf"
    rf_dir.mkdir(parents=True, exist_ok=True)
    _pivot_wide(
        silver_root=silver_root,
        factors=rf,
        out_path=rf_dir / "data.parquet",
        key_cols=["year"],
    )

    # ── 3. Справочник факторов ──
    _build_factor_meta(gold_root / "factor_meta.parquet")

    # ── 4. Справочник регионов ──
    _build_region_meta(
        wide_parquet=wide_dir / "data.parquet",
        out_path=gold_root / "region_meta.parquet",
    )

    logger.success("Готово.")


if __name__ == "__main__":
    main()