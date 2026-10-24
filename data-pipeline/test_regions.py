"""Тест: реально ли ЕМИСС отдаёт данные по регионам (не только РФ).

Берём индикатор 31547 (x1), гоняем POST по всем ОКАТО за 2020 год.
Смотрим: сколько регионов вернуло данные, сколько пусто.
Плюс печатаем реальный body и первые байты ответа для отладки.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from loguru import logger
from pipeline.logging import setup_logging
from pipeline.sources.fedstat import (
    FedstatClient,
    _classify_filter,
    _resolve_period,
    _resolve_unit,
    _resolve_indicator,
    _resolve_secondary_candidates,
    _normalize_results,
)

INDICATOR_ID = 31547   # x1
YEAR = 2020
REGION_TITLE = "Российская Федерация"


def main() -> None:
    setup_logging()

    with FedstatClient() as client:
        meta = client.fetch_indicator_meta(INDICATOR_ID)
        logger.info(f"Индикатор: {meta.title}")
        logger.info(f"Фильтров: {len(meta.filters)}")

        okato_filt = None
        for oid, f in meta.filters.items():
            if _classify_filter(f) == "okato":
                okato_filt = f
                break
        if okato_filt is None:
            logger.error("Не нашли фильтр ОКАТО.")
            return

        logger.info(f"ОКАТО-фильтр: {okato_filt.title} ({len(okato_filt.values)} значений)")

        # Первые 3 региона — для быстрого теста
        test_values = okato_filt.values[:3]
        logger.info(f"Тестируем {len(test_values)} регионов за {YEAR} год")

        plans: dict[int, list[int]] = {}
        for oid, f in meta.filters.items():
            if oid == okato_filt.owner_id:
                continue
            kind = _classify_filter(f)
            if kind == "year":
                plans[oid] = [YEAR]
            elif kind == "period":
                plans[oid] = _resolve_period(f)
            elif kind == "unit":
                plans[oid] = _resolve_unit(f)
            elif kind == "indicator":
                plans[oid] = _resolve_indicator(f)
            else:
                candidates = _resolve_secondary_candidates(f, meta.title)
                plans[oid] = candidates[:1] if candidates else [f.values[0].id]

        url = f"/indicator/dataGrid.do?id={INDICATOR_ID}"
        results: list[tuple[str, int]] = []

        for rv in test_values:
            parts = []
            for lid in meta.line_filters:
                parts.append(f"lineObjectIds={lid}")
            for cid in meta.column_filters:
                parts.append(f"columnObjectIds={cid}")
            for oid, values in plans.items():
                for v in values:
                    parts.append(f"selectedFilterIds={oid}_{v}")
            parts.append(f"selectedFilterIds={okato_filt.owner_id}_{rv.id}")
            body = "&".join(parts)

            logger.info(f"=== {rv.title} ({rv.id}) ===")
            logger.info(f"BODY: {body}")

            try:
                r = client.client.post(url, content=body)
                logger.info(f"HTTP {r.status_code}, ctype={r.headers.get('content-type')}")
                logger.info(f"RESP[0:300]: {r.text[:300]}")

                if r.status_code != 200:
                    results.append((rv.title, -1))
                    continue
                if "json" not in r.headers.get("content-type", ""):
                    results.append((rv.title, -1))
                    continue
                rows = r.json().get("results", [])
                logger.info(f"rows: {len(rows)}")
                if not rows:
                    results.append((rv.title, 0))
                    continue
                df = _normalize_results(rows)
                logger.info(f"df: {df.shape}")
                results.append((rv.title, df.height))
            except Exception as e:
                logger.warning(f"{rv.title}: {e}")
                results.append((rv.title, -2))

        logger.info("=" * 60)
        logger.info("Результаты по регионам:")
        non_empty = 0
        for title, n in results:
            flag = "✅" if n > 0 else "❌"
            logger.info(f"  {flag} {title}: {n} строк")
            if n > 0:
                non_empty += 1
        logger.info(f"\nНепустых: {non_empty} из {len(results)}")


if __name__ == "__main__":
    main()