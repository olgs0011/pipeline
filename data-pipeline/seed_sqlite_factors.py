import sys
from pathlib import Path
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from pipeline.db.session import session_scope
from pipeline.db.models import FactorSource


def seed() -> None:
    csv_path = Path("data/reference/factor_matches.csv")
    if not csv_path.exists():
        logger.error(f"Файл {csv_path} не найден!")
        return

    df = pd.read_csv(csv_path)
    logger.info(f"Загружено строк из CSV: {len(df)}")

    # Убираем дубликаты по factor_code, оставляя первую подходящую запись для каждого фактора
    df_unique = df.drop_duplicates(subset=["factor_code"], keep="first")
    logger.info(f"Уникальных факторов для записи: {len(df_unique)}")

    with session_scope() as session:
        # Очищаем старые привязки, если есть
        session.query(FactorSource).delete()

        # Записываем актуальные
        for _, row in df_unique.iterrows():
            fs = FactorSource(
                factor_code=row["factor_code"],
                source_id="fedstat",
                external_id=str(row["indicator_id"]),
                filter_json={},
                match_method=row.get("match_method", "manual"),
                confidence=float(row.get("confidence", 1.0)),
            )
            session.add(fs)
        session.commit()
    logger.success("Таблица factor_sources успешно заполнена уникальными факторами!")


if __name__ == "__main__":
    seed()