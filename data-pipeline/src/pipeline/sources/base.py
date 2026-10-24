"""Базовый интерфейс источника данных."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl


@dataclass
class DiscoveredFile:
    """Файл, найденный на сайте источника (ещё не скачан)."""
    url: str
    filename: str
    period: str | None = None
    year: int | None = None
    region: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    size_bytes: int | None = None
    meta: dict = field(default_factory=dict)


class Source(ABC):
    """Абстрактный источник. Каждый подкласс реализует discover/parse."""

    id: str
    name: str
    base_url: str

    @abstractmethod
    def discover(self) -> list[DiscoveredFile]:
        """Найти файлы на сайте источника. Возвращает список DiscoveredFile."""
        ...

    @abstractmethod
    def parse(self, path: Path, period: str | None = None) -> pl.DataFrame:
        """Распарсить скачанный файл в long-format Polars DataFrame."""
        ...