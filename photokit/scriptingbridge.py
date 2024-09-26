"""Functions for interacting with Photos via the Scripting Bridge."""

from __future__ import annotations

from functools import cache

from ScriptingBridge import SBApplication, SBObject


class ScriptingBridgeError(Exception):
    """Base class for Scripting Bridge errors."""

    pass


@cache
def photos_app() -> SBApplication:
    """Return the Photos app instance.

    Raises:
        ScriptingBridgeError: If the Photos app bridge cannot be loaded.
    """
    try:
        return SBApplication.applicationWithBundleIdentifier_("com.apple.Photos")
    except Exception as e:
        raise ScriptingBridgeError(f"Error loading Photos app bridge: {e}")


def library_asset_by_uuid(uuid: str) -> SBObject:
    """Return the library asset with the given UUID.

    Args:
        uuid: The UUID of the asset.

    Returns: The library asset.

    Raises:
        ValueError: If the library asset cannot be found.
        ScriptingBridgeError: If an error occurs while getting the library asset.
    """
    photos = photos_app()
    if not photos.isRunning():
        photos.activate()

    try:
        asset = photos.mediaItems().objectWithID_(uuid)
    except Exception as e:
        raise ScriptingBridgeError(f"Error getting asset with UUID {uuid}: {e}")
    if not asset or not asset.id():
        # mediaItems().objectWithID_() can return a valid object with a nil ID if the ID is not found
        raise ValueError(f"No asset found with UUID {uuid}")
    return asset


def photo_set_description(uuid: str, descr: str | None):
    """Set the description of a photo with the given UUID.

    Args:
        uuid: The UUID of the photo.
        descr: The new description to set. If empty string or None, the description will be removed.
    """
    asset = library_asset_by_uuid(uuid)
    asset.setObjectDescription_(descr or "")
