"""Agentic ESG — MongoDB persistence layer (Motor async driver)."""

import dataclasses
import logging
import os
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_MONGO_URL = os.getenv("MONGO_URL", "")

if _MONGO_URL:
    _client = AsyncIOMotorClient(_MONGO_URL, maxPoolSize=10)
    db = _client["agentic_esg"]
    analyses = db["analyses"]
    logger.info("MongoDB connected via MONGO_URL")
else:
    logger.warning("MONGO_URL not set — database operations will be no-ops until configured")
    _client = None
    db = None
    analyses = None


def _result_to_doc(result, session_id: str | None = None, source: str = "single") -> dict:
    """Convert an AnalysisResult dataclass (or dict) to a MongoDB-ready document."""
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        doc = dataclasses.asdict(result)
    elif isinstance(result, dict):
        doc = dict(result)
    else:
        raise TypeError(f"Cannot convert {type(result)} to MongoDB document")

    doc["source"] = source
    if session_id:
        doc["session_id"] = session_id
        doc["expires_at"] = datetime.utcnow() + timedelta(days=30)

    return doc


async def save_analysis(result, session_id: str | None = None, source: str = "single") -> str:
    """Persist an AnalysisResult and return the MongoDB _id as string."""
    if analyses is None:
        logger.warning("save_analysis: MONGO_URL not configured, skipping")
        return getattr(result, "analysis_id", "")

    doc = _result_to_doc(result, session_id, source=source)
    doc.pop("_id", None)

    existing = await analyses.find_one({"analysis_id": doc["analysis_id"]}, {"_id": 1})
    if existing:
        await analyses.replace_one({"analysis_id": doc["analysis_id"]}, doc)
        mongo_id = str(existing["_id"])
    else:
        insert_result = await analyses.insert_one(doc)
        mongo_id = str(insert_result.inserted_id)

    logger.info("MongoDB saved analysis %s (mongo_id=%s, risk_score=%s, session_id=%s)",
                doc["analysis_id"], mongo_id, doc.get("risk_score"), session_id or "none")
    return mongo_id


async def get_analysis(analysis_id: str) -> dict | None:
    """Return a single analysis document by analysis_id field or MongoDB _id."""
    if analyses is None:
        return None
    # Try the analysis_id UUID field first
    doc = await analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if doc:
        return doc
    # Fall back to MongoDB ObjectId (history items expose the _id string)
    try:
        from bson import ObjectId
        doc = await analyses.find_one({"_id": ObjectId(analysis_id)}, {"_id": 0})
    except Exception:
        pass
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
    """Return the most recent analyses for a given session_id.

    Each item's analysis_id is set to the MongoDB _id string so the frontend
    can fetch the full document via GET /api/analyses/{id} using ObjectId lookup.
    """
    if analyses is None:
        return []
    cursor = analyses.find(
        {"session_id": session_id},
    ).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    for item in items:
        item["analysis_id"] = str(item.pop("_id"))
    return items


async def create_indexes() -> None:
    """Ensure performance indexes exist. Call once at startup."""
    if analyses is None:
        return
    try:
        # Drop existing TTL index if it exists (value may have changed)
        try:
            await analyses.drop_index("expires_at_1")
        except Exception:
            pass  # Index doesn't exist, that's fine

        await analyses.create_index(
            "expires_at",
            expireAfterSeconds=2592000,
            name="expires_at_1",
        )

        await analyses.create_index("analysis_id", unique=True)
        await analyses.create_index([("created_at", -1)])
        await analyses.create_index("session_id")
        logger.info("MongoDB indexes ensured (including TTL on expires_at)")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")
        # Don't crash on index errors — app still works
