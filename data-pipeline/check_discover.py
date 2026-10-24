"""Разовый скрипт для проверки discover(). Удалить после верификации."""
from pipeline.logging import setup_logging
from pipeline.sources.rospotrebnadzor import RospotrebnadzorSource

setup_logging()

src = RospotrebnadzorSource()
files = src.discover()

print(f"\n=== Найдено {len(files)} файлов ===")
for f in files[:20]:
    print(f"  year={f.year} region={f.region}  {f.filename}")
    print(f"    {f.url}")