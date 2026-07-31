"""Database engine, SQLAlchemy base class, and request-scoped sessions."""

from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load local development settings from backend/.env.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)

explicit_database_url = os.getenv("DATABASE_URL")

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

    missing_settings = [
        setting for setting in required_settings if not os.getenv(setting)
    ]

    if missing_settings:
        raise RuntimeError(
            "Missing database settings in .env: "
            + ", ".join(missing_settings)
        )

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT")),
        database=os.getenv("POSTGRES_DB"),
    )

engine_options = {"pool_pre_ping": True}

if str(database_url).startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

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

# Create database tables (development only)
from . import models

print("Creating tables...")
print(engine.url)
Base.metadata.create_all(bind=engine)
print("Finished creating tables.")