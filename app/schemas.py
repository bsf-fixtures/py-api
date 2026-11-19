"""Request and response shapes."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    sensor: str = Field(min_length=1, max_length=64)
    # Absolute zero is the floor; anything below it is a bad reading, not a cold day.
    celsius: float = Field(gt=-273.15, le=1000.0)


class ReadingOut(BaseModel):
    id: int
    sensor: str
    celsius: float
    recorded_at: datetime


class SensorSummary(BaseModel):
    sensor: str
    count: int
    min_celsius: float
    max_celsius: float
    mean_celsius: float
