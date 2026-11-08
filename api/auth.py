
import secrets

from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse, RedirectResponse

from core.exceptions import APIException
from core.logger import logger
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



@router.get("/callback", summary="Handle Spotify OAuth Callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    spotify_auth_state: str | None = Cookie(default=None),
):
    def error_response(message: str, status_code: int):
        response = JSONResponse(
            content={"error": True, "message": message},
            status_code=status_code,
        )
        clear_state_cookie(response)
        return response

    # 1. Validate callback state.
    if not state:
        return error_response("Missing OAuth state.", 400)

    # 2. Ensure the state cookie exists.
    if not spotify_auth_state:
        return error_response("OAuth session state is missing.", 401)

    # 3. Compare states using constant-time comparison.
    if not secrets.compare_digest(state, spotify_auth_state):
        logger.warning("Spotify OAuth state validation failed.")
        return error_response("Invalid OAuth state.", 403)

    # 4. Handle Spotify authorization denial only after state validation.
    if error:
        logger.warning("Spotify authorization was declined.")
        return error_response("Spotify authorization was declined.", 403)

    # 5. Ensure the authorization code exists.
    if not code:
        return error_response("Missing authorization code.", 400)

    # 6. Exchange authorization code for tokens.
    try:
        await spotify_client.exchange_code_for_token(code)

        logger.info("Spotify authorization and token exchange completed.")

        response = JSONResponse(
            content={
                "status": "success",
                "message": "Spotify authorization completed successfully.",
            },
            status_code=200,
        )
        clear_state_cookie(response)
        return response

    except APIException as exc:
        logger.warning("Spotify token exchange failed.")
        return error_response(
            "Spotify token exchange failed.",
            exc.status_code,
        )

    except Exception as exc:
        logger.error(
            "Unexpected Spotify callback failure. Exception type: %s",
            type(exc).__name__,
        )
        return error_response(
            "An unexpected authentication error occurred.",
            500,
        )
