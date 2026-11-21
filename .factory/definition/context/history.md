<!--
  What has gone wrong before, and what was learned. Seeded by setup from the
  mined corrections, then added to by the scheduled review.

  This file is for failures whose lesson could not be turned into a check. A
  correction that became a rule does not belong here: the rule is the record,
  and repeating it in prose means two things to keep in step.
-->

# History — py-api

## Lessons

**No corrections were mined for this file.** This is setup round 1 on a repo
with a single commit of its own history (`12b250b`, "Upgrade the factory to
e29d8e0"), no merged pull requests, and no prior factory runs. Nothing was read
from anyone's agent sessions. Every row below is a failure the setup episode
hit itself and could reproduce — nothing here is inferred from how the code
looks.

| What happened | What to do instead | Where it came from |
| --- | --- | --- |
| Running the test suite twice against the same database failed the second time: `tests/test_api.py::test_summary_reflects_the_readings_posted` asserted `6 == 3`. The suite POSTs rows under sensors named `test-a`, `test-b` and `test-summary` and never cleans up, so the second run counts the first run's rows. CI never sees this because its service container is fresh; a role iterating on a change in one sandbox does. | Make the *command* idempotent, not the test. The sandbox's `test` command deletes rows whose sensor is `LIKE 'test-%'` before invoking pytest — exactly what the suite inserts, nothing else. If you are tempted to relax that `== 3` assertion to make a run pass, this is why it failed, and relaxing it is the wrong fix. | Setup round 1, attempt 8: ran the test command three times in a row and watched the second fail. |
| `pytest` reported a green run having touched no database at all. `tests/conftest.py:18` calls `pytest.skip` when `DATABASE_URL` is unset, so all seven tests in `tests/test_api.py` disappear and the suite still exits 0 — *11 passed, 7 skipped*. A sandbox that pointed `DATABASE_URL` at nothing would be indistinguishable from one that got it right. | Make the database a precondition of the step rather than something the tests discover. The sandbox's `test` command connects first, retrying for 60s, and exits with a message naming `DATABASE_URL` if it never answers. Treat "the tests passed" as meaningless here unless you also know the database was up. | Setup round 1, attempt 3: ran `pytest -rs` with `DATABASE_URL` deliberately unset. |
| `localhost` is not `127.0.0.1`. `README.md` and `.github/workflows/ci.yml` both put `localhost` in `DATABASE_URL`; `localhost` can resolve to `::1`, where a service bound to `127.0.0.1` does not answer, and the failure looks like a dead database rather than a name-resolution choice. | Use the literal `127.0.0.1` everywhere in the sandbox — in `DATABASE_URL` and in `app_url`. | Setup round 1, writing the manifest. Not reproduced as a failure here, since the sandbox never used `localhost`; recorded because the two files an agent would copy from both contain it. |
| A sidecar's TCP port opening is not the same as its database accepting connections. The sandbox's only readiness option is a port check, and `compose.yaml`'s `pg_isready` healthcheck does not carry over into it. | Keep a real connect-and-retry in whichever step actually needs the database, rather than trusting the port probe. The `test` command's preamble is that check. | Setup round 1, attempt 4: read how `bsf sandbox trial` starts a service and waits for it. |
| `uvicorn --reload`, which `README.md`'s Run section uses, starts a file-watching supervisor that re-execs a child process. The sandbox stops the app by signalling its process group, and a supervisor in between makes what is actually running ambiguous. | Run a single non-reloading process in the sandbox. `--reload` belongs on a developer's laptop. | Setup round 1, writing the manifest. |
| `pip install -e '.[dev]'` as `README.md` writes it depends on a virtualenv or `actions/setup-python` already being arranged. Ubuntu 24.04 marks its system Python externally managed (PEP 668) and refuses the install outright. | Build a venv at `.venv/` and call its binaries by path in every command, so nothing depends on which interpreter is first on `PATH`. | Setup round 1, attempt 2. |

## Problem classes already eliminated

Kept so nobody proposes a rule that exists, and so a regression is
recognisable as one.

Everything in this table was already true at commit `12b250b`, before the
factory was installed. The dates are "before setup" because this repo's git
history does not record when each was introduced — there is one commit.

| Problem class | How it was eliminated | When |
| --- | --- | --- |
| A build or test run reaching a real database because a developer's credentials were lying around | `app/settings.py` reads only `os.environ`; nothing in the repo imports dotenv or loads a config file, and `.env*` is in `.gitignore`. The sandbox supplies a closed environment, so a variable nobody listed is absent rather than inherited, and the app fails loudly instead of connecting to something real. | Before setup; stated as deliberate in `README.md`'s "One thing it deliberately does not do". |
| A summary endpoint answering for a sensor that never reported, with a row of zeros that reads like real measurements | `summarize()` raises `ValueError` on an empty list and `app/main.py:72` turns that into a 404. Covered at both layers: `tests/test_summary.py::test_refuses_an_empty_list_rather_than_reporting_zeros` and `tests/test_api.py::test_summary_for_an_unknown_sensor_is_a_404_not_a_row_of_zeros`. | Before setup. |
| An unbounded `limit` on `GET /readings` letting a caller ask for the whole table | Clamped to 1..1000 in the handler (`app/main.py:51`), with `tests/test_api.py::test_limit_is_clamped_rather_than_trusted`. | Before setup. |
| A physically impossible sensor reading being stored as data | `app/schemas.py` bounds `celsius` to `> -273.15` and `<= 1000.0` and `sensor` to 1–64 characters, enforced by pydantic at the edge. Tested through the model (`tests/test_schemas.py`) and over HTTP (422, `tests/test_api.py`). | Before setup. |
| Untyped code drifting into `app/` | `mypy` with `strict = true` over `app/`, run in CI before the tests. Clean at setup with no `# type: ignore` anywhere in the repo. | Before setup; `.github/workflows/ci.yml`. |
| A session left open, or a failed write committed anyway | The `session()` context manager in `app/db.py:29` commits on a clean exit, rolls back on any exception, and closes in a `finally`. Every database access in `app/main.py` goes through it; nothing else constructs a `Session`. | Before setup. |
| Lint rules being quietly relaxed to make a change pass | `pyproject.toml#tool.ruff` is a guardrail path in `.factory/definition/policy.yaml`: only the hardening pipeline may tighten it, and loosening needs a trusted human. | At factory install (`12b250b`). |

## Escalations

Work the factory could not finish, and why. A pattern across several of these
is a signal about the factory rather than about the work.

| Work item | Where it stopped | Cause |
| --- | --- | --- |

No work has run through the factory yet — this is setup round 1, so there is
nothing to escalate. The table is empty on purpose rather than filled with a
guess.

One thing worth knowing before the first run, which is not an escalation but
would become one: the sandbox cannot exercise schema migrations, durability
across a restart, connection pooling under concurrency, or any Postgres
version other than `17-alpine`. Those are recorded with their paths under
`capabilities.not_exercised` in the sandbox manifest. A change touching
`app/models.py` or `app/db.py` is the case to watch, because the sandbox will
report green on exactly the class of mistake it cannot see.
