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
