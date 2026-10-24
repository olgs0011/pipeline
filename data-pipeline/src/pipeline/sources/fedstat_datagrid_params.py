"""Найти в FGrid.js, как формируются параметры для dataGrid.do."""
import re

js = open("FGrid.js", encoding="utf-8").read()
print(f"FGrid.js: {len(js)} символов")

# Ищем все места с dataGrid.do
print("\n=== Все упоминания 'dataGrid.do' ===")
for m in re.finditer(r"dataGrid\.do", js):
    start = max(0, m.start() - 500)
    end = min(len(js), m.start() + 300)
    snippet = js[start:end].replace("\n", " ")
    # Убираем множественные пробелы
    snippet = re.sub(r"\s+", " ", snippet)
    print(f"\n--- позиция {m.start()} ---")
    print(snippet)

# Ищем ключевые слова вокруг AJAX
print("\n\n=== Места с 'data:' в AJAX-контексте ===")
for kw in ["data: ", "type: 'GET'", 'type: "GET"', "type: 'POST'", 'type: "POST"']:
    positions = [m.start() for m in re.finditer(re.escape(kw), js)]
    print(f"\n'{kw}' — {len(positions)} совпадений")
    for pos in positions[:3]:
        snippet = js[max(0, pos - 200): pos + 300].replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet)
        print(f"  [{pos}] {snippet}")