"""Sumaat API: one FastAPI app, run on Lambda through Mangum (API Gateway REST event -> ASGI)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from api.errors import ApiError

app = FastAPI(title="Sumaat API", version="0.1.0")


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# lifespan="off": no startup/shutdown events on Lambda.
handler = Mangum(app, lifespan="off")
