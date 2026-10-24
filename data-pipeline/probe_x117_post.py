"""Проверяем _try_year для x117 (31165) за 2020."""
from pipeline.logging import setup_logging
from pipeline.sources.fedstat import FedstatClient

setup_logging()

with FedstatClient() as client:
    meta = client.fetch_indicator_meta(31165)
    print(f"\nTitle: {meta.title}")
    print(f"Line: {meta.line_filters}")
    print(f"Column: {meta.column_filters}")
    print(f"Filters: {len(meta.filters)}")

    # Прямой вызов _try_year для 2020
    df = client._try_year(meta, 2020, "Российская Федерация")
    print(f"\n_try_year(2020): {df.shape}")
    if not df.is_empty():
        print(df)

    # Пробуем ещё года
    for year in [2015, 2018, 2021]:
        df = client._try_year(meta, year, "Российская Федерация")
        print(f"_try_year({year}): {df.shape}")