from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Neon's pooler does not keep server-side prepared statements across transactions.
CONNECT_ARGS = {"prepare_threshold": None}

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_db_engine(*, null_pool: bool = False, url: str | None = None) -> Engine:
    options: dict[str, object] = {
        "pool_pre_ping": True,
        "connect_args": CONNECT_ARGS,
    }
    if null_pool:
        options["poolclass"] = NullPool
    else:
        options["pool_recycle"] = 300
    return create_engine(url or settings.sqlalchemy_database_url, **options)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
