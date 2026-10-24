"""Прямая отладка _normalize_results."""
from pipeline.sources.fedstat import _normalize_results
import polars as pl

row = {'dim57831': 'Российская Федерация', 'dim58097': 'ВСЕГО', 'dim2015_d45713923_i2197': '5433'}

print("=== row ===")
for k, v in row.items():
    print(f"  {k!r} = {v!r} (type={type(v).__name__})")

print("\n=== Проверка float ===")
for k, v in row.items():
    try:
        f = float(str(v).replace(",", "."))
        print(f"  {k!r}: float OK → {f}")
    except (ValueError, TypeError) as e:
        print(f"  {k!r}: ошибка → {type(e).__name__}: {e}")

print("\n=== regexp ===")
import re
col_key = "dim2015_d45713923_i2197"
m = re.search(r"_(20\d{2}|19\d{2})_", col_key)
print(f"  m_year для {col_key!r}: {m}")
if m:
    print(f"  group(1) = {m.group(1)!r}")

print("\n=== _normalize_results ===")
df = _normalize_results([row])
print(f"shape: {df.shape}")
print(df)