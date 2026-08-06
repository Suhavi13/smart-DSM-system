
"""Database engine and request-scoped SQLAlchemy sessions for this service."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from services.shared.environment import load_service_environment


SERVICE_ROOT = Path(__file__).resolve().parents[1]
load_service_environment(SERVICE_ROOT)

explicit_database_url = os.getenv("DATABASE_URL", "").strip()

if explicit_database_url:
    database_url = explicit_database_url
else:
    required_settings = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    ]
    missing_settings = [name for name in required_settings if not os.getenv(name)]
    if missing_settings:
        raise RuntimeError(
            "Missing database settings: " + ", ".join(missing_settings)
        )

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB"),
    )

engine_options: dict = {"pool_pre_ping": True}
if str(database_url).startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    sslmode = os.getenv("POSTGRES_SSLMODE", "").strip()
    if sslmode:
        engine_options["connect_args"] = {"sslmode": sslmode}

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
