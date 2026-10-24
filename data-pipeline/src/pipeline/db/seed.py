from pipeline.db.models import Dataset, Source
from pipeline.db.session import session_scope


def seed_metadata() -> None:
    with session_scope() as session:
        # 1. Источник: Роспотребнадзор
        rpn = session.get(Source, "rospotrebnadzor")
        if not rpn:
            rpn = Source(
                id="rospotrebnadzor",
                name="Федеральная служба по надзору в сфере защиты прав потребителей и благополучия человека",
                base_url="https://www.rospotrebnadzor.ru",
                description="Официальные формы статистической отчетности и мониторинга",
            )
            session.add(rpn)

        # 2. Датасет: Форма №1 (инфекционная заболеваемость)
        dataset_form1 = session.get(Dataset, "form_1_rost_snizh")
        if not dataset_form1:
            dataset_form1 = Dataset(
                id="form_1_rost_snizh",
                source_id="rospotrebnadzor",
                name="Форма №1: Сведения об инфекционных и паразитарных заболеваниях (рост-снижение)",
                period_type="annual",
                schema_version="v1",
            )
            session.add(dataset_form1)

        # 3. Источник: ЕМИСС / Росстат
        fedstat = session.get(Source, "fedstat")
        if not fedstat:
            fedstat = Source(
                id="fedstat",
                name="Единая межведомственная информационно-статистическая система (ЕМИСС)",
                base_url="https://www.fedstat.ru",
                description="Официальная статистическая информация РФ",
            )
            session.add(fedstat)

        # Датасет: индикаторы ЕМИСС (long-format: year/region/value)
        ds_fedstat = session.get(Dataset, "fedstat_indicators")
        if not ds_fedstat:
            ds_fedstat = Dataset(
                id="fedstat_indicators",
                source_id="fedstat",
                name="Индикаторы ЕМИСС (long-format)",
                period_type="annual",
                schema_version="v1",
            )
            session.add(ds_fedstat)

    print("Базовые метаданные (источники и датасеты) успешно зафиксированы в БД.")


if __name__ == "__main__":
    seed_metadata()