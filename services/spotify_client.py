import re
import base64
import secrets
import urllib.parse

import httpx

from core.config import settings
from core.logger import logger
from core.exceptions import APIException


class SpotifyOAuthClient:
    """
    Handles Spotify OAuth 2.0 authorization and server-side token exchange.
    """

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, redirect_uri: str):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = redirect_uri

        if not self.client_id or not self.client_secret:
            logger.error(
                "Spotify OAuth initialization failed: credentials missing."
            )
            raise APIException(
                "Spotify integration is misconfigured on the server.",
                status_code=500,
            )

    @staticmethod
    def generate_state(length: int = 32) -> str:
        """Generate a cryptographically secure OAuth state value."""

        if length < 16:
            raise ValueError(
                "State entropy length must be at least 16 bytes."
            )

        return secrets.token_urlsafe(length)

    def get_authorization_url(
        self,
        scopes: list[str],
    ) -> tuple[str, str]:
        """Construct Spotify's authorization URL."""

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

        except Exception:
            logger.exception(
                "Failed to generate Spotify authorization URL."
            )
            raise APIException(
                "Failed to initiate Spotify authentication.",
                status_code=500,
            ) from None

    async def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange an authorization code for Spotify tokens.
        Credentials and tokens remain server-side.
        """

        auth_string = f"{self.client_id}:{self.client_secret}"

        encoded_credentials = base64.b64encode(
            auth_string.encode("utf-8")
        ).decode("ascii")

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        "Spotify token exchange rejected. HTTP status: %s",
                        response.status_code,
                    )
                    raise APIException(
                        "Failed to exchange authorization code with Spotify.",
                        status_code=400,
                    )

                token_data = response.json()

                if not isinstance(token_data, dict):
                    raise APIException(
                        "Spotify returned an invalid token response.",
                        status_code=502,
                    )

                if not token_data.get("access_token"):
                    raise APIException(
                        "Spotify token response did not contain an access token.",
                        status_code=502,
                    )

                return token_data

        except APIException:
            raise

        except httpx.TimeoutException:
            logger.warning("Spotify token exchange timed out.")
            raise APIException(
                "Spotify authentication service timed out.",
                status_code=504,
            ) from None

        except httpx.HTTPError as exc:
            logger.error(
                "Spotify token exchange network failure: %s",
                type(exc).__name__,
            )
            raise APIException(
                "Unable to communicate with Spotify authentication service.",
                status_code=502,
            ) from None

        except ValueError:
            logger.error(
                "Spotify returned an invalid JSON token response."
            )
            raise APIException(
                "Spotify returned an invalid authentication response.",
                status_code=502,
            ) from None

        except Exception:
            logger.exception(
                "Unexpected failure during Spotify token exchange."
            )
            raise APIException(
                "Internal failure during authentication.",
                status_code=500,
            ) from None

    
    async def get_client_credentials_token(self) -> str:
        """
        Obtain an application-level Spotify access token
        using the Client Credentials grant.
        """

        auth_string = f"{self.client_id}:{self.client_secret}"

        encoded_credentials = base64.b64encode(
            auth_string.encode("utf-8")
        ).decode("ascii")

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "client_credentials",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        "Spotify Client Credentials request failed. "
                        "HTTP status: %s",
                        response.status_code,
                    )
                    raise APIException(
                        "Unable to obtain Spotify application token.",
                        status_code=502,
                    )

                token_data = response.json()

                if (
                    not isinstance(token_data, dict)
                    or not isinstance(token_data.get("access_token"), str)
                    or not token_data["access_token"]
                ):
                    raise APIException(
                        "Spotify returned an invalid application token.",
                        status_code=502,
                    )

                return token_data["access_token"]

        except APIException:
            raise

        except httpx.TimeoutException:
            logger.warning(
                "Spotify Client Credentials request timed out."
            )
            raise APIException(
                "Spotify authentication service timed out.",
                status_code=504,
            ) from None

        except httpx.HTTPError as exc:
            logger.error(
                "Spotify Client Credentials network failure: %s",
                type(exc).__name__,
            )
            raise APIException(
                "Unable to communicate with Spotify authentication service.",
                status_code=502,
            ) from None

        except ValueError:
            logger.error(
                "Spotify returned invalid Client Credentials JSON."
            )
            raise APIException(
                "Spotify returned an invalid authentication response.",
                status_code=502,
            ) from None

        except Exception:
            logger.exception(
                "Unexpected Client Credentials authentication failure."
            )
            raise APIException(
                "Internal failure during Spotify authentication.",
                status_code=500,
            ) from None

    async def fetch_playlist_metadata(
        self,
        spotify_uri: str,
    ) -> dict:
        """
        Fetch public playlist metadata using an application token.
        """

        match = re.fullmatch(
            r"spotify:playlist:([a-zA-Z0-9]+)",
            spotify_uri,
        )

        if not match:
            raise APIException(
                "Invalid Spotify playlist URI.",
                status_code=400,
            )

        playlist_id = match.group(1)

        access_token = await self.get_client_credentials_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        params = {
            "fields": "name,description,external_urls.spotify",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"https://api.spotify.com/v1/playlists/{playlist_id}",
                    headers=headers,
                    params=params,
                )

                if response.status_code == 404:
                    raise APIException(
                        "Spotify playlist was not found.",
                        status_code=404,
                    )

                if response.status_code == 403:
                    raise APIException(
                        "Spotify denied access to this playlist.",
                        status_code=403,
                    )

                if response.status_code == 429:
                    logger.warning(
                        "Spotify playlist API rate limit reached."
                    )
                    raise APIException(
                        "Spotify is temporarily rate limiting requests.",
                        status_code=503,
                    )

                if response.status_code != 200:
                    logger.error(
                        "Spotify playlist metadata request failed. "
                        "HTTP status: %s",
                        response.status_code,
                    )
                    raise APIException(
                        "Unable to retrieve Spotify playlist metadata.",
                        status_code=502,
                    )

                playlist_data = response.json()

                if not isinstance(playlist_data, dict):
                    raise APIException(
                        "Spotify returned an invalid playlist response.",
                        status_code=502,
                    )

                external_urls = playlist_data.get("external_urls")

                if (
                    not isinstance(playlist_data.get("name"), str)
                    or not playlist_data["name"]
                    or not isinstance(external_urls, dict)
                    or not isinstance(external_urls.get("spotify"), str)
                ):
                    raise APIException(
                        "Spotify playlist metadata is incomplete.",
                        status_code=502,
                    )

                description = playlist_data.get("description")

                if description is not None and not isinstance(
                    description, str
                ):
                    raise APIException(
                        "Spotify returned invalid playlist metadata.",
                        status_code=502,
                    )

                return {
                    "name": playlist_data["name"],
                    "description": description,
                    "external_url": external_urls["spotify"],
                }

        except APIException:
            raise

        except httpx.TimeoutException:
            logger.warning(
                "Spotify playlist metadata request timed out."
            )
            raise APIException(
                "Spotify playlist service timed out.",
                status_code=504,
            ) from None

        except httpx.HTTPError as exc:
            logger.error(
                "Spotify playlist metadata network failure: %s",
                type(exc).__name__,
            )
            raise APIException(
                "Unable to communicate with Spotify playlist service.",
                status_code=502,
            ) from None

        except ValueError:
            logger.error(
                "Spotify returned invalid playlist JSON."
            )
            raise APIException(
                "Spotify returned an invalid playlist response.",
                status_code=502,
            ) from None

        except Exception:
            logger.exception(
                "Unexpected Spotify playlist metadata retrieval failure."
            )
            raise APIException(
                "Internal failure during playlist retrieval.",
                status_code=500,
            ) from None

    async def get_user_profile(self, access_token: str) -> dict:
        """
        Fetch the authenticated Spotify user's profile.
        """

        if not access_token:
            raise APIException(
                "Spotify access token is missing.",
                status_code=401,
            )

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.spotify.com/v1/me",
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        "Spotify profile request failed. HTTP status: %s",
                        response.status_code,
                    )
                    raise APIException(
                        "Failed to retrieve Spotify user profile.",
                        status_code=401 if response.status_code == 401 else 502,
                    )

                profile_data = response.json()

                if not isinstance(profile_data, dict):
                    raise APIException(
                        "Spotify returned an invalid profile response.",
                        status_code=502,
                    )

                if not profile_data.get("id"):
                    raise APIException(
                        "Spotify profile does not contain a user ID.",
                        status_code=502,
                    )

                return profile_data

        except APIException:
            raise

        except httpx.TimeoutException:
            logger.warning("Spotify profile request timed out.")
            raise APIException(
                "Spotify profile service timed out.",
                status_code=504,
            ) from None

        except httpx.HTTPError as exc:
            logger.error(
                "Spotify profile network failure: %s",
                type(exc).__name__,
            )
            raise APIException(
                "Unable to communicate with Spotify profile service.",
                status_code=502,
            ) from None

        except ValueError:
            logger.error("Spotify returned invalid profile JSON.")
            raise APIException(
                "Spotify returned an invalid profile response.",
                status_code=502,
            ) from None

        except Exception:
            logger.exception("Unexpected Spotify profile retrieval failure.")
            raise APIException(
                "Internal failure during profile retrieval.",
                status_code=500,
            ) from None
