"""Смотрим values ОКФС для x5 (31581)."""
import re
import httpx

URL = "https://www.fedstat.ru/indicator/31581.do"
HEADERS = {"User-Agent": "Mozilla/5.0 ..."}

r = httpx.get(URL, headers=HEADERS, timeout=20, follow_redirects=True)
html = r.text

# Найдём блок ОКФС (owner_id=58097)
m = re.search(r"58097:\s*\{", html)
if not m:
    print("58097 не найден")
    raise SystemExit

start = m.end() - 1
depth = 0
for i in range(start, len(html)):
    if html[i] == "{":
        depth += 1
    elif html[i] == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break

block = html[start:end]

# Извлечём все values
values_block_m = re.search(r"values:\s*\{", block)
v_start = values_block_m.end() - 1
v_depth = 0
for i in range(v_start, len(block)):
    if block[i] == "{":
        v_depth += 1
    elif block[i] == "}":
        v_depth -= 1
        if v_depth == 0:
            v_end = i + 1
            break

values_block = block[v_start:v_end]

# Найдём все N: {title: '...', checked: ...}
for vm in re.finditer(r"(\d+)\s*:\s*\{", values_block):
    vid = vm.group(1)
    b_start = vm.end() - 1
    b_depth = 0
    for i in range(b_start, len(values_block)):
        if values_block[i] == "{":
            b_depth += 1
        elif values_block[i] == "}":
            b_depth -= 1
            if b_depth == 0:
                b_end = i + 1
                break
    inner = values_block[b_start:b_end]
    title_m = re.search(r"title:\s*'([^']*)'", inner)
    checked_m = re.search(r"checked:\s*(true|false)", inner)
    title = title_m.group(1).encode("utf-8").decode("unicode_escape") if title_m else "?"
    checked = checked_m.group(1) if checked_m else "?"
    print(f"  {vid}: {title!r} checked={checked}")