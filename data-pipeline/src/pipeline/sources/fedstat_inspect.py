"""Разведка страницы /indicator/data.do — что в ней и куда она шлёт AJAX."""
import re
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# 1. Скачиваем HTML страницы data.do
r = httpx.get(f"{BASE}/indicator/data.do?id=31165", timeout=20, headers=HEADERS, follow_redirects=True)
print(f"Status: {r.status_code}, len: {len(r.text)}, final URL: {r.url}")

html = r.text
open("fedstat_data_do.html", "w", encoding="utf-8").write(html)
print("Saved: fedstat_data_do.html")

# 2. Ищем все inline-скрипты
scripts = re.findall(r"<script[^>]*>(.+?)</script>", html, re.DOTALL)
print(f"\n=== Inline scripts: {len(scripts)} ===")
for i, s in enumerate(scripts[:10]):
    s_clean = s.strip()
    if s_clean:
        print(f"\n--- script[{i}] ({len(s_clean)} chars) ---")
        print(s_clean[:500])

# 3. Ищем все ссылки на .do endpoints
do_links = sorted(set(re.findall(r'["\'`]([^"\'`]*\.do[^"\'`]*)["\'`]', html)))
print(f"\n=== Все .do-ссылки в HTML ({len(do_links)}) ===")
for link in do_links:
    print(f"  {link}")

# 4. Ищем AJAX-вызовы
for kw in ["$.ajax", "$.post", "$.get", "fetch(", "XMLHttpRequest", "url:", "action:"]:
    idx = html.find(kw)
    if idx > 0:
        print(f"\n--- {kw} (позиция {idx}) ---")
        print(html[max(0, idx - 150): idx + 300])