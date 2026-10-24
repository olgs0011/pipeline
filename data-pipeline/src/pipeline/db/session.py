from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pipeline.config import settings

# Определяем, SQLite это или серверная БД (Postgres)
is_sqlite = settings.database_url.startswith("sqlite")

engine_args = {}
if is_sqlite:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args.update({
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": 5,
        "max_overflow": 10,
        "connect_args": {"connect_timeout": 30},
    })

engine = create_engine(settings.database_url, **engine_args)
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