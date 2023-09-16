"""Test PhotoLibrary class in single library mode."""

from __future__ import annotations

import os

import osxphotos
import pytest
from osxphotos.utils import get_system_library_path

import photokit
from photokit.exceptions import PhotoKitFetchFailed


def test_get_photo_count(photo_count: tuple[int, int]):
    """Prompt to enter number of photos and videos"""
    # this is first just to prompt the user for the number of photos before running the rest of the tests
    assert True


def test_photolibrary_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property."""
    assert not photokit.PhotoLibrary.multi_library_mode()


def test_photolibrary_system_photo_library_path():
    """Test PhotoLibrary.system_photo_library_path() method."""
    library_path = get_system_library_path()
    assert photokit.PhotoLibrary.system_photo_library_path() == library_path


def test_photolibrary_authorization_status():
    """ "Tes PhotoLibrary.authorization_status() method; assumes authorization has been granted."""
    assert photokit.PhotoLibrary.authorization_status() == (True, True)


def test_photolibrary_library_path():
    """Test PhotoLibrary().library_path() method."""
    library = photokit.PhotoLibrary()
    assert library.library_path() == get_system_library_path()


def test_photolibrary_assets(photo_count: tuple[int, int]):
    """Test PhotoLibrary().assets() method."""
    library = photokit.PhotoLibrary()
    assets = library.assets()
    assert len(assets) == sum(photo_count)


def test_photolibrary_len(photo_count: tuple[int, int]):
    """Test PhotoLibrary().__len__() method."""
    library = photokit.PhotoLibrary()
    assert len(library) == sum(photo_count)


def test_photolibrary_assets_uuid(photosdb: osxphotos.PhotosDB):
    """Test that assets can be retrieved by UUID"""
    library = photokit.PhotoLibrary()
    # find photos user has interacted with (keywords, favorite, title, description)
    photos = [
        p
        for p in photosdb.photos()
        if p.keywords or p.favorite or p.title or p.description
    ]
    # remove hidden photos as PhotoKit doesn't return them
    photos = [p for p in photos if not p.hidden]
    photo_uuids = [p.uuid for p in photos]
    assets = library.assets(uuids=photo_uuids)
    assert len(assets) == len(photos)


def test_photolibrary_add_delete_photo(asset_photo: str):
    """Test PhotoLibrary().add_photo() and delete_assets() methods."""
    # add a photo to the library
    library = photokit.PhotoLibrary()
    asset = library.add_photo(asset_photo)
    assert asset.uuid
    assert asset.original_filename == os.path.basename(asset_photo)

    # delete the asset
    library.delete_assets([asset])

    # make sure it's gone
    with pytest.raises(PhotoKitFetchFailed):
        library.assets(uuids=[asset.uuid])
