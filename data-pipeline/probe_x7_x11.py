"""Проверяем x7 (31177) и x11 (40642) вручную."""
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}

CASES = [
    # x7 (31177): line=[57831], column=[3], без secondary в line
    ("x7 без ОКФС", "https://www.fedstat.ru/indicator/dataGrid.do?id=31177",
     "lineObjectIds=57831&columnObjectIds=3"
     "&selectedFilterIds=0_31177"
     "&selectedFilterIds=3_2020"
     "&selectedFilterIds=57831_1688487"
     "&selectedFilterIds=30611_950493"
     "&selectedFilterIds=33560_1558883"),

    ("x7 c ОКФС=1707673", "https://www.fedstat.ru/indicator/dataGrid.do?id=31177",
     "lineObjectIds=57831&columnObjectIds=3"
     "&selectedFilterIds=0_31177"
     "&selectedFilterIds=3_2020"
     "&selectedFilterIds=57831_1688487"
     "&selectedFilterIds=58097_1707673"
     "&selectedFilterIds=30611_950493"
     "&selectedFilterIds=33560_1558883"),

    # x11 (40642): line=[57831], column=[3], без secondary
    ("x11", "https://www.fedstat.ru/indicator/dataGrid.do?id=40642",
     "lineObjectIds=57831&columnObjectIds=3"
     "&selectedFilterIds=0_40642"
     "&selectedFilterIds=3_2020"
     "&selectedFilterIds=57831_1688487"
     "&selectedFilterIds=30611_950311"
     "&selectedFilterIds=33560_1558883"),

    # x31581: как x5, но без Специализации
    ("x31581 без ОКФС", "https://www.fedstat.ru/indicator/dataGrid.do?id=31581",
     "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
     "&selectedFilterIds=0_31581"
     "&selectedFilterIds=3_2020"
     "&selectedFilterIds=57831_1688487"
     "&selectedFilterIds=30611_950475"
     "&selectedFilterIds=33560_1558883"),

    ("x31581 c ОКФС=1707673", "https://www.fedstat.ru/indicator/dataGrid.do?id=31581",
     "lineObjectIds=57831&lineObjectIds=58097&columnObjectIds=3"
     "&selectedFilterIds=0_31581"
     "&selectedFilterIds=3_2020"
     "&selectedFilterIds=57831_1688487"
     "&selectedFilterIds=58097_1707673"
     "&selectedFilterIds=30611_950475"
     "&selectedFilterIds=33560_1558883"),
]

with httpx.Client(timeout=20.0, headers=HEADERS) as client:
    for label, url, body in CASES:
        try:
            r = client.post(url, content=body)
            data = r.json()
            rows = data.get("results", [])
            marker = "✅" if rows else "❌"
            print(f"{marker} {label}: {len(rows)} строк")
            if rows:
                print(f"    {rows[0]}")
        except Exception as e:
            print(f"❌ {label}: {e}")