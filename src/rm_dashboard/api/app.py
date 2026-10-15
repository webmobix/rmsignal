"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from ..data.datasource import SqliteDataSource
from .sources import router as sources_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: str | Path) -> FastAPI:
    """Build the app serving the database at ``db_path``.

    Raises FileNotFoundError (naming the seed command) if the database is missing.
    """
    SqliteDataSource(db_path).close()
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
    app.include_router(sources_router)
    return app
