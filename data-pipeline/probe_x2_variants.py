"""Проверяем разные варианты POST для x2 (33458)."""
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.fedstat.ru/indicator/33458.do",
}

URL = "https://www.fedstat.ru/indicator/dataGrid.do?id=33458"


def make_body(okfs_id=None, dolzhnost_id=None):
    parts = [
        "lineObjectIds=57831", "lineObjectIds=58097", "lineObjectIds=58336",
        "columnObjectIds=3", "columnObjectIds=33560",
        "selectedFilterIds=0_33458",
        "selectedFilterIds=3_2020",
        "selectedFilterIds=57831_1688487",
        "selectedFilterIds=30611_950458",
        "selectedFilterIds=33560_1558883",
    ]
    if dolzhnost_id is not None:
        parts.append(f"selectedFilterIds=58336_{dolzhnost_id}")
    if okfs_id is not None:
        parts.append(f"selectedFilterIds=58097_{okfs_id}")
    return "&".join(parts)


VARIANTS = [
    ("без ОКФС и без Должности", make_body()),
    ("только ОКФС=1707673", make_body(okfs_id=1707673)),
    ("ОКФС=1707673 + Должность=1847904 (Всего)",
     make_body(okfs_id=1707673, dolzhnost_id=1847904)),
    ("ОКФС=1707673 + Должность=1751314 (Средний медперсонал)",
     make_body(okfs_id=1707673, dolzhnost_id=1751314)),
    ("ОКФС=1707673 + Должность=1751315 (Всего врачей)",
     make_body(okfs_id=1707673, dolzhnost_id=1751315)),
    ("ОКФС=1704559 + Должность=1751314",
     make_body(okfs_id=1704559, dolzhnost_id=1751314)),
]

with httpx.Client(timeout=20.0, headers=HEADERS) as client:
    for label, body in VARIANTS:
        try:
            r = client.post(URL, content=body)
            data = r.json()
            rows = data.get("results", [])
            marker = "✅" if rows else "❌"
            print(f"{marker} {label}: {len(rows)} строк")
            if rows:
                print(f"    Пример: {rows[0]}")
        except Exception as e:
            print(f"❌ {label}: ошибка {e}")