<!--
  How to build, run, test and verify this app. Written by setup's phase 2,
  with every command tested rather than copied from a README.

  This is the most load-bearing context file: a verifier agent that cannot
  start the app cannot verify anything, and then the factory produces
  confident unverified PRs.
-->

# Runbook — py-api

Every command below was run at setup against a real PostgreSQL server, with
the output recorded. Where this disagrees with `README.md`, the difference is
deliberate and the reason is given.

## Build

```bash
PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3); "$PY" -m venv .venv && .venv/bin/pip install --quiet --disable-pip-version-check -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/mypy app
```

Python has no compile step. The first line is the manifest's `install`; the
second is its `build`, and is the pair of static checks CI runs before the
tests.

- The venv lives at `.venv/` in the repo root and is already in `.gitignore`.
  Every command in this runbook calls binaries inside it **by path**, so
  nothing depends on which interpreter happens to be first on `PATH`, and
  nothing is blocked by Ubuntu 24.04 marking its system Python externally
  managed (PEP 668). `README.md`'s bare `pip install -e '.[dev]'` works only
  where a virtualenv or `actions/setup-python` has already been arranged.
- The interpreter is picked newest-first among 3.13, 3.12 and 3.11, falling
  back to `python3`, because `pyproject.toml` sets
  `requires-python = ">=3.11"`. Measured at setup: Python 3.13.18.
- Measured at setup: install exit 0, `ruff check .` → "All checks passed!",
  `mypy app` → "Success: no issues found in 7 source files". `[tool.mypy]` sets
  `strict = true`, and there is no `# type: ignore` anywhere in the repo.
- `pyproject.toml#tool.ruff` is a **guardrail path** in
  `.factory/definition/policy.yaml`. Only the hardening pipeline may tighten
  it, and loosening it needs a trusted human.

## Run

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The app is then at http://127.0.0.1:8000/docs.

Two differences from `README.md`'s Run section, both deliberate:

- **No `--reload`.** The reloader starts a file-watching supervisor that
  re-execs a child process; the sandbox stops the app by signalling its
  process group, and a supervisor in the middle makes what is actually running
  harder to reason about. `--reload` is for a developer's laptop.
- **`127.0.0.1`, not `localhost`.** `localhost` can resolve to `::1`, where a
  process bound to `127.0.0.1` does not answer. The literal address is used
  for both `DATABASE_URL` and the app URL.

`DATABASE_URL` must be set before this runs. The startup lifespan calls
`Base.metadata.create_all()` (`app/main.py:21-23`), and `app/settings.py:18`
raises a `RuntimeError` naming the variable if it is missing.

## Test

```bash
.venv/bin/python -c '
import sys, time

from sqlalchemy import text

from app.db import create_all, engine

last = None
for _ in range(60):
    try:
        create_all()
        break
    except Exception as exc:
        last = exc
        time.sleep(1)
else:
    sys.exit("the sandbox database never answered at DATABASE_URL: %s" % last)

with engine().begin() as conn:
    n = conn.execute(
        text("DELETE FROM readings WHERE sensor LIKE :prefix"), {"prefix": "test-%"}
    ).rowcount
print("database ready; cleared %d row(s) left by a previous test run" % n)
' && .venv/bin/pytest --cov=app --cov-report=term-missing
```

Measured at setup: **18 passed, 96% total coverage**, and the same result on
each of three consecutive runs against the same database.

The preamble is not ceremony. It does two things that the suite needs and does
not do for itself:

- **It makes the database a precondition rather than a discovery.**
  `tests/conftest.py:18` calls `pytest.skip` when `DATABASE_URL` is unset, so
  all seven tests in `tests/test_api.py` vanish and the run still exits 0.
  Setup confirmed this: with the variable unset, `pytest -rs` reports *11
  passed, 7 skipped*. A sandbox that pointed `DATABASE_URL` somewhere wrong
  would look exactly like one that got it right. Connecting first turns that
  into a failed step with a message.
- **It makes the suite repeatable.** `tests/test_api.py` POSTs rows under
  sensors named `test-a`, `test-b` and `test-summary` and never cleans up, so a
  second run counts the first run's rows and
  `test_summary_reflects_the_readings_posted` fails with `assert 6 == 3`. Setup
  hit this. The `DELETE ... LIKE 'test-%'` removes exactly what the suite
  inserts and nothing else — seed data under `kitchen` and `garage` is
  untouched, which setup verified.

Also worth knowing:

- `tests/test_summary.py` and `tests/test_schemas.py` need no database and run
  anywhere.
- `ruff check .` and `mypy app` are in **Build**, in the order CI runs them —
  both before `pytest`.
- `[tool.pytest.ini_options]` already sets `testpaths = ["tests"]` and
  `addopts = "-q"`.

## Verify

How to see for yourself that the app works, as a developer would. Start the
database and the app first; every output below was observed at setup.

1. **The app is up and the database answers.** `/health` runs a real
   `SELECT 1` through a session, so it is a readiness check, not a liveness
   ping — it fails when Postgres is gone.

   ```bash
   curl -s http://127.0.0.1:8000/health
   # {"status":"ok"}
   ```

2. **Write a reading.** It comes back with an id and a server-set timestamp.

   ```bash
   curl -s -X POST http://127.0.0.1:8000/readings \
     -H 'content-type: application/json' \
     -d '{"sensor":"kitchen","celsius":21.5}'
   # {"id":6,"sensor":"kitchen","celsius":21.5,"recorded_at":"2026-11-21T04:33:55.333442Z"}
   ```

3. **Summarize a sensor.** After the seed command below:

   ```bash
   curl -s http://127.0.0.1:8000/sensors/kitchen/summary
   # {"sensor":"kitchen","count":3,"min_celsius":19.0,"max_celsius":23.25,"mean_celsius":21.25}
   curl -s http://127.0.0.1:8000/sensors/garage/summary
   # {"sensor":"garage","count":2,"min_celsius":8.5,"max_celsius":11.0,"mean_celsius":9.75}
   ```

4. **A sensor with no readings is a 404, not a row of zeros.**

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/sensors/nope/summary
   # 404
   ```

5. **A reading below absolute zero is rejected at the edge**, by the pydantic
   model rather than the handler.

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/readings \
     -H 'content-type: application/json' -d '{"sensor":"kitchen","celsius":-400}'
   # 422
   ```

6. **In a browser.** Open http://127.0.0.1:8000/docs — the page a person lands
   on. Swagger UI lists all four operations (`GET /health`, `POST /readings`,
   `GET /readings`, `GET /sensors/{sensor}/summary`) and five schemas
   (`HTTPValidationError`, `ReadingIn`, `ReadingOut`, `SensorSummary`,
   `ValidationError`). Verified at setup with a full-page screenshot.

   The page pulls its bundle and stylesheet from `cdn.jsdelivr.net` and its
   favicon from `fastapi.tiangolo.com`. Both are in the sandbox's `egress`
   list. Without `cdn.jsdelivr.net` the page still returns 200 but renders
   blank, which looks like a broken app and is not one.

## Seed data

```bash
.venv/bin/python -c '
from app.db import create_all, session
from app.models import Reading

create_all()
rows = [("kitchen", 21.5), ("kitchen", 19.0), ("kitchen", 23.25),
        ("garage", 8.5), ("garage", 11.0)]
with session() as db:
    for sensor, celsius in rows:
        db.add(Reading(sensor=sensor, celsius=celsius))
print("seeded %d readings across 2 sensors" % len(rows))
'
```

- **There is no seed script in the repo.** This one was written and run by the
  setup episode. It goes through the app's own `Reading` model and `session()`
  context manager, so it exercises the same write path a request does, and it
  needs only `DATABASE_URL` — the server does not have to be running.
- Measured at setup: `seeded 5 readings across 2 sensors`, after which the two
  summary endpoints returned the values quoted in Verify step 3.
- **It is additive.** Running it twice doubles the rows. Nothing in it deletes.
- Two sensors rather than one, so `GET /readings?sensor=` and the per-sensor
  summary have something to actually distinguish.
- The sensor names avoid the `test-` prefix on purpose, so the test command's
  cleanup does not remove the seed data.
- The sandbox's database is a `--rm` container with no volume, so seed data
  does not survive the sandbox.

## Commands that change persistent state

These are kept out of the build path on purpose. Each one writes to something
that outlives the process, so running it against the wrong target is the kind
of mistake that cannot be undone by reverting a commit.

| Command | Writes to | Only when |
| --- | --- | --- |
| `.venv/bin/uvicorn app.main:app ...` — at startup, not per request | The database at `DATABASE_URL`. The lifespan calls `Base.metadata.create_all()`, issuing `CREATE TABLE` for any table in `app/models.py` that is missing. | Every single start, unavoidably. This is the main reason `DATABASE_URL` must never name anything real: merely starting the app writes to it. |
| The seed command above | The `readings` table at `DATABASE_URL`. Inserts only; repeats accumulate. | By hand, against the sandbox's throwaway database. |
| `.venv/bin/pytest` with `DATABASE_URL` set | The `readings` table at `DATABASE_URL`. `tests/test_api.py` POSTs rows under `test-a`, `test-b` and `test-summary` and does not clean up after itself. | Against the sandbox's throwaway database only. This one *is* in the build path, which is precisely why the throwaway has to be real and the credentials have to be worthless. |
| The test command's preamble | The `readings` table at `DATABASE_URL`. `DELETE FROM readings WHERE sensor LIKE 'test-%'` — the only deletion anywhere in this runbook. | Part of the test command. Scoped to the prefix the suite itself uses; it cannot touch a row this repo's tests did not create. |

There is no migration command, because there is no migration tool. A change to
`app/models.py` reaches an existing table only by someone dropping and
recreating it.

## Services this app needs

| Service | How it starts | Reached at |
| --- | --- | --- |
| `db` — PostgreSQL 17 (`postgres:17-alpine`) | Declared under `services` in `.factory/sandbox/manifest.json`; `bsf sandbox start` brings it up as `docker run -d --rm --name bsf-db -p 127.0.0.1:5432:5432 -e POSTGRES_USER=pyapi -e POSTGRES_PASSWORD=pyapi-throwaway -e POSTGRES_DB=pyapi_test postgres:17-alpine`, then waits up to 90s for the port. On a laptop, `docker compose up -d db` starts the same image from `compose.yaml`. | `127.0.0.1:5432`, as `DATABASE_URL`. `--rm` with no volume, so it is empty at every start. |

That is the only service. The app has no cache, queue, object store or mail
path, and makes no outbound HTTP calls.

## The sandbox's environment

Built from this list, and from nothing else. It does not inherit a
developer's environment and it does not read any `.env` file, because a
documented build command that runs a migration would otherwise migrate
whatever a developer's credentials happen to point at.

| Variable | Value in the sandbox |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://pyapi:pyapi-throwaway@127.0.0.1:5432/pyapi_test` — the throwaway sidecar above, with the credentials the repo already publishes in `compose.yaml` and `ci.yml`. |

One row, and that is the whole list. `app/settings.py:18` and
`tests/conftest.py:16` are the only two reads of the environment in the repo,
and both read `DATABASE_URL`. Anything else an agent believes the app needs
from the environment is a belief this repo does not support — check it against
the code before acting on it.
