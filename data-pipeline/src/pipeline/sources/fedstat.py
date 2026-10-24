"""Клиент ЕМИСС (fedstat.ru) с динамическим resolve фильтров и fallback.

Логика:
  1. GET /indicator/{id}.do → HTML с JSON `filters: {...}`
  2. Парсим ВСЕ фильтры (owner_id → {title, values, all, indicator})
  3. Для каждого фильтра выбираем значения:
     - Год       → переданные годы
     - ОКАТО     → «Российская Федерация» (или ВСЕ субъекты РФ при all_regions=True)
     - Период    → «за год»
     - Единица   → checked=true
     - Показатель → checked=true
     - Прочее    → «ВСЕГО» / «ВСЕГО (...)» / checked / первое
  4. POST /indicator/dataGrid.do?id={id} ОТДЕЛЬНО ПО КАЖДОМУ ГОДУ
  5. FALLBACK: альтернативные значения secondary-фильтров
  6. Парсим JSON → long-format DataFrame (year, region, period_value_id, value)

Важно: ЕМИСС НЕ отдаёт регион в ответе (нет dim57831).
Поэтому в режиме all_regions=True мы сами подставляем название региона,
который запросили в body (см. _fetch_all_regions_one_year_async).
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from itertools import product

import httpx
import polars as pl
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://www.fedstat.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

DEFAULT_REGION_TITLE = "Российская Федерация"
DEFAULT_PERIOD_HINT = "за год"

# Регионы, которые НЕ являются субъектами РФ — исключаем в режиме all_regions
_SKIP_REGION_PATTERNS = (
    "российская федерация",           # РФ в целом
    "федеральный округ",               # ЦФО, СЗФО, ...
    "без учета новых субъектов",       # новый агрегат с 2023
    "экономический район",
)

EMPTY_SCHEMA = {
    "year": pl.Int32,
    "region": pl.Utf8,
    "period_value_id": pl.Int64,
    "value": pl.Float64,
}

# Debug
DEBUG_LOG_BODIES = False
DEBUG_HEAD_N = 3


# ───────────────────────── структуры ─────────────────────────


@dataclass
class FilterValue:
    id: int
    title: str
    checked: bool


@dataclass
class Filter:
    owner_id: int
    title: str
    all: bool
    is_indicator: bool
    values: list[FilterValue] = field(default_factory=list)


@dataclass
class IndicatorMeta:
    id: int
    title: str
    unit: str
    line_filters: list[int] = field(default_factory=list)
    column_filters: list[int] = field(default_factory=list)
    filters: dict[int, Filter] = field(default_factory=dict)


# ───────────────────────── парсинг HTML ─────────────────────────


def _decode_unicode(s: str) -> str:
    if "\\u" not in s:
        return s
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        return s


def _find_braces_block(text: str, start_idx: int) -> tuple[int, int] | None:
    if start_idx >= len(text) or text[start_idx] != "{":
        return None
    depth = 0
    for i in range(start_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return start_idx, i + 1
    return None


def _extract_filters_block(html: str) -> str | None:
    m = re.search(r"filters:\s*\{", html)
    if not m:
        return None
    brace_start = m.end() - 1
    rng = _find_braces_block(html, brace_start)
    if not rng:
        return None
    return html[rng[0]:rng[1]]


def _parse_filter_values(values_block: str) -> list[FilterValue]:
    values: list[FilterValue] = []
    for m in re.finditer(r"(\d+)\s*:\s*\{", values_block):
        vid = int(m.group(1))
        brace_start = m.end() - 1
        rng = _find_braces_block(values_block, brace_start)
        if not rng:
            continue
        block = values_block[rng[0]:rng[1]]
        title_m = re.search(r"title:\s*'([^']*)'", block)
        title = _decode_unicode(title_m.group(1)) if title_m else ""
        checked_m = re.search(r"checked:\s*(true|false)", block)
        checked = (checked_m.group(1) == "true") if checked_m else False
        values.append(FilterValue(id=vid, title=title, checked=checked))
    return values


def _parse_filters(filters_block: str) -> dict[int, Filter]:
    filters: dict[int, Filter] = {}
    for m in re.finditer(r"(\d+)\s*:\s*\{", filters_block):
        owner_id = int(m.group(1))
        brace_start = m.end() - 1
        rng = _find_braces_block(filters_block, brace_start)
        if not rng:
            continue
        block = filters_block[rng[0]:rng[1]]

        if "values:" not in block:
            continue

        title_m = re.search(r"title:\s*'([^']*)'", block)
        title = _decode_unicode(title_m.group(1)) if title_m else ""

        all_m = re.search(r"all:\s*(true|false)", block)
        all_val = (all_m.group(1) == "true") if all_m else False

        ind_m = re.search(r"indicator:\s*(true|false)", block)
        is_indicator = (ind_m.group(1) == "true") if ind_m else False

        values_m = re.search(r"values:\s*\{", block)
        if not values_m:
            continue
        v_start = values_m.end() - 1
        v_rng = _find_braces_block(block, v_start)
        if not v_rng:
            continue
        values_block = block[v_rng[0]:v_rng[1]]

        values = _parse_filter_values(values_block)
        if not values:
            continue

        filters[owner_id] = Filter(
            owner_id=owner_id,
            title=title,
            all=all_val,
            is_indicator=is_indicator,
            values=values,
        )
    return filters


def _extract_line_column(html: str) -> tuple[list[int], list[int]]:
    left_m = re.search(r"left_columns:\s*\[([^\]]*)\]", html)
    top_m = re.search(r"top_columns:\s*\[([^\]]*)\]", html)

    def parse_ids(s: str | None) -> list[int]:
        if not s:
            return []
        return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]

    return (
        parse_ids(left_m.group(1)) if left_m else [],
        parse_ids(top_m.group(1)) if top_m else [],
    )


# ───────────────────────── resolve ─────────────────────────


def _resolve_okato(filt: Filter, region_title: str) -> list[int]:
    for v in filt.values:
        if v.title.strip().lower() == region_title.lower():
            return [v.id]
    for v in filt.values:
        if region_title.lower() in v.title.lower():
            return [v.id]
    for v in filt.values:
        if v.checked:
            return [v.id]
    return [filt.values[0].id] if filt.values else []


def _resolve_okato_all(filt: Filter) -> list[tuple[int, str]]:
    """ID и названия субъектов РФ (без РФ в целом, ФО, автономных агрегатов).

    Возвращает [(id, title), ...] — чтобы потом подставить название в результат.
    """
    result: list[tuple[int, str]] = []
    for v in filt.values:
        t = v.title.lower().strip()
        if any(p in t for p in _SKIP_REGION_PATTERNS):
            continue
        result.append((v.id, v.title))
    return result


def _resolve_period(filt: Filter) -> list[int]:
    for v in filt.values:
        if DEFAULT_PERIOD_HINT in v.title.lower():
            return [v.id]
    for v in filt.values:
        if v.checked:
            return [v.id]
    return [filt.values[0].id] if filt.values else []


def _resolve_unit(filt: Filter) -> list[int]:
    for v in filt.values:
        if v.checked:
            return [v.id]
    return [filt.values[0].id] if filt.values else []


def _resolve_indicator(filt: Filter) -> list[int]:
    for v in filt.values:
        if v.checked:
            return [v.id]
    return [filt.values[0].id] if filt.values else []


def _resolve_forced(filt: Filter, extra_filters: dict[str, str]) -> int | None:
    """Явное значение из extra_filters → id."""
    if not extra_filters:
        return None
    title_low = filt.title.lower()
    for key, wanted in extra_filters.items():
        if key.lower() not in title_low:
            continue
        wanted_low = str(wanted).lower()
        for v in filt.values:
            if v.title.strip().lower() == wanted_low:
                return v.id
        for v in filt.values:
            if wanted_low in v.title.lower():
                return v.id
        if wanted_low in ("все", "всего", "all"):
            for v in filt.values:
                if "всего" in v.title.lower():
                    return v.id
        logger.warning(
            f"[{filt.title}] явный фильтр {key}={wanted!r} не найден среди "
            f"{len(filt.values)} значений"
        )
    return None


def _resolve_secondary_candidates(
    filt: Filter,
    indicator_title: str = "",
) -> list[int]:
    """КАНДИДАТЫ для secondary-фильтра."""
    seen: set[int] = set()
    candidates: list[int] = []

    def add(vid: int) -> None:
        if vid not in seen:
            seen.add(vid)
            candidates.append(vid)

    title_low = filt.title.lower()
    ind_low = indicator_title.lower()

    if "должност" in title_low:
        keywords = [
            "средний медицинский персонал",
            "врачи",
            "средний медперсонал",
        ]
        for kw in keywords:
            if kw in ind_low:
                for v in filt.values:
                    if kw in v.title.lower():
                        add(v.id)
                        break
        for v in filt.values:
            if v.checked:
                add(v.id)
                break
        for v in filt.values:
            t = v.title.lower()
            if "всего" in t or "средн" in t:
                add(v.id)
        if filt.values:
            add(filt.values[0].id)
        return candidates

    for v in filt.values:
        if v.title.strip().lower() == "всего":
            add(v.id)
            break
    for v in filt.values:
        t = v.title.lower()
        if "всего" in t or "всем" in t or "по всем" in t:
            add(v.id)
    for v in filt.values:
        if v.checked:
            add(v.id)
            break
    if filt.values:
        add(filt.values[0].id)

    logger.debug(
        f"[{filt.title}] кандидаты: "
        f"{[(c, next((v.title for v in filt.values if v.id == c), '?')) for c in candidates[:5]]}"
    )
    return candidates


def _classify_filter(filt: Filter) -> str:
    """'year' | 'okato' | 'period' | 'unit' | 'indicator' | 'secondary'."""
    t = filt.title.lower()
    if t == "год":
        return "year"
    if "окато" in t or "административно" in t:
        return "okato"
    if "период" in t:
        return "period"
    if "единица" in t:
        return "unit"
    if filt.is_indicator or t == "показатель":
        return "indicator"
    return "secondary"


# ───────────────────────── normalize ─────────────────────────


def _normalize_results(rows: list[dict]) -> pl.DataFrame:
    """Wide → long-format.

    ВНИМАНИЕ: ЕМИСС НЕ отдаёт dim57831 в ответе, поэтому region будет "РФ".
    Настоящий регион подставляется выше — в _fetch_all_regions_one_year_async.
    """
    normalized: list[dict] = []
    for row in rows:
        region = row.get("dim57831", "") or "РФ"

        year_from_row: int | None = None
        y = row.get("dim3")
        if y is not None:
            try:
                year_from_row = int(y)
            except (ValueError, TypeError):
                pass

        for col_key, val in row.items():
            if not col_key.startswith("dim"):
                continue
            if val is None:
                continue
            if col_key in ("dim57831", "dim30611", "dim3"):
                continue

            try:
                value = float(str(val).replace(",", "."))
            except (ValueError, TypeError):
                continue

            year = year_from_row
            if year is None:
                m_year = re.search(r"(20\d{2}|19\d{2})_", col_key)
                if m_year:
                    year = int(m_year.group(1))
            if year is None:
                continue

            m_i = re.search(r"_i(\d+)$", col_key)
            period_value_id = int(m_i.group(1)) if m_i else None

            normalized.append({
                "year": year,
                "region": region,
                "period_value_id": period_value_id,
                "value": value,
            })

    if not normalized:
        return pl.DataFrame(schema=EMPTY_SCHEMA)

    df = pl.DataFrame(normalized)
    df = df.unique(subset=["year", "region", "period_value_id"], keep="first")
    return df


# ───────────────────────── клиент ─────────────────────────


class FedstatClient:
    """Клиент ЕМИСС."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.client = httpx.Client(
            base_url=BASE,
            timeout=timeout,
            follow_redirects=True,
            headers=HEADERS,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "FedstatClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=15),
           reraise=True)
    def fetch_indicator_page(self, indicator_id: int) -> str:
        logger.info(f"GET /indicator/{indicator_id}.do")
        r = self.client.get(f"/indicator/{indicator_id}.do")
        r.raise_for_status()
        return r.text

    def fetch_indicator_meta(self, indicator_id: int) -> IndicatorMeta:
        html = self.fetch_indicator_page(indicator_id)

        title_m = re.search(r"title:\s*'([^']+)'", html)
        unit_m = re.search(r"unit:\s*'([^']*)'", html)
        title = _decode_unicode(title_m.group(1)) if title_m else "unknown"
        unit = unit_m.group(1) if unit_m else "-"

        line, column = _extract_line_column(html)

        filters_block = _extract_filters_block(html)
        filters: dict[int, Filter] = {}
        if filters_block:
            filters = _parse_filters(filters_block)
            logger.info(
                f"[{indicator_id}] filters: {len(filters)} шт "
                f"(line={line}, column={column})"
            )
        else:
            logger.warning(f"[{indicator_id}] filters не найдены в HTML")

        return IndicatorMeta(
            id=indicator_id,
            title=title,
            unit=unit,
            line_filters=line,
            column_filters=column,
            filters=filters,
        )

    # ─────────── генерация стратегий ───────────
    #
    # Возвращает list[tuple[body_str, region_title | None]]
    # region_title заполняется ТОЛЬКО в режиме all_regions=True.

    def _generate_strategies(
        self,
        meta: IndicatorMeta,
        year: int,
        region_title: str,
        *,
        extra_filters: dict[str, str] | None = None,
        all_regions: bool = False,
    ) -> list[tuple[str, str | None]]:
        extra_filters = extra_filters or {}
        filter_plans: dict[int, list[list[int]]] = {}
        # region_names[owner_id] = {value_id: title}
        region_names: dict[int, dict[int, str]] = {}
        okato_owner_id: int | None = None

        for owner_id, filt in meta.filters.items():
            kind = _classify_filter(filt)
            if kind == "year":
                filter_plans[owner_id] = [[year]]
            elif kind == "okato":
                okato_owner_id = owner_id
                if all_regions:
                    pairs = _resolve_okato_all(filt)
                    filter_plans[owner_id] = [[rid] for rid, _ in pairs]
                    region_names[owner_id] = {rid: title for rid, title in pairs}
                else:
                    filter_plans[owner_id] = [_resolve_okato(filt, region_title)]
            elif kind == "period":
                filter_plans[owner_id] = [_resolve_period(filt)]
            elif kind == "unit":
                filter_plans[owner_id] = [_resolve_unit(filt)]
            elif kind == "indicator":
                filter_plans[owner_id] = [_resolve_indicator(filt)]
            else:
                forced = _resolve_forced(filt, extra_filters)
                if forced is not None:
                    filter_plans[owner_id] = [[forced]]
                    continue
                candidates = _resolve_secondary_candidates(filt, meta.title)
                if all_regions:
                    candidates = candidates[:1]
                else:
                    title_low = filt.title.lower()
                    if "окфс" in title_low or "собственност" in title_low:
                        candidates = candidates[:2]
                    elif "должност" in title_low:
                        candidates = candidates[:3]
                    else:
                        candidates = candidates[:2]
                filter_plans[owner_id] = [[c] for c in candidates]

        owner_ids = list(filter_plans.keys())
        if not owner_ids:
            return []

        variants_lists = [filter_plans[oid] for oid in owner_ids]
        strategies: list[tuple[str, str | None]] = []

        for combo in product(*variants_lists):
            parts: list[str] = []
            for lid in meta.line_filters:
                parts.append(f"lineObjectIds={lid}")
            for cid in meta.column_filters:
                parts.append(f"columnObjectIds={cid}")

            region_for_body: str | None = None
            for owner_id, value_list in zip(owner_ids, combo):
                for v in value_list:
                    parts.append(f"selectedFilterIds={owner_id}_{v}")
                    # Если это ОКАТО и мы знаем название — запомним
                    if (
                        all_regions
                        and okato_owner_id is not None
                        and owner_id == okato_owner_id
                    ):
                        region_for_body = region_names.get(owner_id, {}).get(v)

            strategies.append(("&".join(parts), region_for_body))

        return strategies

    # ─────────── fetch одного года (одна победа) ───────────

    def _try_year(
        self,
        meta: IndicatorMeta,
        year: int,
        region_title: str,
        *,
        extra_filters: dict[str, str] | None = None,
    ) -> pl.DataFrame:
        strategies = self._generate_strategies(
            meta, year, region_title, extra_filters=extra_filters
        )
        url = f"/indicator/dataGrid.do?id={meta.id}"

        for idx, (body, _) in enumerate(strategies):
            try:
                logger.debug(f"[{meta.id}] {year}: стратегия #{idx + 1}: {body}")
                r = self.client.post(url, content=body)
                if r.status_code != 200:
                    continue
                ctype = r.headers.get("content-type", "")
                if "json" not in ctype:
                    continue
                rows = r.json().get("results", [])
                if rows:
                    return _normalize_results(rows)
            except Exception as e:
                logger.debug(f"[{meta.id}] {year} стратегия #{idx+1}: {e}")
                continue

        return pl.DataFrame(schema=EMPTY_SCHEMA)

    # ─────────── async: все регионы за год ───────────

    async def _fetch_all_regions_one_year_async(
        self,
        meta: IndicatorMeta,
        year: int,
        *,
        extra_filters: dict[str, str] | None = None,
        concurrency: int = 10,
    ) -> pl.DataFrame:
        strategies = self._generate_strategies(
            meta, year, DEFAULT_REGION_TITLE,
            extra_filters=extra_filters,
            all_regions=True,
        )
        url = f"/indicator/dataGrid.do?id={meta.id}"
        total = len(strategies)
        logger.info(f"[{meta.id}] {year}: {total} регионов, concurrency={concurrency}")

        if DEBUG_LOG_BODIES:
            for i in range(min(DEBUG_HEAD_N, len(strategies))):
                logger.info(f"[{meta.id}] {year} BODY#{i+1}: {strategies[i][0]}")

        sem = asyncio.Semaphore(concurrency)
        dfs: list[pl.DataFrame] = []
        empties = 0
        errors = 0

        async with httpx.AsyncClient(
            base_url=BASE, timeout=30.0, follow_redirects=True, headers=HEADERS
        ) as ac:
            async def one(body: str, region_title: str | None, idx: int) -> pl.DataFrame | None:
                nonlocal empties, errors
                async with sem:
                    try:
                        r = await ac.post(url, content=body)
                        if r.status_code != 200:
                            errors += 1
                            return None
                        ctype = r.headers.get("content-type", "")
                        if "json" not in ctype:
                            errors += 1
                            return None
                        rows = r.json().get("results", [])
                        if not rows:
                            empties += 1
                            if empties == 1:
                                logger.info(
                                    f"[{meta.id}] {year} EMPTY#{idx+1}: {body}"
                                )
                            return None
                        df = _normalize_results(rows)
                        # ГЛАВНОЕ: подставляем название региона
                        if region_title is not None and not df.is_empty():
                            df = df.with_columns(
                                pl.lit(region_title).alias("region")
                            )
                        return df
                    except Exception as e:
                        errors += 1
                        logger.debug(f"[{meta.id}] {year} #{idx+1}: {e}")
                        return None

            results = await asyncio.gather(
                *(one(body, rt, i) for i, (body, rt) in enumerate(strategies)),
                return_exceptions=False,
            )

        for df in results:
            if df is not None and not df.is_empty():
                dfs.append(df)

        logger.info(
            f"[{meta.id}] {year}: пусто={empties}, ошибок={errors}, "
            f"непустых={len(dfs)}"
        )

        if not dfs:
            return pl.DataFrame(schema=EMPTY_SCHEMA)

        merged = pl.concat(dfs, how="diagonal").unique(
            subset=["year", "region", "period_value_id"], keep="first"
        )
        logger.info(
            f"[{meta.id}] {year}: собрано {merged.height} строк "
            f"по {merged['region'].n_unique()} регионам"
        )
        return merged

    def _fetch_all_regions_one_year(
        self,
        meta: IndicatorMeta,
        year: int,
        *,
        extra_filters: dict[str, str] | None = None,
        concurrency: int = 10,
    ) -> pl.DataFrame:
        return asyncio.run(
            self._fetch_all_regions_one_year_async(
                meta, year, extra_filters=extra_filters, concurrency=concurrency
            )
        )

    # ─────────── главный метод ───────────

    def fetch_data(
        self,
        indicator_id: int,
        years: list[int] | None = None,
        *,
        meta: IndicatorMeta | None = None,
        region_title: str = DEFAULT_REGION_TITLE,
        extra_filters: dict[str, str] | None = None,
        all_regions: bool = False,
        concurrency: int = 10,
    ) -> pl.DataFrame:
        if years is None:
            years = []

        if meta is None:
            meta = self.fetch_indicator_meta(indicator_id)

        # ── ШАГ 1: GET ──
        df_get = pl.DataFrame(schema=EMPTY_SCHEMA)
        try:
            r = self.client.get(f"/indicator/dataGrid.do?id={indicator_id}")
            if "json" in r.headers.get("content-type", ""):
                rows = r.json().get("results", [])
                if rows:
                    df_get = _normalize_results(rows)
        except Exception as e:
            logger.debug(f"[{indicator_id}] GET не сработал: {e}")

        years_in_get: set[int] = set()
        if not df_get.is_empty() and "year" in df_get.columns:
            years_in_get = set(df_get["year"].unique().to_list())
            logger.info(f"[{indicator_id}] GET вернул годы: {sorted(years_in_get)}")

        # ── ШАГ 2: POST ──
        missing_years = [y for y in years if y not in years_in_get]
        all_dfs: list[pl.DataFrame] = []
        if not df_get.is_empty():
            all_dfs.append(df_get)

        if DEBUG_LOG_BODIES and missing_years:
            missing_years = missing_years[:1]
            logger.info(f"[{indicator_id}] DEBUG: обрабатываем только {missing_years}")

        for year in missing_years:
            if all_regions:
                df = self._fetch_all_regions_one_year(
                    meta, year, extra_filters=extra_filters, concurrency=concurrency
                )
            else:
                df = self._try_year(
                    meta, year, region_title, extra_filters=extra_filters
                )
            if not df.is_empty():
                all_dfs.append(df)

        # ── ШАГ 3: merge ──
        if not all_dfs:
            return pl.DataFrame(schema=EMPTY_SCHEMA)

        result = pl.concat(all_dfs, how="diagonal")
        result = result.unique(
            subset=["year", "region", "period_value_id"], keep="first"
        )
        logger.success(f"[{indicator_id}] Long: {result.shape}")
        return result


# ───────────────────────── тест ─────────────────────────


if __name__ == "__main__":
    from pipeline.logging import setup_logging

    setup_logging()

    TEST_IDS = [31165, 33458, 31565, 31581, 31177, 40642]

    with FedstatClient() as client:
        for ind_id in TEST_IDS:
            print(f"\n{'=' * 60}")
            print(f"Индикатор {ind_id}")
            print(f"{'=' * 60}")
            try:
                meta = client.fetch_indicator_meta(ind_id)
                print(f"Title: {meta.title}")
                print(f"Line:  {meta.line_filters}")
                print(f"Column: {meta.column_filters}")
                print(f"Filters: {len(meta.filters)}")
                for oid, f in meta.filters.items():
                    kind = _classify_filter(f)
                    print(f"  [{oid}] {f.title!r} values={len(f.values)} kind={kind}")

                df = client.fetch_data(
                    ind_id, years=list(range(2015, 2026)), meta=meta
                )
                print(f"→ {df.shape} строк")
                if not df.is_empty():
                    print(df.head(3))
            except Exception as e:
                print(f"❌ {type(e).__name__}: {e}")