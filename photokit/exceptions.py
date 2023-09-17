"""Exceptions for photokit"""


class PhotoKitError(Exception):
    """Base class for exceptions in this module."""

    pass


class PhotoKitFetchFailed(PhotoKitError):
    """Exception raised for errors in the input."""

    pass


class PhotoKitAuthError(PhotoKitError):
    """Exception raised if unable to authorize use of PhotoKit."""

    pass


class PhotoKitExportError(PhotoKitError):
    """Exception raised if unable to export asset."""

    pass


class PhotoKitImportError(PhotoKitError):
    """Exception raised if unable to import asset."""

    pass


class PhotoKitMediaTypeError(PhotoKitError):
    """Exception raised if an unknown mediaType() is encountered"""

    pass


class PhotoKitCreateLibraryError(PhotoKitError):
    """Exception raised if unable to create a PhotoLibrary object"""

    pass


class PhotoKitAlbumCreateError(PhotoKitError):
    """Exception raised if unable to create an Album object"""

    pass


class PhotoKitAlbumDeleteError(PhotoKitError):
    """Exception raised if unable to create an Album object"""

    pass


class PhotoKitAlbumAddAssetError(PhotoKitError):
    """Exception raised if unable to add asset to album"""

    pass
