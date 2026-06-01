"""CS runtime configuration: logging, CORS, rate-limiter, env vars."""

import logging
import os
import sys

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("crewai").setLevel(logging.WARNING)


setup_logging()
load_dotenv()

logger = logging.getLogger(__name__)

# ── Core secrets ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
MONGO_URL: str = os.environ.get("MONGO_URL", "")

# ── Server ────────────────────────────────────────────────────────────────────
PORT: int = int(os.environ.get("PORT", 8000))

# ── CORS ──────────────────────────────────────────────────────────────────────
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://localhost:8000",
]

_configured = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]
ALLOWED_ORIGINS = _configured + [
    o for o in DEFAULT_ALLOWED_ORIGINS if o not in _configured
]

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── NASA POWER ────────────────────────────────────────────────────────────────
NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_DEFAULT_START_YEAR = 2014
NASA_DEFAULT_END_YEAR = 2023
