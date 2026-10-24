# Data Pipeline — дневник проекта

## 2026-10-08 — DONE
- Роспотребнадзор: bronze → silver → Postgres полностью
- 158 факторов в справочнике
- Prefect flow работает (с fallback)
- DuckDB витрина (hive_partitioning=false!)
- Исправлено 4 бага: парсер, индекс, hive_partitioning, кодировка

## 2026-10-09 — TODO
- [ ] Поставить R + fedstatAPIr
- [ ] Выгрузить fedstat_indicators.csv
- [ ] Fuzzy-matching x1..x10 → indicator_id
- [ ] FedstatSource MVP (x1 за 2023)
- [ ] Таблица factor_sources в Postgres

## Открытые вопросы
- Где реальный URL форм Роспотребнадзора?
- Как часто ЕМИСС обновляет данные?
- Есть ли API-лимиты?