"""Engine and session handling."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.settings import Settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(Settings.from_env().database_url, pool_pre_ping=True)
    return _engine


def create_all() -> None:
    """Create the tables. Idempotent, so running it twice is harmless."""
    Base.metadata.create_all(engine())


@contextmanager
def session() -> Iterator[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=engine(), expire_on_commit=False)
    db = _session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
