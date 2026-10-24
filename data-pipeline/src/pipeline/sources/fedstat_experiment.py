"""Эксперимент: как передать годы и регионы в dataGrid.do."""
import json
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": f"{BASE}/indicator/31165.do",
}


def show(label: str, r: httpx.Response) -> None:
    ctype = r.headers.get("content-type", "?").split(";")[0]
    print(f"\n=== {label} ===")
    print(f"Status: {r.status_code}, ctype: {ctype}, len: {len(r.text)}")
    print(r.text[:600])
    # Пробуем распарсить JSON
    try:
        data = r.json()
        if "results" in data:
            print(f"  ✅ results: {len(data['results'])} rows")
            print(f"  Первая запись: {data['results'][0]}")
    except Exception:
        pass


with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
    # 1. GET базовый
    r = client.get(f"{BASE}/indicator/dataGrid.do?id=31165")
    show("GET базовый", r)

    # 2. GET с параметрами фильтров (предположение)
    params = {
        "id": 31165,
        "dataIds[]": [31165, 2015, 1688487, 1341910, 1558883],
    }
    r = client.get(f"{BASE}/indicator/dataGrid.do", params=params)
    show("GET с dataIds[] (2015, РФ, год)", r)

    # 3. POST с dataIds
    payload = {
        "id": 31165,
        "dataIds": [31165, 2015, 1688487, 1341910, 1558883],
    }
    r = client.post(f"{BASE}/indicator/dataGrid.do", json=payload)
    show("POST с dataIds", r)

    # 4. POST с filters (как FGrid может шлать)
    payload = {
        "id": 31165,
        "filters": {
            "57831": [1688487],
            "3": [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024],
            "30611": [1341910],
            "33560": [1558883],
        },
    }
    r = client.post(f"{BASE}/indicator/dataGrid.do", json=payload)
    show("POST с filters (все годы 2015-2024)", r)