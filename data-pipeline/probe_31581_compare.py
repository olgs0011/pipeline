"""Сравниваем запрос из check-скрипта и через FedstatClient."""
import httpx
from pipeline.sources.fedstat import FedstatClient

# ============================================================
# Вариант A: чистый httpx (как в check_31581_years.py)
# ============================================================
BODY = (
    "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
    "&selectedFilterIds=0_31581"
    "&selectedFilterIds=3_2015"
    "&selectedFilterIds=57831_1688487"
    "&selectedFilterIds=58097_1707673"
    "&selectedFilterIds=30611_950475"
    "&selectedFilterIds=33560_1558883"
)
URL = "https://www.fedstat.ru/indicator/dataGrid.do?id=31581"

HEADERS_MIN = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}

print("=== A: чистый httpx (минимальные заголовки) ===")
r = httpx.post(URL, content=BODY, headers=HEADERS_MIN, timeout=20)
print(f"Status: {r.status_code}, ctype: {r.headers.get('content-type')}")
print(f"Body: {r.text[:300]}")
print()

# ============================================================
# Вариант B: через FedstatClient
# ============================================================
print("=== B: FedstatClient (полные заголовки + сессия) ===")
with FedstatClient() as client:
    # Сначала GET страницы (как делает fetch_indicator_meta)
    client.fetch_indicator_page(31581)
    # Затем POST
    r2 = client.client.post("/indicator/dataGrid.do?id=31581", content=BODY)
    print(f"Status: {r2.status_code}, ctype: {r2.headers.get('content-type')}")
    print(f"Body: {r2.text[:300]}")
print()

# ============================================================
# Вариант C: тот же httpx, но с полными заголовками FedstatClient
# ============================================================
print("=== C: httpx с заголовками как у FedstatClient ===")
HEADERS_FULL = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
r3 = httpx.post(URL, content=BODY, headers=HEADERS_FULL, timeout=20)
print(f"Status: {r3.status_code}, ctype: {r3.headers.get('content-type')}")
print(f"Body: {r3.text[:300]}")