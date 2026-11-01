"""Bounded HTTP boundary; synchronous analyses use the framework's request pool."""

import hmac
from uuid import UUID

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from app.ingestion.models import AnalysisError, AnalysisRequest, IngestionError
from app.ingestion.pipeline import run_analysis
from app.ingestion.urls import parse_pr_url


def http_status(code):
    """HTTP policy is intentionally independent of ingestion/CLI error statuses."""
    if code in {
        "invalid_pr_url",
        "validation_error",
        "unsafe_repository_path",
        "unsupported_repository_entry",
    }:
        return 422
    if code in {
        "repository_not_allowed",
        "unsupported_repository",
        "unsupported_private_repository",
    }:
        return 403
    if code in {"analysis_not_found", "github_not_found"}:
        return 404
    if code in {"analysis_busy", "analysis_id_conflict", "pr_changed"}:
        return 409
    if code in {"resource_limit", "result_limit_exceeded", "request_body_too_large"}:
        return 413
    return {
        "unauthorized": 401,
        "unsupported_media_type": 415,
        "github_rate_limited": 429,
        "live_analysis_disabled": 503,
        "analysis_timeout": 504,
    }.get(code, 502)


def error_response(code, message, retry_after_seconds=None):
    error = AnalysisError(code=code, message=message, retry_after_seconds=retry_after_seconds)
    return JSONResponse(
        {"error": error.model_dump()}, status_code=http_status(code), headers=retry_headers(error)
    )


def retry_headers(error):
    seconds = error.retry_after_seconds
    return {"Retry-After": str(seconds)} if seconds is not None else {}


class AnalysisBoundary:
    """Authorize before reading bodies; cap streamed bytes before JSON decoding.

    Buffer at most 8 KiB and replay a single bounded ASGI request message. Neither
    Content-Length nor the number of chunks is trusted as the size measurement.
    """

    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (
            scope["path"] == "/api/analyses" or scope["path"].startswith("/api/analyses/")
        ):
            return await self.app(scope, receive, send)
        if not self.settings.live_enabled:
            return await error_response(
                "live_analysis_disabled", "Live analysis is currently disabled."
            )(scope, receive, send)
        credentials = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        expected = b"Bearer " + self.settings.live_access_token.get_secret_value().encode("utf-8")
        if len(credentials) != 1 or not hmac.compare_digest(credentials[0], expected):
            return await error_response("unauthorized", "Authorization is required.")(
                scope, receive, send
            )
        if scope["method"] == "POST" and scope["path"] == "/api/analyses":
            types = [v.lower().strip() for k, v in scope["headers"] if k.lower() == b"content-type"]
            if len(types) != 1 or types[0] not in {
                b"application/json",
                b"application/json; charset=utf-8",
                b"application/json;charset=utf-8",
            }:
                return await error_response(
                    "unsupported_media_type", "Use application/json with UTF-8 encoding."
                )(scope, receive, send)
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > 8192:
                    return await error_response(
                        "request_body_too_large", "Request body exceeds 8 KiB."
                    )(scope, receive, send)
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            original_receive = receive
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()

            receive = replay
        await self.app(scope, receive, send)


def create_router(settings, registry, client_factory):
    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok"}

    @router.post("/api/analyses", status_code=201)
    def submit(request: AnalysisRequest):
        # Validate before reservation, so rejected input cannot consume status slots.
        parse_pr_url(request.pr_url, settings.allowed_repositories)
        result = run_analysis(request, registry, settings, client_factory=client_factory)
        return JSONResponse(
            jsonable_encoder(result),
            status_code=http_status(result.error.code) if result.error else 201,
            headers=retry_headers(result.error) if result.error else {},
        )

    @router.get("/api/analyses/{analysis_id}")
    def status(analysis_id: UUID):
        return registry.get(analysis_id)

    return router


async def ingestion_error_handler(request, error: IngestionError):
    return error_response(error.code, error.public_message, error.retry_after_seconds)


async def validation_error_handler(request, error):
    # Framework validation errors contain raw input, which must never be serialized.
    return error_response("validation_error", "Request does not match the analysis contract.")


async def http_error_handler(request, error):
    if error.status_code == 400:
        return await validation_error_handler(request, error)
    return JSONResponse(
        {
            "error": AnalysisError(
                code="http_error", message="Request cannot be served."
            ).model_dump()
        },
        status_code=error.status_code,
    )


async def unexpected_error_handler(request, error):
    return error_response("analysis_failed", "Analysis could not be completed.")
