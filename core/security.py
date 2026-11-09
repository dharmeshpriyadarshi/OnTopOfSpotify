
import jwt

from datetime import datetime, timedelta, timezone

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
        logger.error(
            "JWT generation failed: signing secret is missing or insufficient."
        )
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

        expiration = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload.update({
            "iat": datetime.now(timezone.utc),
            "exp": expiration,
        })

        encoded_token = jwt.encode(
            payload,
            secret_key,
            algorithm=ALGORITHM,
        )

        return encoded_token

    except Exception:
        logger.error("Failed to generate internal JWT.")
        raise APIException(
            "Internal security failure during session creation.",
            status_code=500,
        ) from None
