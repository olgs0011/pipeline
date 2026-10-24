"""Найти AJAX-endpoint в FGrid.js."""
import re
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# FGrid.js — ключевой файл с AJAX
r = httpx.get(
    f"{BASE}/common/js/fgrid/FGrid.js?v=13527C1",
    timeout=20,
    headers=HEADERS,
    follow_redirects=True,
)
print(f"Status: {r.status_code}, length: {len(r.text)}")
js = r.text
open("FGrid.js", "w", encoding="utf-8").write(js)
print("Saved: FGrid.js")

# Ищем AJAX-вызовы
print("\n=== Ищем 'ajax' / '$.post' / '$.get' / 'url' ===")
for kw in ["$.ajax", "$.post", "$.get", ".do", "url:", "url =", "action:", "load("]:
    positions = [m.start() for m in re.finditer(re.escape(kw), js)]
    print(f"\n--- {kw} — {len(positions)} совпадений ---")
    for pos in positions[:5]:
        snippet = js[max(0, pos - 80): pos + 200].replace("\n", " ").replace("  ", " ")
        print(f"  [{pos}] {snippet[:250]}")

# Ищем все .do URL
print("\n=== Все .do URL в FGrid.js ===")
do_urls = sorted(set(re.findall(r'["\'`](/[^"\'`\s]*\.do[^"\'`\s]*)["\'`]', js)))
for u in do_urls:
    print(f"  {u}")

# Ищем все строки вида '/indicator/...'
print("\n=== Все '/indicator/...' пути ===")
indicator_paths = sorted(set(re.findall(r'["\'`](/indicator/[^"\'`\s]+)["\'`]', js)))
for p in indicator_paths:
    print(f"  {p}")