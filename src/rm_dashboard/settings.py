"""Runtime settings read from the environment (no clock, no hidden defaults for ``as_of``)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: str | None = None
    gateway_url: str = "http://localhost:4000/v1"
    gateway_api_key: str = "not-set"
    model_name: str = "stub"
    model_provider: str = "gateway"
    """``gateway`` (OpenAI-compatible endpoint) or ``vertex`` (Gemini on Vertex AI, Google application default credentials)."""
    vertex_project: str | None = None
    """Vertex AI project; default: ``GOOGLE_CLOUD_PROJECT``, else the project of the Google credentials."""
    vertex_location: str = "global"
    horizon_days: int = 365
    max_concurrency: int = 2
    data_source: str | None = None
    """``sqlite:<file>`` or ``firestore:<project>[/<database>]``; where the source tables are read from. Default: ``db_path``."""
    artifact_store: str = "sqlite:reports/artifacts.db"
    """``sqlite:<file or folder>`` or ``firestore:<project>[/<database>]``; where generated artifacts live."""

    @property
    def data_source_spec(self) -> str | None:
        """The configured source-data backend: ``data_source``, else the SQLite file ``db_path``, else ``None``."""
        return self.data_source or (f"sqlite:{self.db_path}" if self.db_path else None)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        d = cls()
        return cls(
            db_path=e.get("RM_DASHBOARD_DB", d.db_path),
            gateway_url=e.get("RM_GATEWAY_URL", d.gateway_url),
            gateway_api_key=e.get("RM_GATEWAY_API_KEY", d.gateway_api_key),
            model_name=e.get("RM_MODEL_NAME", d.model_name),
            model_provider=e.get("RM_MODEL_PROVIDER", d.model_provider),
            vertex_project=e.get("RM_VERTEX_PROJECT") or e.get("GOOGLE_CLOUD_PROJECT") or d.vertex_project,
            vertex_location=e.get("RM_VERTEX_LOCATION", d.vertex_location),
            horizon_days=int(e.get("RM_HORIZON_DAYS", d.horizon_days)),
            max_concurrency=int(e.get("RM_MAX_CONCURRENCY", d.max_concurrency)),
            data_source=e.get("RM_DATA_SOURCE", d.data_source),
            artifact_store=e.get("RM_ARTIFACT_STORE", d.artifact_store),
        )
