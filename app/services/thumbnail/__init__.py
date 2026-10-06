"""Thumbnail generation abstraction and implementations."""

from app.services.thumbnail.base import ThumbnailGenerator
from app.services.thumbnail.pil_thumbnail import PILThumbnailGenerator

__all__ = ["ThumbnailGenerator", "PILThumbnailGenerator"]
