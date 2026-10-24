import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select
from pipeline.db.models import FactorSource
from pipeline.db.session import session_scope

FIXES = {
    "x83": {"external_id": "60752", "filter_json": {"товары": "образование"}},
    "x84": {"external_id": "60752", "filter_json": {"товары": "здравоохранение"}},
}

with session_scope() as session:
    for code, new in FIXES.items():
        fs = session.execute(
            select(FactorSource).where(
                FactorSource.factor_code == code,
                FactorSource.source_id == "fedstat",
            )
        ).scalar_one_or_none()
        if fs is None:
            print(f"{code}: не найден")
            continue
        old_id, old_f = fs.external_id, fs.filter_json
        fs.external_id = new["external_id"]
        fs.filter_json = new["filter_json"]
        print(f"{code}: id {old_id} → {new['external_id']}, filters {old_f} → {new['filter_json']}")

print("\nПроверка:")
with session_scope() as session:
    for code in FIXES:
        fs = session.execute(
            select(FactorSource).where(
                FactorSource.factor_code == code,
                FactorSource.source_id == "fedstat",
            )
        ).scalar_one_or_none()
        print(f"  {code}: id={fs.external_id}, filters={fs.filter_json}")