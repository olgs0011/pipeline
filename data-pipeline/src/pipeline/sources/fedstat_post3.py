"""Правильный POST: params_data как x-www-form-urlencoded."""
import httpx

BASE = "https://www.fedstat.ru"
URL = f"{BASE}/indicator/dataGrid.do?id=31165"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": f"{BASE}/indicator/31165.do",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def show(label: str, r: httpx.Response) -> None:
    ctype = r.headers.get("content-type", "?").split(";")[0]
    print(f"\n=== {label} ===")
    print(f"Status: {r.status_code}, ctype: {ctype}, len: {len(r.text)}")
    if "json" in ctype:
        try:
            data = r.json()
            if "results" in data:
                rows = data["results"]
                print(f"  ✅ results: {len(rows)} rows")
                years = sorted({row.get("dim3") for row in rows if "dim3" in row})
                print(f"  Годы: {years}")
                # Показать РФ и 2015, если есть
                for row in rows:
                    if row.get("dim3") == "2015" and "Российская Федерация" in row.get("dim57831", ""):
                        print(f"  🎯 РФ, 2015: {row}")
                        break
        except Exception as e:
            print(f"  JSON parse error: {e}")


def build_params_data(selected: list[tuple[int, int]]) -> str:
    """Строит строку params_data для POST.

    selected: список (owner_id, filter_id) — выбранные значения фильтров.
    """
    # lineObjectIds — фильтры, отображаемые по строкам (регион, единица, год)
    # columnObjectIds — фильтры по столбцам (период)
    parts = [
        "lineObjectIds=57831",   # регион
        "lineObjectIds=30611",   # единица измерения
        "lineObjectIds=3",       # год
        "columnObjectIds=33560", # период
    ]
    for owner_id, filter_id in selected:
        parts.append(f"selectedFilterIds={owner_id}_{filter_id}")
    return "&".join(parts)


with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
    # Пробуем: РФ, все годы 2015-2024, единица «-», период «за год»
    selected = [
        (57831, 1688487),        # РФ
        (30611, 1341910),        # единица «-»
        (33560, 1558883),        # период «за год»
    ]
    for year in range(2015, 2025):
        selected.append((3, year))   # года 2015-2024

    body = build_params_data(selected)
    print("=== Тело запроса ===")
    print(body)
    print()

    r = client.post(URL, content=body)
    show("POST с правильным params_data", r)