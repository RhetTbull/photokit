"""Python package for accessing the macOS Photos.app library via Apple's native PhotoKit framework."""

__version__ = "0.1.2"
import logging

from .album import Album
from .asset import LivePhotoAsset, PhotoAsset, VideoAsset
from .exceptions import (
    PhotoKitAlbumAddAssetError,
    PhotoKitAlbumCreateError,
    PhotoKitAlbumDeleteError,
    PhotoKitAuthError,
    PhotoKitCreateLibraryError,
    PhotoKitError,
    PhotoKitExportError,
    PhotoKitFetchFailed,
    PhotoKitImportError,
    PhotoKitMediaTypeError,
)
from .photolibrary import PhotoLibrary

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(lineno)d - %(message)s",
)

__all__ = [
    "Album",
    "LivePhotoAsset",
    "PhotoAsset",
    "PhotoKitAlbumAddAssetError",
    "PhotoKitAlbumCreateError",
    "PhotoKitAlbumDeleteError",
    "PhotoKitAuthError",
    "PhotoKitCreateLibraryError",
    "PhotoKitError",
    "PhotoKitExportError",
    "PhotoKitFetchFailed",
    "PhotoKitImportError",
    "PhotoKitMediaTypeError",
    "PhotoLibrary",
    "VideoAsset",
]
