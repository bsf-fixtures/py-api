"""Settings read from the environment.

The sandbox points DATABASE_URL at a throwaway Postgres. Nothing here reads a
.env file on purpose: a build or test run must never be able to reach a real
database just because a developer's credentials happen to be present.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str

    @staticmethod
    def from_env() -> "Settings":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Start the sidecar Postgres and point "
                "DATABASE_URL at it; see the Run section of the README."
            )
        return Settings(database_url=url)
