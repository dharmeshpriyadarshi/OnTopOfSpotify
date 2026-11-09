
import jwt

from datetime import datetime, timedelta, timezone
from uuid import UUID

from core.config import settings
from core.exceptions import APIException
from core.logger import logger


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
MINIMUM_SECRET_LENGTH = 32


def create_access_token(data: dict) -> str:
    """
    Generate a cryptographically signed JWT for internal CMS sessions.
    """

    secret_key = settings.JWT_SECRET_KEY

    if not isinstance(secret_key, str) or len(secret_key.encode("utf-8")) < MINIMUM_SECRET_LENGTH:
        logger.error("JWT generation failed: signing secret is missing or insufficient.")
        raise APIException(
            "Internal security configuration failure.",
            status_code=500,
        )

    if not isinstance(data, dict) or not data.get("sub"):
        raise APIException(
            "Invalid session identity supplied for JWT generation.",
            status_code=500,
        )

    try:
        payload = data.copy()
        now = datetime.now(timezone.utc)

        payload.update({
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        })

        return jwt.encode(
            payload,
            secret_key,
            algorithm=ALGORITHM,
        )

    except Exception:
        logger.error("Failed to generate internal JWT.")
        raise APIException(
            "Internal security failure during session creation.",
            status_code=500,
        ) from None


def verify_access_token(token: str) -> UUID:
    """
    Verify an internal JWT and return its PostgreSQL user UUID.
    """

    secret_key = settings.JWT_SECRET_KEY

    if not isinstance(secret_key, str) or len(secret_key.encode("utf-8")) < MINIMUM_SECRET_LENGTH:
        logger.error("JWT verification failed: signing secret is missing or insufficient.")
        raise APIException(
            "Internal security configuration failure.",
            status_code=500,
        )

    if not isinstance(token, str) or not token:
        raise APIException(
            "Invalid authentication credentials.",
            status_code=401,
        )

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )

    except jwt.ExpiredSignatureError:
        logger.warning("Rejected expired internal JWT.")
        raise APIException(
            "Session expired. Please log in again.",
            status_code=401,
        ) from None

    except jwt.InvalidTokenError:
        logger.warning("Rejected invalid internal JWT.")
        raise APIException(
            "Invalid authentication credentials.",
            status_code=401,
        ) from None

    user_id = payload.get("sub")

    try:
        return UUID(user_id)
    except (ValueError, TypeError, AttributeError):
        logger.warning("Rejected internal JWT with invalid subject.")
        raise APIException(
            "Invalid authentication credentials.",
            status_code=401,
        ) from None
