"""Sumaat API: one FastAPI app, run on Lambda through Mangum (API Gateway REST event -> ASGI)."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from api.controllers import cashiers, menu, orders, restaurants
from api.errors import ApiError
from api.settings import get_settings


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def health() -> dict:
    return {"status": "ok"}


def create_app() -> FastAPI:
    s = get_settings()
    docs = s.enable_docs
    app = FastAPI(
        title="Sumaat API",
        version="0.1.0",
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    # CORS headers on real responses. Browser preflight (OPTIONS) is answered by API Gateway on AWS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.allowed_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(ApiError, _api_error)
    app.add_api_route("/health", health, methods=["GET"])
    app.include_router(restaurants.router)
    app.include_router(menu.router)
    app.include_router(cashiers.router)
    app.include_router(orders.router)
    return app


app = create_app()

# lifespan="off": no startup/shutdown events on Lambda.
handler = Mangum(app, lifespan="off")
