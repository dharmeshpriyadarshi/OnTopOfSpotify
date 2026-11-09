import asyncio
import codecs
import os
import uuid
import warnings
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image

from core.exceptions import APIException
from core.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "uploads"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class LocalStorageManager:
    """Validate and save uploaded image and Markdown assets."""

    MAX_FILE_SIZE_MB = 5
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    MAX_IMAGE_PIXELS = 25_000_000

    IMAGE_TYPES = {
        "image/jpeg": (".jpg", "jpeg"),
        "image/png": (".png", "png"),
        "image/webp": (".webp", "webp"),
    }

    MARKDOWN_TYPES = {
        "text/markdown",
        "text/plain",
    }

    @staticmethod
    def _detect_image_type(header: bytes) -> str | None:
        """Identify supported image formats using their file signatures."""

        if header.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"

        if (
            len(header) >= 12
            and header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        ):
            return "webp"

        return None

    @classmethod
    def _validate_image(cls, path: Path, expected_format: str) -> tuple[int, int]:
        """Verify image integrity and force pixel decoding."""

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)

                with Image.open(path) as image:
                    if image.format.lower() != expected_format:
                        raise ValueError("Image format does not match its signature.")

                    if getattr(image, "n_frames", 1) != 1:
                        raise ValueError("Animated images are not supported.")

                    width, height = image.size

                    if width < 1 or height < 1:
                        raise ValueError("Invalid image dimensions.")

                    if width * height > cls.MAX_IMAGE_PIXELS:
                        raise ValueError("Image exceeds the pixel limit.")

                    image.verify()

                # Reopen after verify() and force complete pixel decoding.
                with Image.open(path) as image:
                    image.load()

                    return width, height

        except Exception as exc:
            raise APIException(
                "Invalid, corrupted, animated, or unsupported image.",
                status_code=400,
            ) from exc

    @classmethod
    async def validate_and_save(
        cls,
        file: UploadFile,
        asset_type: str,
    ) -> str:
        """
        Validate an uploaded asset and save it under a server-generated name.

        Returns a relative URL reference for database storage.
        """

        if asset_type not in {"image", "markdown"}:
            raise APIException(
                "Unsupported asset type classification.",
                status_code=400,
            )

        content_type = (file.content_type or "").lower().strip()

        if asset_type == "image" and content_type not in cls.IMAGE_TYPES:
            raise APIException(
                "Unsupported image MIME type. Allowed: JPEG, PNG, WebP.",
                status_code=400,
            )

        if asset_type == "markdown" and content_type not in cls.MARKDOWN_TYPES:
            raise APIException(
                "Unsupported Markdown MIME type. Use text/markdown or text/plain.",
                status_code=400,
            )

        if file.size is not None and file.size > cls.MAX_FILE_SIZE_BYTES:
            raise APIException(
                f"File exceeds the {cls.MAX_FILE_SIZE_MB}MB limit.",
                status_code=413,
            )

        storage_name = uuid.uuid4().hex
        temporary_path = STORAGE_DIR / f".{storage_name}.part"
        total_size = 0
        first_chunk = True
        detected_image_type = None

        text_decoder = (
            codecs.getincrementaldecoder("utf-8")()
            if asset_type == "markdown"
            else None
        )

        try:
            await file.seek(0)

            async with aiofiles.open(temporary_path, "xb") as output:
                while True:
                    chunk = await file.read(cls.CHUNK_SIZE)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > cls.MAX_FILE_SIZE_BYTES:
                        raise APIException(
                            f"File exceeds the {cls.MAX_FILE_SIZE_MB}MB limit.",
                            status_code=413,
                        )

                    if first_chunk:
                        if asset_type == "image":
                            detected_image_type = cls._detect_image_type(chunk)
                            expected_type = cls.IMAGE_TYPES[content_type][1]

                            if detected_image_type != expected_type:
                                raise APIException(
                                    "Image content does not match its declared MIME type.",
                                    status_code=400,
                                )

                        first_chunk = False

                    if asset_type == "markdown":
                        try:
                            decoded_text = text_decoder.decode(chunk)
                        except UnicodeDecodeError as exc:
                            raise APIException(
                                "Markdown files must contain valid UTF-8 text.",
                                status_code=400,
                            ) from exc

                        if "\x00" in decoded_text:
                            raise APIException(
                                "Markdown files cannot contain null bytes.",
                                status_code=400,
                            )

                    await output.write(chunk)

                if total_size == 0:
                    raise APIException(
                        "Uploaded file is empty.",
                        status_code=400,
                    )

                if asset_type == "markdown":
                    try:
                        remaining_text = text_decoder.decode(b"", final=True)
                    except UnicodeDecodeError as exc:
                        raise APIException(
                            "Markdown files must contain valid UTF-8 text.",
                            status_code=400,
                        ) from exc

                    if "\x00" in remaining_text:
                        raise APIException(
                            "Markdown files cannot contain null bytes.",
                            status_code=400,
                        )

            if asset_type == "image":
                extension = cls.IMAGE_TYPES[content_type][0]
                await asyncio.to_thread(
                    cls._validate_image,
                    temporary_path,
                    detected_image_type,
                )
            else:
                extension = ".md"

            final_path = STORAGE_DIR / f"{storage_name}{extension}"

            # Hard-link publication fails if the destination already exists.
            # Both paths are in the same directory/filesystem.
            await asyncio.to_thread(os.link, temporary_path, final_path)

            logger.info(
                "Stored %s asset | Storage key: %s | Size: %d bytes",
                asset_type,
                final_path.name,
                total_size,
            )

            return f"/static/uploads/{final_path.name}"

        except APIException:
            raise

        except Exception as exc:
            logger.error(
                "Storage I/O failure while saving an asset.",
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise APIException(
                "Internal storage failure. Could not save the uploaded asset.",
                status_code=500,
            ) from exc

        finally:
            try:
                if temporary_path.exists():
                    await asyncio.to_thread(temporary_path.unlink)
            except OSError:
                logger.error(
                    "Could not remove temporary storage file: %s",
                    temporary_path.name,
                )
