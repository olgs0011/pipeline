"""Пробуем GET с параметром года."""
import httpx

# x117 (Джини) — индикатор 31165
for year in [2015, 2018, 2020, 2022]:
    url = f"https://www.fedstat.ru/indicator/dataGrid.do?id=31165"
    params = {
        "lineObjectIds": "57831",  # регион
        "columnObjectIds": "3",     # год
        "selectedFilterIds": f"3_{year}",  # фильтр года
    }
    r = httpx.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    print(f"\n=== {year} ===")
    print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
    print(r.text[:300])