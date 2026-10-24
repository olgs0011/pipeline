"""Что отдаёт fedstat для /indicator/31165.do с разными Accept?"""
import httpx

URL = "https://www.fedstat.ru/indicator/31165.do"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

VARIANTS = [
    ("без Accept", {"User-Agent": UA}),
    ("Accept: text/html", {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}),
    ("Accept: */*", {"User-Agent": UA, "Accept": "*/*"}),
    ("Accept: application/json", {"User-Agent": UA, "Accept": "application/json"}),
    ("браузерный полный", {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }),
]

with httpx.Client(timeout=20.0, follow_redirects=True) as client:
    for label, headers in VARIANTS:
        r = client.get(URL, headers=headers)
        html = r.text
        has_filters = "filters:" in html
        has_fgrid = "new FGrid" in html
        len_html = len(html)
        marker = "✅" if has_filters and has_fgrid else "❌"
        print(f"{marker} [{label}] len={len_html:>7}  filters={has_filters}  FGrid={has_fgrid}")