"""Пробуем POST-запрос на /indicator/data.do с разными форматами."""
import httpx
import json

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# Вариант 1: form-data с id
with httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True) as client:
    print("=== POST /indicator/data.do (form) ===")
    r = client.post(f"{BASE}/indicator/data.do", data={"id": "31165"})
    print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}, len: {len(r.text)}")
    print(r.text[:500])
    print()

    # Вариант 2: JSON
    print("=== POST /indicator/data.do (json) ===")
    r = client.post(
        f"{BASE}/indicator/data.do",
        json={"id": 31165},
    )
    print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}, len: {len(r.text)}")
    print(r.text[:500])
    print()

    # Вариант 3: известный формат FGrid — dataIds
    # Фильтры: показатель=31165, год=2024, ОКАТО=1688487 (РФ), период=год, единица=1341910
    print("=== POST /indicator/data.do (grid dataIds) ===")
    payload = {
        "id": 31165,
        "dataIds": [31165, 2024, 1688487, 1341910, 1558883],  # показатель, год, ОКАТО, единица, период
    }
    r = client.post(f"{BASE}/indicator/data.do", json=payload)
    print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}, len: {len(r.text)}")
    print(r.text[:800])
