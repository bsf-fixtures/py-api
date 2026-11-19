# py-api

Build Software Factory fixture: a FastAPI service that genuinely needs a
database, so the sandbox has to run a sidecar.

Four endpoints over one table of sensor readings — enough for API-level
runtime verification, where the verifier calls the service rather than
clicking a page.

## Run

```bash
docker compose up -d db
export DATABASE_URL='postgresql+psycopg://pyapi:pyapi-throwaway@localhost:5432/pyapi_test'
pip install -e '.[dev]'
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

## Test

```bash
pytest                            # database tests skip without DATABASE_URL
ruff check .
mypy app
```

`tests/test_summary.py` and `tests/test_schemas.py` need no database.
`tests/test_api.py` skips, loudly, unless `DATABASE_URL` is set.

## Verify by hand

```bash
curl -s localhost:8000/health
# {"status":"ok"}  — ok only if the database answers

curl -s -X POST localhost:8000/readings \
  -H 'content-type: application/json' \
  -d '{"sensor":"kitchen","celsius":21.5}'

curl -s localhost:8000/sensors/kitchen/summary
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/sensors/nope/summary   # 404
```

## What this fixture exercises

- **Sidecar services in the sandbox.** Reaching a published Actions `services:`
  port from inside gh-aw's agent sandbox requires the `docker-sudo-iptables`
  runtime, which runs AWF with host privileges. This fixture is where that
  trade-off gets tested, and where the cheaper alternative — starting Postgres
  from `pre-agent-steps` inside the agent's own network — gets tried first.
- **API-level runtime verification**, with no browser involved.
- **A guardrail in an existing tool's config.** The ruff rules live in
  `pyproject.toml#tool.ruff`, which `policy.yaml` treats as a guardrail path:
  only hardening may tighten it, and any loosening needs a human.

## One thing it deliberately does not do

Nothing here reads a `.env` file. A build or test run must not be able to
reach a real database because a developer's credentials happen to be present —
the connection string comes from the environment the sandbox sets, and from
nowhere else.
