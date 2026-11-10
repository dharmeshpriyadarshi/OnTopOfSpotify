
import re
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from api.auth import spotify_client

from core.config import settings
from core.exceptions import APIException
from core.logger import logger
from db.database import SessionLocal
from db.models import User, Playlist, PlaylistAccess, MultimediaAsset
from api.dependencies import get_current_user
from api.schemas import (
    MultimediaAssetResponse,
    AggregatedPlaylistResponse,
)
from services.storage import LocalStorageManager, STORAGE_DIR


router = APIRouter(prefix="/api/v1/playlists", tags=["Playlists"])


def check_playlist_access(
    spotify_uri: str,
    user_id: UUID
) -> UUID:
    """Verify that a user owns or can edit a playlist."""

    db: Session = SessionLocal()

    try:
        playlist = (
            db.query(Playlist)
            .filter(Playlist.spotify_uri == spotify_uri)
            .first()
        )

        if not playlist:
            raise APIException(
                "The requested playlist is not registered in the CMS.",
                status_code=404
            )

        is_owner = playlist.owner_id == user_id

        if not is_owner:
            access_record = (
                db.query(PlaylistAccess)
                .filter(
                    PlaylistAccess.playlist_id == playlist.id,
                    PlaylistAccess.user_id == user_id,
                    PlaylistAccess.role.in_(["editor", "owner"])
                )
                .first()
            )

            if not access_record:
                logger.warning(
                    f"Unauthorized upload attempt by User {user_id} "
                    f"on Playlist {playlist.id}"
                )

                raise APIException(
                    "You do not have editor or owner privileges "
                    "for this playlist.",
                    status_code=403
                )

        return playlist.id

    finally:
        db.close()


def persist_asset_metadata(
    spotify_uri: str,
    user_id: UUID,
    asset_type: str,
    relative_url: str
) -> MultimediaAssetResponse:
    """Persist asset metadata and commit the transaction."""

    db: Session = SessionLocal()

    try:
        # Recheck playlist authorization before persistence.
        playlist = (
            db.query(Playlist)
            .filter(Playlist.spotify_uri == spotify_uri)
            .first()
        )

        if not playlist:
            raise APIException(
                "The requested playlist no longer exists.",
                status_code=404
            )

        is_owner = playlist.owner_id == user_id

        if not is_owner:
            access_record = (
                db.query(PlaylistAccess)
                .filter(
                    PlaylistAccess.playlist_id == playlist.id,
                    PlaylistAccess.user_id == user_id,
                    PlaylistAccess.role.in_(["editor", "owner"])
                )
                .first()
            )

            if not access_record:
                raise APIException(
                    "Your playlist editing permissions have changed.",
                    status_code=403
                )

        new_asset = MultimediaAsset(
            playlist_id=playlist.id,
            asset_type=asset_type,
            storage_url=relative_url,
            created_by=user_id,
            metadata_payload={}
        )

        db.add(new_asset)
        db.flush()

        # Construct the response before committing.
        response = MultimediaAssetResponse.model_validate(new_asset)

        # No database operations should follow a successful commit.
        db.commit()

        logger.info(
            f"Asset metadata committed successfully. "
            f"Asset ID: {new_asset.id}"
        )

        return response

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_playlist_assets(
    spotify_uri: str
) -> list[MultimediaAssetResponse]:
    """Retrieve CMS assets associated with a registered playlist."""

    db: Session = SessionLocal()

    try:
        playlist = (
            db.query(Playlist)
            .filter(Playlist.spotify_uri == spotify_uri)
            .first()
        )

        # A valid Spotify playlist may not yet exist in our CMS.
        if not playlist:
            return []

        assets = (
            db.query(MultimediaAsset)
            .filter(MultimediaAsset.playlist_id == playlist.id)
            .order_by(MultimediaAsset.created_at.asc())
            .all()
        )

        return [
            MultimediaAssetResponse.model_validate(asset)
            for asset in assets
        ]

    except SQLAlchemyError:
        logger.exception(
            "Database failure while retrieving playlist CMS assets."
        )
        raise APIException(
            "CMS database is temporarily unavailable.",
            status_code=503,
        ) from None

    finally:
        db.close()


def cleanup_uploaded_file(relative_url: str) -> None:
    """Safely remove an uploaded file after a failed database transaction."""

    try:
        filename = Path(relative_url).name

        if not filename or filename != relative_url.rstrip("/").split("/")[-1]:
            raise ValueError("Invalid storage filename.")

        storage_root = Path(STORAGE_DIR).resolve()
        physical_path = (storage_root / filename).resolve()

        if physical_path.parent != storage_root:
            raise ValueError("Storage path escaped the upload directory.")

        if physical_path.exists():
            physical_path.unlink()

            logger.warning(
                f"Orphaned file {filename} successfully removed."
            )

    except Exception:
        logger.exception(
            "Failed to clean up an uploaded file after database failure."
        )


@router.get(
    "/{spotify_uri}",
    response_model=AggregatedPlaylistResponse,
    summary="Retrieve Aggregated Playlist"
)
async def get_aggregated_playlist(spotify_uri: str):
    """
    Combine Spotify playlist metadata with internal CMS assets.

    This endpoint is public and does not require user authentication.
    """

    # 1. Validate the Spotify URI before making external requests.
    if not re.fullmatch(
        r"spotify:playlist:[a-zA-Z0-9]+",
        spotify_uri
    ):
        raise APIException(
            "Invalid Spotify playlist URI.",
            status_code=400
        )

    # 2. Retrieve external Spotify playlist metadata.
    spotify_data = await spotify_client.fetch_playlist_metadata(
        spotify_uri
    )

    # 3. Retrieve internal CMS assets from PostgreSQL.
    cms_assets = await run_in_threadpool(
        get_playlist_assets,
        spotify_uri
    )

    # 4. Combine both data sources into one response.
    return AggregatedPlaylistResponse(
        spotify_uri=spotify_uri,
        spotify_name=spotify_data["name"],
        spotify_description=spotify_data["description"],
        spotify_external_url=spotify_data["external_url"],
        internal_cms_assets=cms_assets,
    )


@router.post(
    "/{spotify_uri}/assets",
    response_model=MultimediaAssetResponse,
    summary="Upload Asset to Playlist"
)
async def upload_multimedia_asset(
    request: Request,
    spotify_uri: str,
    asset_type: Annotated[
        Literal["image", "markdown"],
        Form(...)
    ],
    file: Annotated[UploadFile, File(...)],
    current_user: User = Depends(get_current_user)
):
    """
    Upload an asset after verifying frontend origin, JWT authentication,
    and playlist editing permissions.
    """

    # 1. Validate browser request origin.
    origin = request.headers.get("origin")

    if origin != settings.FRONTEND_ORIGIN:
        raise APIException(
            "Request origin is not permitted.",
            status_code=403
        )

    # 2. Validate Spotify playlist URI.
    if not re.fullmatch(
        r"spotify:playlist:[a-zA-Z0-9]+",
        spotify_uri
    ):
        raise APIException(
            "Invalid Spotify playlist URI.",
            status_code=400
        )

    user_id = current_user.id

    # 3. Verify playlist authorization before storing the file.
    await run_in_threadpool(
        check_playlist_access,
        spotify_uri,
        user_id
    )

    relative_url = None

    try:
        # 4. Validate and store the physical file.
        relative_url = await LocalStorageManager.validate_and_save(
            file=file,
            asset_type=asset_type
        )

        # 5. Persist metadata in PostgreSQL.
        response = await run_in_threadpool(
            persist_asset_metadata,
            spotify_uri,
            user_id,
            asset_type,
            relative_url
        )

        return response

    except Exception as exc:

        # 6. Compensating cleanup if persistence or subsequent
        # endpoint processing fails.
        if relative_url is not None:
            cleanup_uploaded_file(relative_url)

        if isinstance(exc, APIException):
            raise

        logger.exception(
            "Asset upload failed during database persistence."
        )

        raise APIException(
            "Failed to upload asset. Database persistence was unsuccessful.",
            status_code=500
        ) from exc

    finally:
        await file.close()
