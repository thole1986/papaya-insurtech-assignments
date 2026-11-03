import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import ROOT, Settings
from app.core.errors import AppError
from app.repositories.database import Database
from app.repositories.fixtures import Catalog
from app.services.assessment import AssessmentService


def create_app(settings: Settings | None = None, provider_factory=None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.database_url)
        try:
            await db.start()
            catalog = Catalog()
            app.state.db, app.state.catalog, app.state.settings = db, catalog, settings
            app.state.service = AssessmentService(db, catalog, settings, provider_factory)
            logging.getLogger(__name__).info("claim_agent_started mode=%s", settings.run_mode)
            yield
        finally:
            await db.close()

    app = FastAPI(
        title="Claim Assessment Agent",
        version="0.1.0",
        lifespan=lifespan,
        description="Local synthetic-data MVP. Offline mode is explicit; live mode uses Gemini.",
    )

    @app.exception_handler(AppError)
    async def app_error(request: Request, error: AppError):
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": settings.run_mode}

    @app.get("/ready")
    async def ready():
        await app.state.db.ready()
        return JSONResponse(
            status_code=200 if settings.provider_ready else 503,
            content={
                "database": "ready",
                "mode": settings.run_mode,
                "provider_configured": settings.provider_ready,
                "provider_credentials_verified": False,
            },
        )

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(ROOT / "app/static/index.html")

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    return app


app = create_app()
