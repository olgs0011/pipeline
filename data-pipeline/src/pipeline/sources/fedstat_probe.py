"""Разведка: найти URL, куда FGrid шлёт запрос за данными."""
import re
import httpx

BASE = "https://www.fedstat.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# 1. Скачиваем report.js
print("=== Скачиваем /js/report.js ===")
r = httpx.get(f"{BASE}/js/report.js", timeout=20, headers=HEADERS, follow_redirects=True)
print(f"Status: {r.status_code}, length: {len(r.text)}")
js = r.text

# 2. Ищем все URL внутри report.js
urls = sorted(set(re.findall(r'["\'`](/[^"\'`\s]+)["\'`]', js)))
print(f"\n=== Все относительные URL в report.js ({len(urls)}) ===")
for u in urls:
    if any(k in u.lower() for k in ["data", "indicator", "grid", "export", "download", "api"]):
        print(f"  {u}")

# 3. Ищем ключевые слова вокруг AJAX-вызовов
print("\n=== Контекст вокруг .do / ajax / url ===")
for kw in ["data.do", "ajax", "url:", "$.post", "$.get", "fetch("]:
    idx = js.find(kw)
    if idx > 0:
        print(f"\n--- {kw} (позиция {idx}) ---")
        print(js[max(0, idx - 100): idx + 300])