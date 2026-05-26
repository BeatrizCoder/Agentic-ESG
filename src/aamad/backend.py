"""Entry point — creates the FastAPI app and wires everything together."""

import logging
import os

os.environ.setdefault("CREWAI_VERBOSE", "0")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response

from .core.config import limiter
from .core import services as _svc  # noqa: F401 — triggers singleton initialization
from .api.routes import router
from .config import DATABASE_URL

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AAMAD Support Backend",
    description="Backend API for the CrewAI multi-agent support interface.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def _add_cors_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    response = await call_next(request)

    response.headers["access-control-allow-origin"] = origin or "*"
    response.headers["access-control-allow-methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["access-control-allow-headers"] = "Content-Type, X-API-Key, Authorization"
    response.headers["access-control-expose-headers"] = "Content-Disposition"

    if request.method == "OPTIONS":
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        return Response(status_code=204, headers=headers)

    return response

app.include_router(router)


@app.on_event("startup")
async def _log_db_config() -> None:
    # STEP 3 — confirm which database the production backend is actually using
    db_type = "postgresql" if "postgresql" in DATABASE_URL else "sqlite"
    safe_url = DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL
    logger.info("DATABASE_URL type: %s", db_type)
    logger.info("DATABASE_URL: %s", safe_url)


def main(argv: list[str] | None = None) -> int:
    import uvicorn
    uvicorn.run(
        "aamad.backend:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
