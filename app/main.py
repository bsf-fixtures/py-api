"""The service.

Four endpoints, enough for API-level runtime verification: write a reading,
read them back, summarize one sensor, and a health check the sandbox can poll
to know the service and its database are both up.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import select

from app.db import create_all, session
from app.models import Reading
from app.schemas import ReadingIn, ReadingOut, SensorSummary
from app.summary import summarize


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create the tables on startup. Idempotent, so a restart is harmless."""
    create_all()
    yield


app = FastAPI(title="py-api", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Up only if the database answers, so this is a real readiness check."""
    with session() as db:
        db.execute(select(1))
    return {"status": "ok"}


@app.post("/readings", response_model=ReadingOut, status_code=status.HTTP_201_CREATED)
def add_reading(payload: ReadingIn) -> ReadingOut:
    with session() as db:
        row = Reading(sensor=payload.sensor, celsius=payload.celsius)
        db.add(row)
        db.flush()
        return ReadingOut(
            id=row.id, sensor=row.sensor, celsius=row.celsius, recorded_at=row.recorded_at
        )


@app.get("/readings", response_model=list[ReadingOut])
def list_readings(sensor: str | None = None, limit: int = 100) -> list[ReadingOut]:
    limit = max(1, min(limit, 1000))
    with session() as db:
        stmt = select(Reading).order_by(Reading.id.desc()).limit(limit)
        if sensor is not None:
            stmt = stmt.where(Reading.sensor == sensor)
        rows = db.execute(stmt).scalars().all()
        return [
            ReadingOut(id=r.id, sensor=r.sensor, celsius=r.celsius, recorded_at=r.recorded_at)
            for r in rows
        ]


@app.get("/sensors/{sensor}/summary", response_model=SensorSummary)
def sensor_summary(sensor: str) -> SensorSummary:
    with session() as db:
        values = list(
            db.execute(select(Reading.celsius).where(Reading.sensor == sensor)).scalars().all()
        )
    try:
        return summarize(sensor, values)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
