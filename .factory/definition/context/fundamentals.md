<!--
  The conventions no check enforces. Everything here is something a script
  could not decide, which is why it is prose.

  The bar for a line in this file: it has to be a judgement. If a static rule
  could catch it, it belongs in .factory/guardrails/ instead, because a rule
  is reproducible and prose is something agents argue with.

  Each line carries where it came from, so a line nobody can justify can be
  removed later.
-->

# Fundamentals — py-api

## Dominant patterns

For each recurring concern, the pattern most of this codebase already uses.
Follow it rather than introducing a second way of doing the same thing.

| Concern | The pattern here | Source |
| --- | --- | --- |
| Reading configuration | One module, `app/settings.py`, reads `os.environ` and raises a `RuntimeError` that names the variable and points at the README's Run section. Nothing else in `app/` touches the environment. | `app/settings.py:18` — the only `os.environ` call in `app/`, confirmed by grep at setup. |
| Database access | A `session()` context manager that commits on a clean exit, rolls back on an exception, and always closes. All four endpoints use `with session() as db:`. | `app/db.py:29`, used throughout `app/main.py`. |
| Engine construction | One module-level engine, built lazily on first use and cached in a module global, with `pool_pre_ping=True`. Never built at import time. | `app/db.py:12-20` |
| Validation | pydantic models in `app/schemas.py` carry the bounds — `Field(gt=-273.15, le=1000.0)`, `Field(min_length=1, max_length=64)`. Handlers do not re-check what the model already enforces. | `app/schemas.py`; `tests/test_schemas.py` tests the bounds through the model directly. |
| Turning a domain error into HTTP | The pure function raises `ValueError`; the route catches it and chooses the status. `summarize()` has no idea HTTP exists. | `app/summary.py:14` raises, `app/main.py:72` translates to 404. |
| Untrusted query parameters | Clamped in the handler rather than trusted or rejected: `limit = max(1, min(limit, 1000))`. The caller gets an answer, not a 422. | `app/main.py:51`, with `tests/test_api.py::test_limit_is_clamped_rather_than_trusted`. |
| Building a response | Handlers construct the pydantic `*Out` model explicitly from ORM columns rather than handing back the ORM object and letting serialization work it out. | `app/main.py`, in `add_reading` and `list_readings`. |
| Creating the schema | `Base.metadata.create_all()` in the FastAPI lifespan, documented as idempotent so a restart is harmless. There is no migration tool and no plan for one. | `app/main.py:21-23`, `app/db.py:23` |
| Tests that need the database | A session-scoped `database_url` fixture that calls `pytest.skip` with a message naming what to start. Database tests take the `client` fixture, which pulls the skip in transitively. | `tests/conftest.py:18` |
| Naming a test | The name is the claim, written as a sentence: `test_summary_for_an_unknown_sensor_is_a_404_not_a_row_of_zeros`. | Every test file; no exceptions in the repo. |
| Typing | Full annotations everywhere, including test signatures. `mypy` runs with `strict = true` over `app/` and there is no `# type: ignore` anywhere in the repo. | `pyproject.toml#tool.mypy`; verified clean at setup against mypy 2.4.1. |
| Module docstrings | Every module opens with one line saying what it owns, and several add the thing it deliberately does *not* do. | All seven modules in `app/` and all four files in `tests/`. |

## Product intent

`README.md` says it in its first line: this is a **Build Software Factory
fixture**. It is not a product with users. It exists to prove two things — that
the sandbox can run a sidecar database, and that a verifier can check a change
by calling an API rather than clicking a page. Two consequences for decisions
an agent has to make here:

- **Small is the specification, not a stage it is growing out of.** Four
  endpoints over one table is the point. A change that adds a second table, a
  second external dependency, or a second concern makes the fixture worse at
  the job it exists for, even if it would make a real product better. Say so
  before implementing it.
- **The parts that look over-careful are the product.** The refusal to read a
  `.env`; the `RuntimeError` that names the missing variable; the 404 instead
  of a row of zeros; the clamp on `limit`; splitting `summary.py` out so it can
  be tested with no database. Each of those is a behaviour the fixture exists
  to demonstrate. Removing one in the name of simplification removes the thing
  being demonstrated. `README.md`'s "One thing it deliberately does not do"
  section is load-bearing documentation, not a footnote.

## Taste

Things a reviewer would ask for that no rule states.

- **A test name states its claim.** `test_limit_is_clamped_rather_than_trusted`
  and `test_refuses_an_empty_list_rather_than_reporting_zeros` are the register.
  A test called `test_summary_2` would be sent back, even passing.
- **Comments explain the choice, not the mechanism.** `# Absolute zero is the
  floor; anything below it is a bad reading, not a cold day.` earns its line. A
  comment restating the code beneath it does not. Several comments in this repo
  explain a decision *not* to do something, which is the hardest thing to
  recover from code alone and the most worth writing down.
- **An empty result is not zero.** `summarize()` raises rather than returning
  `count=0, mean=0.0`, because zeros read like measurements someone took.
  Prefer refusing over inventing a neutral value, and let the caller decide
  what the absence means.
- **Error messages say what to do next.** The `DATABASE_URL` error names the
  variable *and* points at the README section that explains how to set it. The
  `pytest.skip` message says "start the sidecar Postgres".
- **Bounds live on the model.** If you find yourself re-validating in a handler,
  the model is wrong — fix it there.
- **Keep arithmetic away from the session.** `app/summary.py` exists only so
  that the interesting logic can be tested without a sidecar. New logic that
  could be pure should go somewhere pure.

## Deliberate exceptions

Places that look like they break a rule and should stay as they are, with the
reason. Without this section, cleanup keeps rediscovering them.

| Place | Looks like | Why it stays |
| --- | --- | --- |
| `app/db.py:12-14` — the module-level `_engine` and `_session_factory` globals | Mutable module state, which a reviewer would normally object to. | A deliberate lazy singleton. The engine must not be built at import time: `create_engine` would then need `DATABASE_URL` just to `import app.main`, and `tests/test_summary.py` and `tests/test_schemas.py` could no longer run without a database. The globals are what buy that. |
| `tests/conftest.py:18` — skipping rather than failing when `DATABASE_URL` is unset | A suite that reports green having run a third fewer tests. | Deliberate, so `pytest` works on a laptop with no sidecar — `README.md` says so. The hole is closed from the other side instead: the sandbox's `test` command connects to the database before invoking pytest, so in the factory a missing database fails the step rather than shrinking the suite. Do not "fix" this by making the fixture raise. |
| `pyproject.toml#tool.ruff` | An ordinary tool config that an agent would normally edit freely. | It is listed as a guardrail path in `.factory/definition/policy.yaml`. Only the hardening pipeline may tighten it, and any loosening needs a trusted human. `README.md` calls this out as one of the things the fixture exists to exercise. |
| `app/settings.py` not loading a `.env` file | Every other Python service of this shape loads dotenv, and `python-dotenv` is even present in the installed tree. | Stated as deliberate in both `README.md` and the module docstring: a build or test run must not be able to reach a real database because a developer's credentials happen to be lying around. `python-dotenv` is there only as a transitive dependency of `uvicorn[standard]`; no code in this repo imports it, and none should. |
| `app/main.py:51` — clamping `limit` silently instead of returning 422 | Swallowing bad input rather than rejecting it, which contradicts the strictness of `app/schemas.py`. | The two are different cases on purpose. A celsius value below absolute zero is a *broken sensor* and must be refused. An oversized `limit` is a caller asking for more than the service will give, and the useful answer is the most it will give. The test name says as much. |
