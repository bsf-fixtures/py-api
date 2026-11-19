"""Test fixtures.

The database tests need the sidecar Postgres. They are skipped, loudly, when
DATABASE_URL is absent, so `pytest` still passes on a laptop with no sidecar
while CI and the factory's sandbox run the full set.
"""

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set; start the sidecar Postgres to run database tests")
    return url


@pytest.fixture()
def client(database_url: str) -> Iterator[object]:
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        yield c
