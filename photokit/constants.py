"""Constants for photokit."""

from __future__ import annotations

import Photos

# which version to export
PHImageRequestOptionsVersionOriginal = Photos.PHImageRequestOptionsVersionOriginal
PHImageRequestOptionsVersionUnadjusted = Photos.PHImageRequestOptionsVersionUnadjusted
PHImageRequestOptionsVersionCurrent = Photos.PHImageRequestOptionsVersionCurrent

# access level
PHAccessLevelAddOnly = Photos.PHAccessLevelAddOnly
PHAccessLevelReadWrite = Photos.PHAccessLevelReadWrite

# notification that gets sent to Notification Center
PHOTOKIT_NOTIFICATION_FINISHED_REQUEST = "PyPhotoKitNotificationFinishedRequest"

# minimum amount to sleep while waiting for export
MIN_SLEEP = 0.015
