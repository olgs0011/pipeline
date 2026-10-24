"""Проверяем альтернативные способы получить данные за 2020 для x117 (31165)."""
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Вариант 1: POST /indicator/dataGrid.do (как в _try_year)
print("=== 1. POST /indicator/dataGrid.do ===")
body = (
    "lineObjectIds=57831&lineObjectIds=30611&lineObjectIds=3"
    "&columnObjectIds=33560"
    "&selectedFilterIds=0_31165"
    "&selectedFilterIds=3_2020"
    "&selectedFilterIds=57831_1688487"
    "&selectedFilterIds=30611_1341910"
    "&selectedFilterIds=33560_1558883"
)
r = httpx.post(f"{BASE}/indicator/dataGrid.do?id=31165", content=body, headers=HEADERS, timeout=20)
print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
print(f"Body: {r.text[:300]}")
print()

# Вариант 2: GET с другими параметрами
print("=== 2. GET с query string (все параметры) ===")
r = httpx.get(
    f"{BASE}/indicator/dataGrid.do",
    params={
        "id": "31165",
        "lineObjectIds": "57831",
        "columnObjectIds": "3",
        "selectedFilterIds": "3_2020",
    },
    headers=HEADERS,
    timeout=20,
)
print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
print(f"Body: {r.text[:300]}")
print()

# Вариант 3: POST /indicator/data.do (другой endpoint)
print("=== 3. POST /indicator/data.do ===")
body = "id=31165&year=2020&region=1688487"
r = httpx.post(f"{BASE}/indicator/data.do", content=body, headers=HEADERS, timeout=20)
print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
print(f"Body: {r.text[:300]}")
print()

# Вариант 4: POST с dataIds (как FGrid)
print("=== 4. POST /indicator/dataGrid.do с dataIds ===")
body = "dataIds=31165&dataIds=2020&dataIds=1688487&dataIds=1341910&dataIds=1558883"
r = httpx.post(f"{BASE}/indicator/dataGrid.do?id=31165", content=body, headers=HEADERS, timeout=20)
print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
print(f"Body: {r.text[:300]}")
print()