"""Парсер формы №1 Роспотребнадзора «Сведения об инфекционных и паразитарных
заболеваниях за январь–декабрь <год>».

Файл — .xls с 3-уровневой шапкой. Структура колонок (1-based, как в Excel):
    1      №
    2      Наименование заболеваний
    3–8    данные за текущий год   (всего, на 100к, 0-17, на 100к 0-17, 0-14, на 100к 0-14)
    9–14   данные за год-1         (те же 6 колонок)
    15–17  рост/снижение           (всего, 0-17, 0-14)   — смешанные типы, парсим частично
    18     МКБ-код
    19–21  год текущий / год-1 / год-2
    22–27  население (тек. год: всего, 0-17, 0-14; год-1: всего, 0-17, 0-14)
    28–42  расчёты                 (сл., разы+, разы−, %, результат) × 3 среза

На выходе — long-format Polars DataFrame:
    year | icd_code | disease_name | metric | age_group | value
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import polars as pl
from loguru import logger

HEADER_SCAN_LIMIT = 15

# (column_index_0based, metric, age_group) — для текущего и предыдущего года.
# Колонки 0 (№) и 1 (наименование) — служебные.
COLUMNS_CURRENT = {
    2: ("cases",     "all"),
    3: ("per_100k",  "all"),
    4: ("cases",     "0-17"),
    5: ("per_100k",  "0-17"),
    6: ("cases",     "0-14"),
    7: ("per_100k",  "0-14"),
}
COLUMNS_PREV = {
    8:  ("cases",     "all"),
    9:  ("per_100k",  "all"),
    10: ("cases",     "0-17"),
    11: ("per_100k",  "0-17"),
    12: ("cases",     "0-14"),
    13: ("per_100k",  "0-14"),
}
ICD_COLUMN = 17  # 0-based индекс колонки с МКБ-кодом


# --------------------------------------------------------------- утилиты


def _clean_str(value: object) -> str:
    """Аккуратно превращает ячейку в строку, снимает переводы строк и лишние пробелы."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).replace("\xa0", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", s)


def _parse_number(value: object) -> float | None:
    """Парсит число из ячейки. Возвращает None, если не число.

    Обрабатывает:
      - 123, 123.4, '1 234,5', '-2,7 раз', '-2 сл.', '1,9 раз'
      - русский десятичный разделитель ',' → '.'
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return None
        return float(value)

    s = str(value).strip().lower()
    if not s:
        return None

    # «N раз», «N сл.» и подобные — не числовой показатель.
    if "раз" in s or "сл." in s:
        return None

    # убираем пробелы-разделители тысяч и заменяем запятую на точку
    s = s.replace(" ", "").replace("\xa0", "").replace(",", ".")
    s = s.rstrip("%")

    try:
        return float(s)
    except ValueError:
        return None


def _find_header_row(raw_df: pd.DataFrame) -> int:
    """Ищет строку с нумерацией колонок (1, 2, 3, ..., 42).

    В файле Роспотребнадзора такая строка есть — это последний ряд шапки.
    """
    for idx in range(min(HEADER_SCAN_LIMIT, len(raw_df))):
        row = raw_df.iloc[idx]
        # проверяем, что в первых 10 ячейках есть 1, 2, 3, 4 — почти подряд
        vals = [_parse_number(v) for v in row.head(10).tolist()]
        nums = [v for v in vals if v is not None]
        if len(nums) >= 4 and nums[:4] == [1.0, 2.0, 3.0, 4.0]:
            return idx
    return 0


def _extract_period(header_cells: list[str], default: str) -> str:
    """Пытается вытащить год из шапки листа («январь..декабрь 2018»)."""
    text = " ".join(header_cells)
    m = re.search(r"(20\d{2})", text)
    if m:
        return m.group(1)
    return default


# --------------------------------------------------------------- парсер


def parse_form_1_xls(
    file_path: Path,
    period: str | None = None,
) -> pl.DataFrame:
    """Парсит .xls формы №1 и возвращает long-format Polars DataFrame.

    :param file_path: путь к .xls
    :param period: год текущего периода. Если None — попытаемся вытащить из шапки.
    """
    logger.info(f"Старт парсинга файла: {file_path}")
    excel_file = pd.ExcelFile(file_path, engine="xlrd")

    all_rows: list[dict] = []

    for sheet_name in excel_file.sheet_names:
        raw_df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine="xlrd")
        if raw_df.empty:
            continue

        # Ищем строку с нумерацией (1,2,3,...)
        header_row_idx = _find_header_row(raw_df)

        # Шапка — все строки выше нумерации; из них пробуем вытащить год
        header_cells = [
            _clean_str(v)
            for v in raw_df.iloc[: header_row_idx + 1].values.flatten().tolist()
            if _clean_str(v)
        ]
        current_year_str = period or _extract_period(header_cells, "unknown")
        try:
            current_year = int(current_year_str)
        except ValueError:
            current_year = None
        prev_year = current_year - 1 if current_year else None

        logger.info(
            f"Лист «{sheet_name}»: шапка в строке {header_row_idx}, "
            f"год={current_year}, год-1={prev_year}"
        )

        # Читаем данные ниже шапки
        data_df = raw_df.iloc[header_row_idx + 1 :].reset_index(drop=True)

        rows_added = 0
        for _, row in data_df.iterrows():
            disease_name = _clean_str(row.iloc[1]) if len(row) > 1 else ""
            row_number = _parse_number(row.iloc[0]) if len(row) > 0 else None

            # Пропускаем строки без номера и без названия, заголовки «всего»,
            # пустые ячейки, продолжения-«из них» без номера — они нам нужны,
            # поэтому условие мягкое: только имя обязательно.
            if not disease_name:
                continue
            if disease_name.lower() in {"наименование заболеваний", "показатель", "всего"}:
                continue

            icd_code = ""
            if len(row) > ICD_COLUMN:
                icd_code = _clean_str(row.iloc[ICD_COLUMN])
                # МКБ-код бывает "=20101000" (Excel-формула), "20101000" и "А01"
                icd_code = icd_code.lstrip("=").strip()
                if not re.match(r"^[A-ZА-Я]?\d*$", icd_code, re.IGNORECASE):
                    icd_code = ""

            # Текущий год
            if current_year:
                for col_idx, (metric, age_group) in COLUMNS_CURRENT.items():
                    if col_idx >= len(row):
                        continue
                    val = _parse_number(row.iloc[col_idx])
                    if val is None:
                        continue
                    all_rows.append({
                        "year": current_year,
                        "icd_code": icd_code,
                        "disease_name": disease_name,
                        "metric": metric,
                        "age_group": age_group,
                        "value": val,
                    })
                    rows_added += 1

            # Предыдущий год
            if prev_year:
                for col_idx, (metric, age_group) in COLUMNS_PREV.items():
                    if col_idx >= len(row):
                        continue
                    val = _parse_number(row.iloc[col_idx])
                    if val is None:
                        continue
                    all_rows.append({
                        "year": prev_year,
                        "icd_code": icd_code,
                        "disease_name": disease_name,
                        "metric": metric,
                        "age_group": age_group,
                        "value": val,
                    })
                    rows_added += 1

        logger.info(f"Лист «{sheet_name}»: извлечено {rows_added} значений")

    if not all_rows:
        logger.warning(f"Не удалось извлечь данные из {file_path}")
        return pl.DataFrame(
            schema={
                "year": pl.Int32,
                "icd_code": pl.Utf8,
                "disease_name": pl.Utf8,
                "metric": pl.Utf8,
                "age_group": pl.Utf8,
                "value": pl.Float64,
            }
        )

    df = pl.DataFrame(
        all_rows,
        schema={
            "year": pl.Int32,
            "icd_code": pl.Utf8,
            "disease_name": pl.Utf8,
            "metric": pl.Utf8,
            "age_group": pl.Utf8,
            "value": pl.Float64,
        },
    )
    logger.success(f"Распарсено записей: {len(df)} (уникальных болезней: {df['disease_name'].n_unique()})")
    return df

# --------------------------------------------------------------- источник


import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.sources.base import DiscoveredFile, Source


class RospotrebnadzorSource(Source):
    """Источник: Роспотребнадзор.

    Реализует discover() через обход страниц с формами.
    На практике ссылки на .xls меняются раз в год, поэтому список
    целевых URL задаётся в CONFIG_PAGES.

    parse() — делегирует в parse_form_1_xls.
    """

    id = "rospotrebnadzor"
    name = "Федеральная служба по надзору в сфере защиты прав потребителей и благополучия человека"
    base_url = "https://www.rospotrebnadzor.ru"

    # Страницы, где публикуются ссылки на формы.
    # При появлении новой — добавить URL сюда.
    CONFIG_PAGES = [
        # Статистические материалы Роспотребнадзора
        "https://www.rospotrebnadzor.ru/activities/statistical-materials/statictic_details.php?ELEMENT_ID=12640",
    ]

    # Расширения, которые нас интересуют
    TARGET_EXTENSIONS = (".xls", ".xlsx")

    # Слова для фильтрации ссылок — берём только «формы 1»
    KEYWORDS = ("ф 1", "ф1", "форма 1", "рост-сниж", "инфекционн")

    def discover(self) -> list[DiscoveredFile]:
        """Обходит CONFIG_PAGES, собирает ссылки на .xls/.xlsx,
        фильтрует по KEYWORDS, определяет год и регион."""
        found: list[DiscoveredFile] = []
        seen_urls: set[str] = set()

        for page_url in self.CONFIG_PAGES:
            logger.info(f"Discover: обход {page_url}")
            try:
                html = self._fetch(page_url)
            except Exception as e:
                logger.warning(f"Не удалось загрузить {page_url}: {e}")
                continue

            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(" ", strip=True).lower()

                # фильтр по расширению
                if not any(href.lower().endswith(ext) for ext in self.TARGET_EXTENSIONS):
                    continue

                # фильтр по ключевым словам (в href или в тексте ссылки)
                haystack = (href + " " + text).lower()
                if not any(kw in haystack for kw in self.KEYWORDS):
                    continue

                full_url = urljoin(page_url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                filename = full_url.rsplit("/", 1)[-1]
                year = self._extract_year(filename + " " + text)
                region = self._extract_region(text) or "РФ"

                found.append(
                    DiscoveredFile(
                        url=full_url,
                        filename=filename,
                        period=str(year) if year else None,
                        year=year,
                        region=region,
                        meta={"page": page_url, "link_text": text[:200]},
                    )
                )

        logger.success(f"Discover: найдено {len(found)} файлов")
        return found

    def parse(
        self, path: Path, period: str | None = None
    ) -> pl.DataFrame:
        """Парсит .xls формы №1."""
        return parse_form_1_xls(path, period=period)

    # -------- helpers --------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _fetch(self, url: str) -> str:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; data-pipeline/0.2; "
                        "+https://example.local)"
                    )
                },
            )
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text

    @staticmethod
    def _extract_year(text: str) -> int | None:
        import re as _re
        m = _re.search(r"(20\d{2})", text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _extract_region(text: str) -> str | None:
        # Заглушка: Роспотребнадзор публикует свод по РФ.
        # При появлении региональных страниц — доработать.
        if "российск" in text.lower() or "рф" in text.lower():
            return "РФ"
        return None