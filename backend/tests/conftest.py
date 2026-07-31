"""Shared in-memory database and authenticated client fixtures for tests."""

from collections.abc import Generator
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("ENTRA_TENANT_ID", "test-tenant-id")
os.environ.setdefault("ENTRA_API_CLIENT_ID", "test-api-client-id")
os.environ.setdefault("ENTRA_SPA_CLIENT_ID", "test-spa-client-id")
os.environ.setdefault("ENTRA_REQUIRED_SCOPE", "access_as_user")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_db
from backend.app.main import app


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        object_id="test-operator-oid",
        tenant_id="test-tenant-id",
        name="Test Operator",
        username="operator@example.com",
        roles=frozenset({"Operator"}),
        claims={},
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
