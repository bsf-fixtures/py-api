"""The service, plus a sandbox-only admin surface on the same port.

`app` here *is* `app.main:app` — the same FastAPI instance, with its routes,
its lifespan and its behaviour untouched. What this module adds is a handful
of routes under `/__sandbox`, every one of them `include_in_schema=False`, so
`/openapi.json` and the Swagger UI at `/docs` are byte-for-byte what the
service serves on its own.

Why it exists: when the sandbox runs the app on the runner, it forwards one
port — the app's — into the container a role works in. The database is not
forwarded, so from there `127.0.0.1:5432` is refused and
`host.docker.internal:5432` times out. A role that needs to put the database
into a particular state, or to read it back, has no route to it. These routes
are that route, over the one port that does get through.

The sandbox only ever starts the app this way, and the database behind it is a
throwaway container with published credentials holding nothing but test rows.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sandbox_seed import SEED_ROWS, apply_seed, reset_readings, run_sql

from app.main import app

PREFIX = "/__sandbox"


class SqlIn(BaseModel):
    """One statement, and optionally the values to bind into it."""

    sql: str = Field(min_length=1)
    params: dict[str, Any] | None = None


def _fail(exc: Exception) -> HTTPException:
    """Report what the database said, rather than a bare 500."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"{type(exc).__name__}: {exc}",
    )


@app.get(PREFIX, include_in_schema=False)
def sandbox_index() -> dict[str, Any]:
    """What is here, so a role can discover it with one GET."""
    return {
        "what": "sandbox-only database access, on the app's port because nothing "
        "forwards the database's",
        "endpoints": {
            "GET " + PREFIX: "this",
            "POST " + PREFIX + "/sql": 'body {"sql": "...", "params": {...}} - run one '
            "statement against DATABASE_URL and get its rows back; omit params to send "
            "several statements separated by ;",
            "POST " + PREFIX + "/seed": "apply the manifest's seed rows, the same "
            "definition the `seed` command runs",
            "POST " + PREFIX + "/reset": "delete every row in readings and restart its id "
            "sequence",
        },
        "seed_rows": [{"sensor": sensor, "celsius": celsius} for sensor, celsius in SEED_ROWS],
        "not_part_of_the_service": "these routes are added by the sandbox and are hidden from "
        "/openapi.json; nothing in app/ knows about them",
    }


@app.post(PREFIX + "/sql", include_in_schema=False)
def sandbox_sql(payload: SqlIn) -> dict[str, Any]:
    try:
        return run_sql(payload.sql, payload.params)
    except Exception as exc:  # the caller wants the database's own message
        raise _fail(exc) from exc


@app.post(PREFIX + "/seed", include_in_schema=False)
def sandbox_seed() -> dict[str, Any]:
    try:
        return apply_seed()
    except Exception as exc:  # the caller wants the database's own message
        raise _fail(exc) from exc


@app.post(PREFIX + "/reset", include_in_schema=False)
def sandbox_reset() -> dict[str, Any]:
    try:
        return reset_readings()
    except Exception as exc:  # the caller wants the database's own message
        raise _fail(exc) from exc
