"""Runtime settings read from the environment (no clock, no hidden defaults for ``as_of``)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: str | None = None
    gateway_url: str = "http://localhost:4000/v1"
    gateway_api_key: str = "not-set"
    model_name: str = "stub"
    horizon_days: int = 365
    max_concurrency: int = 2

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        d = cls()
        return cls(
            db_path=e.get("RM_DASHBOARD_DB", d.db_path),
            gateway_url=e.get("RM_GATEWAY_URL", d.gateway_url),
            gateway_api_key=e.get("RM_GATEWAY_API_KEY", d.gateway_api_key),
            model_name=e.get("RM_MODEL_NAME", d.model_name),
            horizon_days=int(e.get("RM_HORIZON_DAYS", d.horizon_days)),
            max_concurrency=int(e.get("RM_MAX_CONCURRENCY", d.max_concurrency)),
        )
