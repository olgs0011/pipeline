"""Проверяем downloadData.do — самый простой endpoint для скачивания."""
import httpx

BASE = "https://www.fedstat.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# Пробуем разные форматы и параметры
CANDIDATES = [
    "/indicator/downloadData.do?id=31165&format=xlsx",
    "/indicator/downloadData.do?id=31165&format=csv",
    "/indicator/downloadData.do?id=31165&format=xls",
    "/indicator/downloadData.do?id=31165&format=sdmx",
    "/indicator/downloadData.do?id=31165",
    "/indicator/dataGrid.do?id=31165",
]

with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
    for path in CANDIDATES:
        try:
            r = client.get(f"{BASE}{path}")
            ctype = r.headers.get("content-type", "?").split(";")[0]
            cdisp = r.headers.get("content-disposition", "")
            clen = len(r.content)
            marker = "✅" if ctype not in ("text/html",) else "  "
            print(f"{marker} {r.status_code}  {ctype:50}  {clen:>8}  {path}")
            if cdisp:
                print(f"     └─ Content-Disposition: {cdisp}")
            if ctype not in ("text/html",):
                # Сохраним первую успешную бинарную загрузку
                fname = path.split("format=")[-1].split("&")[0] if "format=" in path else "out"
                out = f"fedstat_probe_31165.{fname}"
                with open(out, "wb") as f:
                    f.write(r.content)
                print(f"     └─ Saved: {out} ({len(r.content)} bytes)")
                # Если не бинарник — покажем текст
                if "text" in ctype or "json" in ctype or "xml" in ctype:
                    print(f"     └─ Head: {r.text[:400]}")
        except Exception as e:
            print(f"ERR  {path}: {e}")