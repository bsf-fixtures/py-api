"""The sandbox's database helpers: seed, reset, and raw SQL.

These exist because the only thing a role's container can reach of this
sandbox is the app's HTTP port. The database is on the runner's loopback and
nothing bridges 5432, so `psql`, a SQLAlchemy one-liner and the manifest's own
`seed` command are all unreachable from inside that container.

`sandbox_app.py` exposes every function below over HTTP under `/__sandbox`,
which *is* reachable. The same module is runnable directly, and that is what
the manifest's `seed` command does, so the seed a role applies over HTTP and
the seed the manifest names are one definition rather than two that can drift.

Nothing in `app/` imports this. It is sandbox scaffolding, not the service.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db import create_all, engine, session
from app.models import Reading

# The readings every role starts from: three in one room, two in another, so a
# GROUP BY has something to group and two sensors have different summaries.
SEED_ROWS: tuple[tuple[str, float], ...] = (
    ("kitchen", 21.5),
    ("kitchen", 19.0),
    ("kitchen", 23.25),
    ("garage", 8.5),
    ("garage", 11.0),
)


def _jsonable(value: object) -> Any:
    """Make one column value safe for JSON, without lying about its type."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).hex()
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def apply_seed() -> dict[str, Any]:
    """Add SEED_ROWS through the app's own session, the way the service writes."""
    create_all()
    with session() as db:
        for sensor, celsius in SEED_ROWS:
            db.add(Reading(sensor=sensor, celsius=celsius))
    return {
        "seeded": len(SEED_ROWS),
        "sensors": sorted({sensor for sensor, _ in SEED_ROWS}),
        "rows": [{"sensor": sensor, "celsius": celsius} for sensor, celsius in SEED_ROWS],
    }


def reset_readings() -> dict[str, Any]:
    """Empty the readings table and restart its id sequence.

    The sequence restart is what makes a reset reproducible: two roles that
    reset and seed see the same ids, so an acceptance check may name one.
    """
    create_all()
    with engine().begin() as conn:
        deleted = conn.execute(text("DELETE FROM readings")).rowcount
        conn.execute(text("ALTER SEQUENCE IF EXISTS readings_id_seq RESTART WITH 1"))
    return {"deleted": deleted}


def _result_set(cursor: Any) -> dict[str, Any]:
    """One statement's outcome, read off a DBAPI cursor."""
    if cursor.description is None:
        return {"rows": [], "rowcount": cursor.rowcount, "returned_rows": False}
    names = [column[0] for column in cursor.description]
    rows = [
        {name: _jsonable(value) for name, value in zip(names, row, strict=True)}
        for row in cursor.fetchall()
    ]
    return {"rows": rows, "rowcount": len(rows), "returned_rows": True}


def run_sql(sql: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run SQL against DATABASE_URL and return everything it produced.

    Without params the text goes to the driver as written, so PostgreSQL's
    simple protocol accepts several statements separated by `;` and every one
    of their result sets comes back under `results`. With params it goes
    through SQLAlchemy's `:name` binding, which is one statement but is how to
    pass a value that would otherwise need quoting or casting.

    `rows` and `rowcount` at the top level are the last statement's, so the
    ordinary one-statement call reads the same either way. Everything runs in
    one transaction, committed when the statements all succeed.
    """
    create_all()
    with engine().begin() as conn:
        if params:
            result = conn.execute(text(sql), dict(params))
            if result.returns_rows:
                rows = [{k: _jsonable(v) for k, v in m.items()} for m in result.mappings()]
                sets = [{"rows": rows, "rowcount": len(rows), "returned_rows": True}]
            else:
                sets = [{"rows": [], "rowcount": result.rowcount, "returned_rows": False}]
        else:
            cursor = conn.connection.cursor()
            try:
                cursor.execute(sql)
                sets = [_result_set(cursor)]
                while cursor.nextset():
                    sets.append(_result_set(cursor))
            finally:
                cursor.close()
    last = sets[-1]
    return {
        "rows": last["rows"],
        "rowcount": last["rowcount"],
        "returned_rows": last["returned_rows"],
        "statements": len(sets),
        "results": sets,
    }


def main() -> None:
    applied = apply_seed()
    # This module is a command as well as a library: the manifest's `seed`
    # runs it, and the wording below is what a role sees in that step's log.
    print(f"seeded {applied['seeded']} readings across {len(applied['sensors'])} sensors")


if __name__ == "__main__":
    main()
