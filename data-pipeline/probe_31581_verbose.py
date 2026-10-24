"""Полная отладка POST для 31581 через FedstatClient."""
import polars as pl
from pipeline.logging import setup_logging
from pipeline.sources.fedstat import (
    FedstatClient,
    _normalize_results,
    _classify_filter,
    _resolve_secondary_candidates,
)

setup_logging()

BODY = (
    "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
    "&selectedFilterIds=0_31581"
    "&selectedFilterIds=3_2015"
    "&selectedFilterIds=57831_1688487"
    "&selectedFilterIds=58097_1707673"
    "&selectedFilterIds=30611_950475"
    "&selectedFilterIds=33560_1558883"
)

with FedstatClient() as client:
    meta = client.fetch_indicator_meta(31581)
    print(f"Filters: {len(meta.filters)}")

    for oid, f in meta.filters.items():
        kind = _classify_filter(f)
        print(f"  [{oid}] {f.title!r} kind={kind}")
        if kind == "secondary":
            cands = _resolve_secondary_candidates(f, meta.title)
            print(f"      кандидаты: {cands}")

    # Прямой POST
    print("\n=== Прямой POST ===")
    r = client.client.post("/indicator/dataGrid.do?id=31581", content=BODY)
    print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
    data = r.json()
    rows = data.get("results", [])
    print(f"rows из JSON: {len(rows)}")
    if rows:
        print(f"Первый row: {rows[0]}")

        # Пробуем нормализовать
        df = _normalize_results(rows)
        print(f"\nПосле _normalize_results: {df.shape}")
        if not df.is_empty():
            print(df)

    # Стратегии из _generate_strategies
    print("\n=== Стратегии для 2015 ===")
    strategies = client._generate_strategies(meta, 2015, "Российская Федерация")
    print(f"Всего стратегий: {len(strategies)}")
    for i, body in enumerate(strategies):
        # Пробуем каждый
        r = client.client.post("/indicator/dataGrid.do?id=31581", content=body)
        try:
            data = r.json()
            n = len(data.get("results", []))
            print(f"  #{i+1}: {n} строк")
        except Exception as e:
            print(f"  #{i+1}: ошибка {e}")