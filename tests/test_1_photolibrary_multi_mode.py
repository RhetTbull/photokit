"""Test PhotoLibrary class in multi library mode."""

from __future__ import annotations

import os
import pathlib
import time

import osxphotos
import pytest

import photokit
from photokit.exceptions import PhotoKitFetchFailed

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()


def test_photolibrary_multi_library_mode_enable_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property and enable_multi_library_mode() method."""
    assert not photokit.PhotoLibrary.multi_library_mode()
    photokit.PhotoLibrary.enable_multi_library_mode()
    assert photokit.PhotoLibrary.multi_library_mode()


def test_photolibrary_multi_library_mode_library_path():
    """Test PhotoLibrary().library_path() method."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    assert library.library_path() == SYSTEM_LIBRARY_PATH


def test_photolibrary_multi_library_mode_assets(photo_count: tuple[int, int]):
    """Test PhotoLibrary().assets() method in multi library mode."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    assets = library.assets()
    assert len(assets) == sum(photo_count)


def test_photolibrary_multi_library_mode_assets_uuid(photosdb: osxphotos.PhotosDB):
    """Test PhotoLibrary().assets(uuids=) method in multi library mode."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
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


def test_photolibrary_multi_library_mode_create_library(tmp_path: pathlib.Path):
    """Test PhotoLibrary.create_library() method."""
    tmp_library = tmp_path / f"Test_{time.perf_counter_ns()}.photoslibrary"
    library = photokit.PhotoLibrary.create_library(tmp_library)
    assert library.library_path() == str(tmp_library)


def test_photolibrary_multi_library_mode_add_delete_photo(asset_photo: str):
    """Test PhotoLibrary().add_photo() and delete_assets() methods in multi library mode."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    asset = library.add_photo(asset_photo)
    assert asset.uuid
    assert asset.original_filename == os.path.basename(asset_photo)

    # delete the asset
    library.delete_assets([asset])

    # make sure it's gone
    with pytest.raises(PhotoKitFetchFailed):
        library.assets(uuids=[asset.uuid])


def test_photolibrary_multi_library_mode_albums(photosdb: osxphotos.PhotosDB):
    """Test PhotoLibrary().albums() method."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    albums = library.albums()
    assert len(albums) == len(photosdb.album_info)


def test_photolibrary_multi_library_mode_albums_top_level(photosdb: osxphotos.PhotosDB):
    """Test PhotoLibrary().albums(top_level=True) method."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    albums = library.albums(top_level=True)
    assert len(albums) == len([a for a in photosdb.album_info if a.parent == None])
