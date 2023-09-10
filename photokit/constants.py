"""Constants for photokit."""

from __future__ import annotations

import Photos

# which version to export, use either PHOTOS_VERSION_X or the longer PhotoKit name
PHOTOS_VERSION_ORIGINAL = (
    PHImageRequestOptionsVersionOriginal
) = Photos.PHImageRequestOptionsVersionOriginal
PHOTOS_VERSION_UNADJUSTED = (
    PHImageRequestOptionsVersionUnadjusted
) = Photos.PHImageRequestOptionsVersionUnadjusted
PHOTOS_VERSION_CURRENT = (
    PHImageRequestOptionsVersionCurrent
) = Photos.PHImageRequestOptionsVersionCurrent

ACCESS_LEVEL_ADD_ONLY = PHAccessLevelAddOnly = Photos.PHAccessLevelAddOnly
ACCESS_LEVEL_READ_WRITE = PHAccessLevelReadWrite = Photos.PHAccessLevelReadWrite

# notification that gets sent to Notification Center
PHOTOKIT_NOTIFICATION_FINISHED_REQUEST = "PyPhotoKitNotificationFinishedRequest"

# minimum amount to sleep while waiting for export
MIN_SLEEP = 0.015
