"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from ..data.factory import open_data_source
from ..store import ArtifactStore, SqliteArtifactStore, as_store
from .callsheet import router as callsheet_router
from .clients import router as clients_router
from .context import ReadContext
from .core import router as core_router
from .evidence import router as evidence_router
from .instruments import router as instruments_router
from .market import router as market_router
from .overview import router as overview_router
from .scenarios import ComputedScenarioProvider, ScenarioProvider
from .scenarios import router as scenarios_router
from .portfolios import router as portfolios_router
from .sources import router as sources_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: str | Path, artifact_store: ArtifactStore | str | Path | None = None,
               scenarios: ScenarioProvider | None = None) -> FastAPI:
    """Build the app serving the source data at ``db_path``: a SQLite file, or a data source spec (``firestore:<project>``).

    ``artifact_store`` is where the runs were saved: a store, a store spec (``sqlite:<file>``, ``firestore:<project>``) or the
    folder holding ``artifacts.db``. Without it the read endpoints answer 404 for lack of a run; ``/api/sources`` is unaffected.

    Raises FileNotFoundError (naming the seed command or the folder) if the database or the SQLite store's folder is missing.
    """
    open_data_source(db_path).close()  # fails early: missing file, unknown backend or Firestore library not installed
    store = as_store(artifact_store) if artifact_store is not None else None
    if isinstance(store, SqliteArtifactStore) and not store.path.parent.is_dir():
        raise FileNotFoundError(f"reports folder not found: {store.path.parent} (create runs with `rm-dashboard-analyse`)")
    # Swagger UI assets are served locally: the default page loads them from a CDN
    # and renders blank when that is unreachable (offline, IDE browsers, blockers).
    app = FastAPI(title="rm-dashboard", docs_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/docs", include_in_schema=False)
    def docs():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - docs",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
            swagger_favicon_url="data:,",
        )

    app.state.open_data_source = lambda: open_data_source(db_path)
    app.state.read = ReadContext.build(db_path, store)
    app.state.scenarios = scenarios or ComputedScenarioProvider(app.state.read)  # rollback: PlaceholderScenarioProvider()
    app.include_router(sources_router)
    app.include_router(core_router)
    app.include_router(overview_router)
    app.include_router(evidence_router)
    app.include_router(portfolios_router)
    app.include_router(callsheet_router)
    app.include_router(clients_router)
    app.include_router(instruments_router)
    app.include_router(market_router)
    app.include_router(scenarios_router)
    return app
