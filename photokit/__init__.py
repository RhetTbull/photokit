"""Python package for accessing the macOS Photos.app library via Apple's native PhotoKit framework."""

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

__version__ = "0.1.3"

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
