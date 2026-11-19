"""Validation at the edge. No database needed."""

import pytest
from pydantic import ValidationError

from app.schemas import ReadingIn


def test_accepts_an_ordinary_reading() -> None:
    r = ReadingIn(sensor="kitchen", celsius=21.5)
    assert r.sensor == "kitchen"


def test_rejects_a_reading_below_absolute_zero() -> None:
    # Below absolute zero is a broken sensor, not a cold day.
    with pytest.raises(ValidationError):
        ReadingIn(sensor="kitchen", celsius=-300.0)


def test_rejects_an_empty_sensor_name() -> None:
    with pytest.raises(ValidationError):
        ReadingIn(sensor="", celsius=20.0)


def test_rejects_an_absurdly_high_reading() -> None:
    with pytest.raises(ValidationError):
        ReadingIn(sensor="kitchen", celsius=5000.0)


def test_accepts_exactly_the_upper_bound() -> None:
    assert ReadingIn(sensor="furnace", celsius=1000.0).celsius == 1000.0
