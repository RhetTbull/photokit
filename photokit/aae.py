"""Handle AAE files which contain adjustment data"""

import logging
import os
import pathlib

import Foundation
import objc
import Photos

logger = logging.getLogger("photokit")

# Format identifier Photos uses for its own adjustments
APPLE_PHOTOS_FORMAT_IDENTIFIER = "com.apple.photo"

# Photos rejects edits submitted by another process that use its own format identifier
# (PHPhotosErrorDomain Code=3302) so adjustments read from an AAE file with
# APPLE_PHOTOS_FORMAT_IDENTIFIER are stored under this identifier instead.
# The adjustment data itself is preserved unchanged but Photos treats the edit as
# coming from another app so it cannot re-open Apple's adjustments in its editor.
PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER = "com.rhettbull.photokit.apple.photo"

# Format identifier used if the AAE file does not specify one
PHOTOKIT_FORMAT_IDENTIFIER = "com.rhettbull.photokit"


def adjustment_data_from_aae(
    aae_path: str | pathlib.Path | os.PathLike | None,
) -> Photos.PHAdjustmentData | None:
    """Parse an AAE file and create PHAdjustmentData.

    Args:
        aae_path: path to AAE file (plist containing adjustment data)

    Returns:
        PHAdjustmentData object or None if aae_path is None, file doesn't exist, or file cannot be parsed

    The AAE file is a plist with the following keys:
    - adjustmentFormatIdentifier: identifier for the adjustment format
    - adjustmentFormatVersion: version string for the format
    - adjustmentData: base64-encoded binary data
    - adjustmentEditorBundleID: bundle ID of the editor (e.g., com.apple.Photos)
    - adjustmentRenderTypes: integer bitmask of render types
    - adjustmentTimestamp: date of the adjustment
    - adjustmentBaseVersion: integer base version

    Note: If the format identifier is APPLE_PHOTOS_FORMAT_IDENTIFIER ("com.apple.photo"),
    it is replaced with PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER as Photos will not accept
    edits from another process using its own format identifier.
    """

    if not aae_path:
        return None

    aae_path = pathlib.Path(aae_path)
    if not aae_path.is_file():
        return None

    try:
        with objc.autorelease_pool():
            plist_data = Foundation.NSDictionary.dictionaryWithContentsOfFile_(
                str(aae_path)
            )
            if plist_data is None:
                logger.error(f"Could not read AAE file {aae_path}")
                return None

            format_version = plist_data.valueForKey_("adjustmentFormatVersion") or "1.0"
            format_identifier = (
                plist_data.valueForKey_("adjustmentFormatIdentifier")
                or PHOTOKIT_FORMAT_IDENTIFIER
            )
            if format_identifier == APPLE_PHOTOS_FORMAT_IDENTIFIER:
                format_identifier = PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
            ns_data = plist_data.valueForKey_(
                "adjustmentData"
            ) or Foundation.NSData.dataWithBytes_length_(b"", 0)
            render_types = plist_data.valueForKey_("adjustmentRenderTypes") or 0
            base_version = plist_data.valueForKey_("adjustmentBaseVersion")

            adjustment_data = Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
                format_identifier, format_version, ns_data
            )
            # adjustmentRenderTypes and baseVersion are private, undocumented properties
            adjustment_data.setAdjustmentRenderTypes_(render_types)
            if base_version is not None:
                adjustment_data.setBaseVersion_(base_version)

            return adjustment_data

    except Exception as e:
        # If we can't parse the AAE file, return None
        # The caller will create a minimal PHAdjustmentData
        logger.error(f"Failed to parse AAE file {aae_path}: {e}")
        return None


def create_minimal_adjustment_data() -> Photos.PHAdjustmentData:
    """Create a minimal PHAdjustmentData for when AAE file is not available.

    Returns:
        PHAdjustmentData with minimal data
    """
    format_identifier = "com.photokit.edit"
    format_version = "1.0"
    adjustment_data_content = b"edited"

    with objc.autorelease_pool():
        adjustment_data = Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
            format_identifier,
            format_version,
            Foundation.NSData.dataWithBytes_length_(
                adjustment_data_content, len(adjustment_data_content)
            ),
        )

        return adjustment_data
