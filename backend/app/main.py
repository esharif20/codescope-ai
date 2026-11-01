"""ASGI application factory; construction performs no GitHub or analysis work."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.api import (
    AnalysisBoundary,
    create_router,
    http_error_handler,
    ingestion_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.ingestion.github import GitHubClient
from app.ingestion.models import IngestionError
from app.ingestion.runtime import AnalysisRegistry
from app.ingestion.settings import Settings


def create_app(settings=None, registry=None, client_factory=None):
    settings = settings if settings is not None else Settings.from_env()
    registry = registry if registry is not None else AnalysisRegistry(settings)
    client_factory = client_factory if client_factory is not None else GitHubClient
    application = FastAPI(title="CodeScope AI", debug=False)
    application.add_exception_handler(IngestionError, ingestion_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.add_middleware(AnalysisBoundary, settings=settings)
    application.include_router(create_router(settings, registry, client_factory))
    return application


app = create_app()
