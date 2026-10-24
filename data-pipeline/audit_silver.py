import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import polars as pl
from pipeline.config import settings

root = settings.silver_dir / "fedstat"
rows = []
for d in sorted(root.iterdir()):
    if not d.is_dir():
        continue
    f = d / "data.parquet"
    if not f.exists():
        rows.append({"factor": d.name, "rows": 0, "years": "", "regions": 0, "note": "нет файла"})
        continue
    df = pl.read_parquet(f)
    years = sorted(df["year"].unique().to_list()) if "year" in df.columns else []
    n_regions = df["region"].n_unique() if "region" in df.columns else 0
    rows.append({
        "factor": d.name,
        "rows": df.height,
        "years": f"{min(years)}..{max(years)}" if years else "-",
        "regions": n_regions,
        "note": "",
    })

out = pl.DataFrame(rows)
print(out)
out.write_csv("silver_audit.csv")
print("\nСохранено в silver_audit.csv")