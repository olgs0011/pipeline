"""Обёртка Source для ЕМИСС — единый интерфейс для пайплайна."""
from __future__ import annotations

from pathlib import Path

import polars as pl
from loguru import logger

from pipeline.sources.base import DiscoveredFile, Source
from pipeline.sources.fedstat import FedstatClient


class FedstatSource(Source):
    """Источник ЕМИСС через FedstatClient.

    В отличие от обычного Source, здесь нет «файлов» в bronze —
    данные тянутся через API и сразу нормализуются в long-format.
    """

    id = "fedstat"
    name = "ЕМИСС (Единая межведомственная информационно-статистическая система)"
    base_url = "https://www.fedstat.ru"

    def discover(self) -> list[DiscoveredFile]:
        """Для ЕМИСС discover возвращает список indicator_id из factor_sources.

        Пока не реализовано — discover делается через БД (таблица factor_sources).
        """
        raise NotImplementedError(
            "Для ЕМИСС discover идёт через таблицу factor_sources. "
            "Используйте оркестратор process_fedstat.py."
        )

    def parse(self, path: Path, period: str | None = None) -> pl.DataFrame:
        """Не применимо — ЕМИСС отдаёт данные через API, не из файла."""
        raise NotImplementedError("ЕМИСС не парсит файлы, используйте fetch_factor()")

    # ---------------- основной метод ----------------

    def fetch_factor(
        self,
        indicator_id: int,
        years: list[int],
        region_id: int = 1688487,   # РФ
    ) -> pl.DataFrame:
        """Тянет данные по одному показателю за указанные годы.

        :param indicator_id: ID показателя в ЕМИСС
        :param years: список лет
        :param region_id: ID региона (по умолчанию РФ)
        """
        with FedstatClient() as client:
            df = client.fetch_data(
                indicator_id=indicator_id,
                years=years,
                region_id=region_id,
            )
        return df