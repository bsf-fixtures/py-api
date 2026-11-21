"""API-level tests. These need the sidecar Postgres (see conftest)."""

from typing import Any


def test_health_reports_ok_only_when_the_database_answers(client: Any) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_posting_a_reading_returns_it_with_an_id(client: Any) -> None:
    res = client.post("/readings", json={"sensor": "test-a", "celsius": 19.25})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] > 0
    assert body["sensor"] == "test-a"
    assert body["celsius"] == 19.25
    assert body["recorded_at"]


def test_a_posted_reading_comes_back_in_the_list(client: Any) -> None:
    client.post("/readings", json={"sensor": "test-b", "celsius": 5.0})
    res = client.get("/readings", params={"sensor": "test-b"})
    assert res.status_code == 200
    assert any(r["sensor"] == "test-b" for r in res.json())


def test_rejects_a_reading_below_absolute_zero(client: Any) -> None:
    res = client.post("/readings", json={"sensor": "test-c", "celsius": -400.0})
    assert res.status_code == 422


def test_summary_reflects_the_readings_posted(client: Any) -> None:
    for c in (10.0, 20.0, 30.0):
        client.post("/readings", json={"sensor": "test-summary", "celsius": c})
    res = client.get("/sensors/test-summary/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 3
    assert body["min_celsius"] == 10.0
    assert body["max_celsius"] == 30.0
    assert body["mean_celsius"] == 20.0


def test_summary_for_an_unknown_sensor_is_a_404_not_a_row_of_zeros(client: Any) -> None:
    res = client.get("/sensors/no-such-sensor/summary")
    assert res.status_code == 404


def test_limit_is_clamped_rather_than_trusted(client: Any) -> None:
    res = client.get("/readings", params={"limit": 100000})
    assert res.status_code == 200
    assert len(res.json()) <= 1000


# The seed data and earlier tests leave rows behind, so every assertion below
# looks its own sensor up rather than measuring the whole list.
def _entry(body: list[dict[str, Any]], sensor: str) -> dict[str, Any] | None:
    return next((e for e in body if e["sensor"] == sensor), None)


def test_sensors_lists_each_sensor_once_with_its_reading_count(client: Any) -> None:
    for c in (1.0, 2.0):
        client.post("/readings", json={"sensor": "test-sensors-a", "celsius": c})
    client.post("/readings", json={"sensor": "test-sensors-b", "celsius": 3.0})
    res = client.get("/sensors")
    assert res.status_code == 200
    body = res.json()
    assert _entry(body, "test-sensors-a") is not None
    assert _entry(body, "test-sensors-a")["count"] == 2
    assert _entry(body, "test-sensors-b")["count"] == 1


def test_sensors_are_ordered_by_name(client: Any) -> None:
    res = client.get("/sensors")
    assert res.status_code == 200
    names = [e["sensor"] for e in res.json()]
    assert names == sorted(names)


def test_sensors_reports_the_time_of_the_most_recent_reading(client: Any) -> None:
    first = client.post("/readings", json={"sensor": "test-sensors-latest", "celsius": 1.0})
    second = client.post("/readings", json={"sensor": "test-sensors-latest", "celsius": 2.0})
    entry = _entry(client.get("/sensors").json(), "test-sensors-latest")
    assert entry is not None
    assert entry["latest_reading_at"] == second.json()["recorded_at"]
    assert entry["latest_reading_at"] != first.json()["recorded_at"]


def test_a_sensor_that_never_reported_is_absent_from_the_list(client: Any) -> None:
    res = client.get("/sensors")
    assert res.status_code == 200
    assert _entry(res.json(), "test-sensors-never") is None
