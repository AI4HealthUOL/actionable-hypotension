from __future__ import annotations
import os
from functools import lru_cache

# Optionally load .env for local/dev usage (no hard dependency).
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass


class MissingDatabaseURI(RuntimeError):
    """Raised when DATABASE_URI is not set."""


@lru_cache
def get_database_uri() -> str:
    """
    Return the SQLAlchemy database URI from the environment.
    Raises a clear error if DATABASE_URI is not set.
    """
    uri = os.getenv("DATABASE_URI")
    if not uri:
        raise MissingDatabaseURI(
            "DATABASE_URI is not set.\n\n"
            "Please define it via environment or a .env file. Examples:\n"
            "  export DATABASE_URI='postgresql+psycopg2://user:pass@localhost:5434/mimic'\n"
            "  export DATABASE_URI='postgresql+psycopg2://user@/mimic?host=/tmp&port=5434'  # UNIX socket\n\n"
            "If you intentionally want a local SQLite dev DB, set:\n"
            "  export DATABASE_URI='sqlite:///local.db'\n"
        )
    return uri


@lru_cache
def get_engine(echo: bool = False):
    """Create and cache a SQLAlchemy Engine. Fails fast if DATABASE_URI is missing."""
    from sqlalchemy import create_engine
    return create_engine(get_database_uri(), echo=echo, future=True, pool_pre_ping=True)