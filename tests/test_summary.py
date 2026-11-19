"""Summary arithmetic. No database needed, so these run anywhere."""

import pytest

from app.summary import summarize


def test_summarizes_a_single_reading() -> None:
    s = summarize("s1", [20.0])
    assert s.count == 1
    assert s.min_celsius == 20.0
    assert s.max_celsius == 20.0
    assert s.mean_celsius == 20.0


def test_summarizes_several_readings() -> None:
    s = summarize("s1", [10.0, 20.0, 30.0])
    assert s.count == 3
    assert s.min_celsius == 10.0
    assert s.max_celsius == 30.0
    assert s.mean_celsius == 20.0


def test_rounds_the_mean_rather_than_returning_a_long_float() -> None:
    s = summarize("s1", [1.0, 2.0])
    assert s.mean_celsius == 1.5
    s2 = summarize("s1", [1.0, 1.0, 2.0])
    assert s2.mean_celsius == 1.3333


def test_handles_negative_readings() -> None:
    s = summarize("s1", [-5.5, -10.0])
    assert s.min_celsius == -10.0
    assert s.max_celsius == -5.5


def test_refuses_an_empty_list_rather_than_reporting_zeros() -> None:
    # Zeros would read like real measurements; the caller must decide.
    with pytest.raises(ValueError, match="no readings"):
        summarize("s1", [])


def test_keeps_the_sensor_name() -> None:
    assert summarize("kitchen-3", [1.0]).sensor == "kitchen-3"
