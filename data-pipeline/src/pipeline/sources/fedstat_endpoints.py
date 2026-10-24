"""Проверяем типичные endpoint'ы ЕМИСС."""
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

CANDIDATES = [
    "/indicator/data.do?id=31165",
    "/indicator/data.do",
    "/api/indicator/31165",
    "/api/data/31165",
    "/indicator/31165/data",
    "/indicator/data?id=31165",
    "/opendata/31165",
]

with httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
    for path in CANDIDATES:
        try:
            r = client.get(f"{BASE}{path}")
            ctype = r.headers.get("content-type", "?")
            print(f"{r.status_code}  {ctype[:40]:40}  {path}")
            if r.status_code == 200 and len(r.text) < 2000:
                print(f"     └─ {r.text[:200]}")
        except Exception as e:
            print(f"ERR   {path}: {e}")