import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select
from pipeline.db.models import FactorSource
from pipeline.db.session import session_scope

# Импорт справочника — подправь путь, если файл называется иначе
from pipeline.reference.factors_list import FACTORS

REF = {code: (name, unit) for code, name, unit in FACTORS}

with session_scope() as session:
    rows = session.execute(
        select(FactorSource).where(FactorSource.source_id == "fedstat")
    ).scalars().all()

print(f"{'code':6} {'indicator_id':12} {'в справочнике?':16} название в справочнике")
print("-" * 120)
for fs in rows:
    code = fs.factor_code
    ref = REF.get(code)
    in_ref = "ДА" if ref else "НЕТ"
    name = ref[0][:70] if ref else "-"
    print(f"{code:6} {fs.external_id:12} {in_ref:16} {name}")

print(f"\nВсего в БД: {len(rows)}")
print(f"Всего в справочнике: {len(FACTORS)}")

# Каких факторов из справочника нет в БД
codes_in_db = {fs.factor_code for fs in rows}
missing = [c for c in REF if c not in codes_in_db]
print(f"\nНет в БД, но есть в справочнике ({len(missing)}): {missing}")