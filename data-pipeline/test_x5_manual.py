"""Ручной POST для x5 (31581) с разными вариантами body."""
import httpx

URL = "https://www.fedstat.ru/indicator/dataGrid.do?id=31581"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.fedstat.ru/indicator/31581.do",
}

CANDIDATES = {
    "наш текущий": (
        "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
        "&selectedFilterIds=0_31581"
        "&selectedFilterIds=3_2015&selectedFilterIds=3_2016&selectedFilterIds=3_2017&selectedFilterIds=3_2018"
        "&selectedFilterIds=3_2019&selectedFilterIds=3_2020&selectedFilterIds=3_2021&selectedFilterIds=3_2022"
        "&selectedFilterIds=3_2023&selectedFilterIds=3_2024&selectedFilterIds=3_2025"
        "&selectedFilterIds=57831_1688487"
        "&selectedFilterIds=58097_1704559"
        "&selectedFilterIds=30611_950475"
        "&selectedFilterIds=33560_1558883"
    ),
    "только один год 2020": (
        "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
        "&selectedFilterIds=0_31581"
        "&selectedFilterIds=3_2020"
        "&selectedFilterIds=57831_1688487"
        "&selectedFilterIds=58097_1704559"
        "&selectedFilterIds=30611_950475"
        "&selectedFilterIds=33560_1558883"
    ),
    "ОКФС=1707673 (ВСЕГО)": (
        "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
        "&selectedFilterIds=0_31581"
        "&selectedFilterIds=3_2020"
        "&selectedFilterIds=57831_1688487"
        "&selectedFilterIds=58097_1707673"
        "&selectedFilterIds=30611_950475"
        "&selectedFilterIds=33560_1558883"
    ),
    "без ОКФС вообще": (
        "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
        "&selectedFilterIds=0_31581"
        "&selectedFilterIds=3_2020"
        "&selectedFilterIds=57831_1688487"
        "&selectedFilterIds=30611_950475"
        "&selectedFilterIds=33560_1558883"
    ),
}

with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
    for label, body in CANDIDATES.items():
        r = client.post(URL, content=body)
        ctype = r.headers.get("content-type", "?").split(";")[0]
        try:
            data = r.json()
            rows = data.get("results", [])
            marker = "✅" if rows else "❌"
            print(f"{marker} [{label}] status={r.status_code} ctype={ctype} rows={len(rows)}")
            if rows:
                print(f"    Пример: {rows[0]}")
        except Exception as e:
            print(f"❌ [{label}] status={r.status_code} ctype={ctype} ошибка: {e}")
            print(f"    первые 100: {r.text[:100]}")