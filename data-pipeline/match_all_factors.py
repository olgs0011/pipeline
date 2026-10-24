"""Автоматический матчинг всех 158 факторов с индикаторами ЕМИСС.

Использует rapidfuzz. Топ-5 кандидатов на каждый фактор.
Результат: data/reference/factor_matches.csv
"""
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from pipeline.reference.factors_list import FACTORS

ROOT = Path(__file__).resolve().parent
INDICATORS_CSV = ROOT / "data" / "reference" / "fedstat_indicators.csv"
OUT_CSV = ROOT / "data" / "reference" / "factor_matches.csv"

# 1. Читаем базу индикаторов, чистим
df = pd.read_csv(INDICATORS_CSV, encoding="utf-8")
df = df[df["id"].astype(str).str.match(r"^\d+$")].copy()
df["id"] = df["id"].astype(int)
df["title"] = df["title"].astype(str)

print(f"Чистых индикаторов в базе: {len(df)}")

# 2. Матчим каждый фактор
rows: list[dict] = []
for entry in FACTORS:
    # Поддерживаем и (code, name) и (code, name, unit)
    if len(entry) == 3:
        code, name, unit = entry
    else:
        code, name = entry
        unit = None

    matches = process.extract(
        name,
        df["title"].tolist(),
        scorer=fuzz.token_set_ratio,
        limit=5,
    )

    for rank, (matched_title, score, idx) in enumerate(matches, start=1):
        row = df.iloc[idx]
        rows.append({
            "factor_code": code,
            "factor_name": name,
            "unit": unit,
            "rank": rank,
            "match_score": round(score, 1),
            "indicator_id": int(row["id"]),
            "indicator_title": matched_title,
            "indicator_department": row["department"],
            "indicator_group": row["group"],
        })

out = pd.DataFrame(rows)
out.to_csv(OUT_CSV, index=False, encoding="utf-8")
print(f"\n✅ Сохранено: {OUT_CSV}")
print(f"Строк: {len(out)} ({len(FACTORS)} факторов × 5 кандидатов)")

# 3. Сводка по качеству матчинга
print(f"\n=== Распределение лучших матчей (rank=1) ===")
best = out[out["rank"] == 1]
bins = pd.cut(
    best["match_score"],
    bins=[0, 50, 65, 80, 100],
    labels=["<50", "50-65", "65-80", "80+"],
)
print(bins.value_counts().sort_index())

# 4. Топ-30 лучших
print(f"\n=== Топ-30 матчей (rank=1) ===")
top30 = best.nlargest(30, "match_score")
for _, r in top30.iterrows():
    print(f"  {r['factor_code']:>4} [{r['match_score']:5.1f}] id={r['indicator_id']:<8} | {r['indicator_title'][:70]}")

# 5. Худшие 20
print(f"\n=== Худшие 20 матчей (нужен ручной поиск) ===")
worst20 = best.nsmallest(20, "match_score")
for _, r in worst20.iterrows():
    print(f"  {r['factor_code']:>4} [{r['match_score']:5.1f}] {r['factor_name'][:80]}")