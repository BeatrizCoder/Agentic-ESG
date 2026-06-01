"""Climate Sentinel — MongoDB persistence layer (Motor async driver)."""

import dataclasses
import logging
import os
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_MONGO_URL = os.getenv("MONGO_URL", "")

if _MONGO_URL:
    _client = AsyncIOMotorClient(_MONGO_URL)
    db = _client["climate_sentinel"]
    analyses = db["analyses"]
    logger.info("MongoDB connected via MONGO_URL")
else:
    logger.warning("MONGO_URL not set — database operations will be no-ops until configured")
    _client = None
    db = None
    analyses = None


def _result_to_doc(result, session_id: str | None = None) -> dict:
    """Convert an AnalysisResult dataclass (or dict) to a MongoDB-ready document."""
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        doc = dataclasses.asdict(result)
    elif isinstance(result, dict):
        doc = dict(result)
    else:
        raise TypeError(f"Cannot convert {type(result)} to MongoDB document")
    
    # Add session_id and expires_at if session_id is provided
    if session_id:
        doc["session_id"] = session_id
        # Set expiration to 24 hours from now
        doc["expires_at"] = datetime.utcnow() + timedelta(hours=24)
    
    return doc


async def save_analysis(result, session_id: str | None = None) -> str:
    """Persist an AnalysisResult and return its analysis_id."""
    if analyses is None:
        logger.warning("save_analysis: MONGO_URL not configured, skipping")
        return getattr(result, "analysis_id", "")

    doc = _result_to_doc(result, session_id)
    doc.pop("_id", None)

    existing = await analyses.find_one({"analysis_id": doc["analysis_id"]}, {"_id": 1})
    if existing:
        await analyses.replace_one({"analysis_id": doc["analysis_id"]}, doc)
    else:
        await analyses.insert_one(doc)

    logger.info("MongoDB saved analysis %s (risk_score=%s, session_id=%s)",
                doc["analysis_id"], doc.get("risk_score"), session_id or "none")
    return doc["analysis_id"]


async def get_analysis(analysis_id: str) -> dict | None:
    """Return a single analysis document by its analysis_id (not MongoDB _id)."""
    if analyses is None:
        return None
    doc = await analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return doc


async def get_recent_analyses(limit: int = 50) -> list[dict]:
    """Return the most recent analyses sorted by created_at descending."""
    if analyses is None:
        return []
    cursor = analyses.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def delete_analysis(analysis_id: str) -> bool:
    """Delete one analysis by analysis_id. Returns True if something was deleted."""
    if analyses is None:
        return False
    result = await analyses.delete_one({"analysis_id": analysis_id})
    return result.deleted_count > 0


async def get_session_history(session_id: str, limit: int = 10) -> list[dict]:
    """Return the most recent analyses for a given session_id."""
    if analyses is None:
        return []
    cursor = analyses.find(
        {"session_id": session_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def create_indexes() -> None:
    """Ensure performance indexes exist. Call once at startup."""
    if analyses is None:
        return
    await analyses.create_index("analysis_id", unique=True)
    await analyses.create_index([("created_at", -1)])
    await analyses.create_index("session_id")
    # TTL index: MongoDB will automatically delete documents when expires_at is reached
    await analyses.create_index("expires_at", expireAfterSeconds=0)
    logger.info("MongoDB indexes ensured (including TTL on expires_at)")
