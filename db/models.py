import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class User(Base):
    """Internal user representation mapped to a Spotify identity."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    spotify_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    playlists: Mapped[list["Playlist"]] = relationship(
        "Playlist", back_populates="owner", cascade="all, delete-orphan"
    )
    access_records: Mapped[list["PlaylistAccess"]] = relationship(
        "PlaylistAccess", back_populates="user", cascade="all, delete-orphan"
    )
    assets: Mapped[list["MultimediaAsset"]] = relationship(
        "MultimediaAsset", back_populates="creator", passive_deletes=True
    )


class Playlist(Base):
    """External Spotify Playlist URI mapped to an internal owner."""
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    spotify_uri: Mapped[str] = mapped_column(String, unique=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner: Mapped["User"] = relationship("User", back_populates="playlists")
    access_records: Mapped[list["PlaylistAccess"]] = relationship(
        "PlaylistAccess", back_populates="playlist", cascade="all, delete-orphan"
    )
    assets: Mapped[list["MultimediaAsset"]] = relationship(
        "MultimediaAsset", back_populates="playlist", cascade="all, delete-orphan"
    )


class PlaylistAccess(Base):
    """Role-Based Access Control junction table."""
    __tablename__ = "playlist_access"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    playlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String)

    playlist: Mapped["Playlist"] = relationship(
        "Playlist", back_populates="access_records"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="access_records"
    )

    __table_args__ = (
        UniqueConstraint(
            "playlist_id", "user_id", name="uix_playlist_user_access"
        ),
        CheckConstraint(
            "role IN ('viewer', 'editor', 'owner')",
            name="ck_playlist_access_role"
        ),
    )


class MultimediaAsset(Base):
    """Internal BLOB metadata mapped to a Spotify Playlist."""
    __tablename__ = "multimedia_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    playlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String)
    storage_url: Mapped[str] = mapped_column(String)
    metadata_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    playlist: Mapped["Playlist"] = relationship(
        "Playlist", back_populates="assets"
    )
    creator: Mapped["User | None"] = relationship(
        "User", back_populates="assets"
    )

    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('image', 'markdown')",
            name="ck_multimedia_asset_type"
        ),
    )
