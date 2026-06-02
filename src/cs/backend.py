"""Climate Sentinel FastAPI application entry point."""

import logging
import os

os.environ.setdefault("CREWAI_VERBOSE", "0")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import FileResponse

from .core.config import ALLOWED_ORIGINS, limiter
from .api.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Climate Sentinel",
    description="ESG climate risk analysis powered by NASA POWER + Claude AI.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True if ALLOWED_ORIGINS != ["*"] else False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-ID"],
    expose_headers=["Content-Disposition"],
)


app.include_router(router)


@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")


@app.on_event("startup")
async def _startup() -> None:
    from .db.mongo import create_indexes, _MONGO_URL
    db_label = "mongodb" if _MONGO_URL else "not connected (MONGO_URL missing)"
    logger.info("CS backend started | db=%s", db_label)
    await create_indexes()


def main() -> int:
    import uvicorn
    from .core.config import PORT
    uvicorn.run(
        "cs.backend:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
