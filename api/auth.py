
import secrets

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import APIException
from core.logger import logger
from core.security import create_access_token
from db.database import get_db
from db.models import User
from services.spotify_client import SpotifyOAuthClient


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

REDIRECT_URI = "http://127.0.0.1:8000/api/v1/auth/callback"

spotify_client = SpotifyOAuthClient(redirect_uri=REDIRECT_URI)


def clear_state_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key="spotify_auth_state",
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
        secure=False,
    )


def error_response(message: str, status_code: int) -> JSONResponse:
    response = JSONResponse(
        content={"error": True, "message": message},
        status_code=status_code,
    )
    clear_state_cookie(response)
    return response


@router.get("/login", summary="Initiate Spotify OAuth 2.0 Login")
def login():
    scopes = [
        "user-read-private",
        "user-read-email",
        "playlist-read-private",
        "playlist-modify-public",
    ]

    auth_url, state = spotify_client.get_authorization_url(scopes=scopes)

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="spotify_auth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/api/v1/auth",
    )

    return response


@router.get(
    "/callback",
    summary="Spotify OAuth Callback and Internal Session Initialization",
)
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    spotify_auth_state: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    # 1. Validate OAuth state before processing Spotify's response.
    if not state:
        return error_response("Missing OAuth state.", 400)

    if not spotify_auth_state:
        return error_response("OAuth session state is missing.", 401)

    if not secrets.compare_digest(state, spotify_auth_state):
        logger.warning("Spotify OAuth state validation failed.")
        return error_response("Invalid OAuth state.", 403)

    # 2. Handle authorization denial.
    if error:
        logger.warning("Spotify authorization was declined.")
        return error_response("Spotify authorization was declined.", 403)

    if not code:
        return error_response("Missing authorization code.", 400)

    try:
        # 3. Exchange authorization code for Spotify tokens.
        token_data = await spotify_client.exchange_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            raise APIException(
                "Spotify token exchange did not return an access token.",
                status_code=502,
            )

        # 4. Retrieve authenticated Spotify profile.
        profile_data = await spotify_client.get_user_profile(access_token)
        spotify_id = profile_data.get("id")

        if not isinstance(spotify_id, str) or not spotify_id.strip():
            raise APIException(
                "Spotify returned an invalid user identity.",
                status_code=502,
            )

        # 5. Find or register the internal user.
        user = (
            db.query(User)
            .filter(User.spotify_id == spotify_id)
            .first()
        )

        if user is None:
            user = User(spotify_id=spotify_id)
            db.add(user)

            try:
                db.commit()
                db.refresh(user)
                logger.info("Registered a new internal CMS user.")

            except IntegrityError:
                db.rollback()

                # Another concurrent request may have registered this ID.
                user = (
                    db.query(User)
                    .filter(User.spotify_id == spotify_id)
                    .first()
                )

                if user is None:
                    raise APIException(
                        "Unable to register the internal user.",
                        status_code=500,
                    )

        # 6. Generate an internal JWT using the internal UUID.
        jwt_token = create_access_token(
            data={"sub": str(user.id)}
        )

        # 7. Establish the internal CMS session.
        response = JSONResponse(
            content={
                "status": "success",
                "message": "Authentication complete. Internal session established.",
                "internal_user_id": str(user.id),
            }
        )

        clear_state_cookie(response)

        response.set_cookie(
            key="cms_access_token",
            value=jwt_token,
            max_age=86400,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )

        logger.info("Internal CMS session established.")

        return response

    except APIException as exc:
        logger.warning("Spotify authentication or session creation failed.")
        db.rollback()
        return error_response(
            "Authentication or session creation failed.",
            exc.status_code,
        )

    except Exception as exc:
        logger.error(
            "Unexpected authentication failure. Exception type: %s",
            type(exc).__name__,
        )
        db.rollback()
        return error_response(
            "An unexpected authentication error occurred.",
            500,
        )
