"""Summary arithmetic, kept apart from the database so it can be tested alone."""

from app.schemas import SensorSummary


def summarize(sensor: str, values: list[float]) -> SensorSummary:
    """Summarize one sensor's readings.

    An empty list has no summary: the caller decides whether that is a 404 or
    an empty response, rather than this returning zeros that read like real
    measurements.
    """
    if not values:
        raise ValueError(f"no readings for sensor {sensor!r}")
    return SensorSummary(
        sensor=sensor,
        count=len(values),
        min_celsius=min(values),
        max_celsius=max(values),
        mean_celsius=round(sum(values) / len(values), 4),
    )
