
import uuid

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class AssetMetadata(BaseModel):
    """
    Strict validation for unstructured PostgreSQL JSONB metadata.
    """

    alt_text: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Accessibility text for images",
    )

    width: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image width in pixels",
    )

    height: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image height in pixels",
    )

    markdown_excerpt: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Brief snippet of markdown content",
    )


class MultimediaAssetBase(BaseModel):
    """
    Base payload contract for CMS assets.
    """

    asset_type: Literal["image", "markdown"] = Field(
        ...,
        description="Strictly restricted asset types",
    )

    metadata_payload: AssetMetadata = Field(
        default_factory=AssetMetadata,
    )


class MultimediaAssetResponse(MultimediaAssetBase):
    """
    Serialization schema for multimedia asset responses.
    """

    id: uuid.UUID
    playlist_id: uuid.UUID
    storage_url: str
    created_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlaylistResponse(BaseModel):
    """
    Serialization schema for playlists and associated assets.
    """

    id: uuid.UUID

    spotify_uri: str = Field(
        ...,
        pattern=r"^spotify:playlist:[a-zA-Z0-9]+$",
    )

    owner_id: uuid.UUID
    created_at: datetime

    assets: list[MultimediaAssetResponse] = Field(
        default_factory=list,
    )

    model_config = ConfigDict(from_attributes=True)


class AggregatedPlaylistResponse(BaseModel):
    """
    Unified payload merging external Spotify metadata
    with internal CMS multimedia assets.
    """

    spotify_uri: str = Field(
        ...,
        description="The requested Spotify URI"
    )

    spotify_name: str = Field(
        ...,
        description="Playlist name retrieved from Spotify"
    )

    spotify_description: Optional[str] = Field(
        default=None,
        description="Playlist description retrieved from Spotify"
    )

    spotify_external_url: str = Field(
        ...,
        description="Direct link to the Spotify playlist"
    )

    internal_cms_assets: list[MultimediaAssetResponse] = Field(
        default_factory=list,
        description="Multimedia assets stored in the internal CMS"
    )

    model_config = ConfigDict(from_attributes=True)
