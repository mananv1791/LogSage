from collections.abc import Generator
import os

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def _database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/logsage.db"
    return "sqlite:///./logsage.db"


def _connect_args(url: str) -> dict[str, object]:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


DATABASE_URL = _database_url()
engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args(DATABASE_URL),
    pool_pre_ping=True,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
