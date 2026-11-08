
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from services.spotify_client import SpotifyOAuthClient


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

# Must exactly match the Spotify Developer Dashboard configuration.
REDIRECT_URI = "http://127.0.0.1:8000/api/v1/auth/callback"

spotify_client = SpotifyOAuthClient(redirect_uri=REDIRECT_URI)


@router.get("/login", summary="Initiate Spotify OAuth 2.0 Login")
def login():
    """Generate the Spotify authorization URL and set the CSRF state cookie."""

    scopes = [
        "user-read-private",
        "user-read-email",
        "playlist-read-private",
        "playlist-modify-public",
    ]

    auth_url, state = spotify_client.get_authorization_url(
        scopes=scopes
    )

    response = RedirectResponse(
        url=auth_url,
        status_code=302,
    )

    response.set_cookie(
        key="spotify_auth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=False,  # Local HTTP development only.
        path="/api/v1/auth",
    )

    return response
