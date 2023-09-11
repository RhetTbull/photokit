"""Album class for photokit"""

from __future__ import annotations

import datetime

import Photos


class Album:
    """Represents a PHAssetCollection"""

    def __init__(self, collection: Photos.PHAssetCollection) -> None:
        """Initialize Album object with a PHAssetCollection"""
        self._collection = collection

    @property
    def collection(self) -> Photos.PHAssetCollection:
        """Return the underlying PHAssetCollection"""
        return self._collection

    @property
    def identifier(self) -> str:
        """Return the local identifier of the underlying PHAssetCollection"""
        return self._collection.localIdentifier()

    @property
    def title(self) -> str:
        """Return the localized title of the underlying PHAssetCollection"""
        return self._collection.localizedTitle()

    @property
    def estimated_count(self) -> int:
        """Return the estimated number of assets in the underlying PHAssetCollection"""
        return self._collection.estimatedAssetCount()

    @property
    def start_date(self) -> datetime.datetime:
        """Return the start date of the underlying PHAssetCollection"""
        return self._collection.startDate()

    @property
    def end_date(self) -> datetime.datetime:
        """Return the end date of the underlying PHAssetCollection"""
        return self._collection.endDate()

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
            asset_list.append(assets.objectAtIndex_(idx))
        return asset_list

    def __repr__(self) -> str:
        """Return string representation of Album object"""
        return f"Album('{self._collection.localizedTitle()}')"

    def __str__(self) -> str:
        """Return string representation of Album object"""
        return f"Album('{self._collection.localizedTitle()}')"
