import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select
from pipeline.db.models import FactorSource
from pipeline.db.session import session_scope

FIXES = {
    "x87": {"продукт": "Хлебные продукты"},
    "x91": {"продукт": "Мясо и мясопродукты"},
    "x92": {"продукт": "Молоко"},
    "x94": {"продукт": "Рыба и рыбопродукты"},
}

with session_scope() as session:
    for code, new_filter in FIXES.items():
        fs = session.execute(
            select(FactorSource).where(
                FactorSource.factor_code == code,
                FactorSource.source_id == "fedstat",
            )
        ).scalar_one_or_none()
        if fs is None:
            print(f"{code}: не найден")
            continue
        old = fs.filter_json
        fs.filter_json = new_filter
        print(f"{code}: {old} → {new_filter}")

print("\nГотово. Проверка:")
with session_scope() as session:
    for code in FIXES:
        fs = session.execute(
            select(FactorSource).where(
                FactorSource.factor_code == code,
                FactorSource.source_id == "fedstat",
            )
        ).scalar_one_or_none()
        print(f"  {code}: {fs.filter_json}")