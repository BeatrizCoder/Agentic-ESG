"""JWT guest authentication helpers."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def create_guest_token() -> str:
    session_id = f"guest-{uuid.uuid4().hex[:12]}"
    payload = {
        "sub": session_id,
        "role": "guest",
        "name": "Demo User",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning("Invalid JWT: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def optional_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Optional[dict]:
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
