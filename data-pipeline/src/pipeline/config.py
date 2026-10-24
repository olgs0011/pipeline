from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем корень подпроекта data-pipeline (поднимаемся на 2 уровня от config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    data_root: Path = PROJECT_ROOT / "data"
    log_level: str = "INFO"

    @property
    def bronze_dir(self) -> Path:
        return self.data_root / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.data_root / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.data_root / "gold"


settings = Settings()