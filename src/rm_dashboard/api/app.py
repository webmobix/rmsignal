"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from ..data.datasource import SqliteDataSource
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


def create_app(db_path: str | Path, reports_dir: str | Path | None = None,
               scenarios: ScenarioProvider | None = None) -> FastAPI:
    """Build the app serving the database at ``db_path``.

    ``reports_dir`` is the folder of persisted runs (``<reports>/<as_of>/...``). Without it the read
    endpoints answer 404 for lack of a run; ``/api/sources`` is unaffected.

    Raises FileNotFoundError (naming the seed command or the folder) if the database or the folder is missing.
    """
    SqliteDataSource(db_path).close()
    reports = Path(reports_dir) if reports_dir is not None else None
    if reports is not None and not reports.is_dir():
        raise FileNotFoundError(f"reports folder not found: {reports} (create runs with `rm-dashboard-analyse`)")
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

    app.state.db_path = Path(db_path)
    app.state.read = ReadContext.build(Path(db_path), reports)
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
