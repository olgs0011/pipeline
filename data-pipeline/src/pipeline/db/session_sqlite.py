"""Сессия для работы с SQLite (без Docker/Postgres)."""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pipeline.config import settings

# Принудительно подключаемся к локальной SQLite-базе в папке data/
sqlite_url = "sqlite:///" + str(settings.data_root / "metadata.db")

engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()