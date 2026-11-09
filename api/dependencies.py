
from fastapi import Request, Depends
from sqlalchemy.orm import Session

from core.security import verify_access_token
from core.exceptions import APIException
from core.logger import logger
from db.database import get_db
from db.models import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the internal JWT cookie and return the authenticated user.
    """

    token = request.cookies.get("cms_access_token")

    if not token:
        logger.warning(
            "Unauthorized access attempt to %s: missing session cookie.",
            request.url.path,
        )
        raise APIException(
            "Authentication credentials were not provided.",
            status_code=401,
        )

    user_id = verify_access_token(token)

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        logger.warning(
            "Token validated, but the associated internal user no longer exists."
        )
        raise APIException(
            "Authenticated user no longer exists.",
            status_code=401,
        )

    return user
