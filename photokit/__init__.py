"""Python package for accessing the macOS Photos.app library via Apple's native PhotoKit framework."""

__version__ = "0.1.0"

from .photokit import (
    LivePhotoAsset,
    PhotoAsset,
    PhotoKitAuthError,
    PhotoKitCreateLibraryError,
    PhotoKitError,
    PhotoKitExportError,
    PhotoKitFetchFailed,
    PhotoKitImportError,
    PhotoKitMediaTypeError,
    PhotoLibrary,
    VideoAsset,
)

__all__ = [
    "PhotoLibrary",
    "PhotoKitError",
    "PhotoKitAuthError",
    "PhotoKitFetchFailed",
    "PhotoKitMediaTypeError",
    "PhotoKitExportError",
    "PhotoKitImportError",
    "PhotoKitCreateLibraryError",
    "PhotoAsset",
    "VideoAsset",
    "LivePhotoAsset",
]
