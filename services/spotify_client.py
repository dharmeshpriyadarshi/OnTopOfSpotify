
import secrets
import urllib.parse

from core.config import settings
from core.logger import logger
from core.exceptions import APIException


class SpotifyOAuthClient:
    """
    Handles Spotify OAuth 2.0 authorization URL generation
    and cryptographically secure state generation.
    """

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, redirect_uri: str):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = redirect_uri

        if not self.client_id:
            logger.error(
                "Spotify OAuth initialization failed: client ID is missing."
            )
            raise APIException(
                "Spotify integration is misconfigured on the server.",
                status_code=500,
            )

    @staticmethod
    def generate_state(length: int = 32) -> str:
        """Generate a cryptographically secure OAuth state value."""

        if length < 16:
            raise ValueError("State entropy length must be at least 16 bytes.")

        return secrets.token_urlsafe(length)

    def get_authorization_url(
        self,
        scopes: list[str],
    ) -> tuple[str, str]:
        """
        Construct the Spotify authorization URL.

        Returns:
            A tuple containing the authorization URL and state value.
        """

        try:
            state = self.generate_state()

            params = {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "state": state,
                "scope": " ".join(scopes),
                "show_dialog": "true",
            }

            query_string = urllib.parse.urlencode(params)
            authorization_url = (
                f"{self.AUTHORIZE_URL}?{query_string}"
            )

            return authorization_url, state

        except APIException:
            raise

        except Exception:
            logger.exception(
                "Failed to generate Spotify authorization URL."
            )
            raise APIException(
                "Failed to initiate Spotify authentication.",
                status_code=500,
            ) from None
