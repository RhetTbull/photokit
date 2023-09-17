"""Album class for photokit"""

from __future__ import annotations

import datetime
import threading
from typing import TYPE_CHECKING

import objc
import Photos

from .exceptions import PhotoKitAlbumAddAssetError
from .objc_utils import NSDate_to_datetime

if TYPE_CHECKING:
    from .asset import Asset
    from .photolibrary import PhotoLibrary


class Album:
    """Represents a PHAssetCollection"""

    def __init__(
        self, library: PhotoLibrary, collection: Photos.PHAssetCollection
    ) -> None:
        """Initialize Album object with a PHAssetCollection"""
        self._library = library
        self._collection = collection

    @property
    def collection(self) -> Photos.PHAssetCollection:
        """Return the underlying PHAssetCollection"""
        return self._collection

    @property
    def local_identifier(self) -> str:
        """Return the local identifier of the underlying PHAssetCollection"""
        return self._collection.localIdentifier()

    @property
    def uuid(self) -> str:
        """ "Return the UUID of the underlying PHAssetCollection"""
        return self._collection.localIdentifier().split("/")[0]

    @property
    def title(self) -> str:
        """Return the localized title of the underlying PHAssetCollection"""
        return self._collection.localizedTitle()

    @property
    def estimated_count(self) -> int:
        """Return the estimated number of assets in the underlying PHAssetCollection"""
        return self._collection.estimatedAssetCount()

    @property
    def start_date(self) -> datetime.datetime | None:
        """Return the start date of the underlying PHAssetCollection as a naive datetime.datetime or None if no start date"""
        start_date = self._collection.startDate()
        return NSDate_to_datetime(start_date) if start_date else None

    @property
    def end_date(self) -> datetime.datetime | None:
        """Return the end date of the underlying PHAssetCollection as a naive datetime.datetime or None if no end date"""
        end_date = self._collection.endDate()
        return NSDate_to_datetime(end_date) if end_date else None

    @property
    def approximate_location(self) -> Photos.CLLocation:
        """Return the approximate location of the underlying PHAssetCollection"""
        return self._collection.approximateLocation()

    @property
    def location_names(self) -> list[str]:
        """Return the location names of the underlying PHAssetCollection"""
        return self._collection.localizedLocationNames()

    def assets(self) -> list[Photos.PHAsset]:
        """Return a list of PHAssets in the underlying PHAssetCollection"""
        assets = Photos.PHAsset.fetchAssetsInAssetCollection_options_(
            self._collection, None
        )
        asset_list = []
        for idx in range(assets.count()):
            asset_list.append(self._library._asset_factory(assets.objectAtIndex_(idx)))
        return asset_list

    def add_assets(self, assets: list[Asset]):
        """Add assets to the underlying album

        Args:
            assets: list of Asset objects to add to the album
        """

        with objc.autorelease_pool():
            event = threading.Event()

            def completion_handler(success, error):
                if error:
                    raise PhotoKitAlbumAddAssetError(
                        f"Error adding asset assets to album {self}: {error}"
                    )
                event.set()

            def album_add_assets_handler(assets):
                creation_request = Photos.PHAssetCollectionChangeRequest.changeRequestForAssetCollection_(
                    self.collection
                )
                phassets = [a.phasset for a in assets]
                creation_request.addAssets_(phassets)

            self._library._phphotolibrary.performChanges_completionHandler_(
                lambda: album_add_assets_handler(assets), completion_handler
            )

            event.wait()

    def remove_assets(self, assets: list[Asset]):
        """Remove assets from the underlying album

        Args:
            assets: list of Asset objects to remove from the album
        """

        with objc.autorelease_pool():
            event = threading.Event()

            def completion_handler(success, error):
                if error:
                    raise PhotoKitAlbumAddAssetError(
                        f"Error adding asset assets to album {self}: {error}"
                    )
                event.set()

            def album_remove_assets_handler(assets):
                creation_request = Photos.PHAssetCollectionChangeRequest.changeRequestForAssetCollection_(
                    self.collection
                )
                phassets = [a.phasset for a in assets]
                creation_request.removeAssets_(phassets)

            self._library._phphotolibrary.performChanges_completionHandler_(
                lambda: album_remove_assets_handler(assets), completion_handler
            )

            event.wait()

    def __repr__(self) -> str:
        """Return string representation of Album object"""
        return f"Album('{self._collection.localizedTitle()}')"

    def __str__(self) -> str:
        """Return string representation of Album object"""
        return f"Album('{self._collection.localizedTitle()}')"

    def __len__(self) -> int:
        """Return number of assets in the album"""
        return len(self.assets())
