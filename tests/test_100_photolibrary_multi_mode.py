"""Test PhotoLibrary class in multi library mode."""

from __future__ import annotations

import os
import pathlib
import time

import osxphotos
import pytest

import photokit
from photokit.exceptions import PhotoKitError, PhotoKitFetchFailed

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()


def test_photolibrary_multi_library_mode_enable_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property and enable_multi_library_mode() method."""
    assert not photokit.PhotoLibrary.multi_library_mode()
    photokit.PhotoLibrary.enable_multi_library_mode()
    assert photokit.PhotoLibrary.multi_library_mode()


def test_photolibrary_multi_library_mode_raises():
    """Test PhotoLibrary.__init__() raises error if called in single-library mode after multi-library mode."""
    photokit.PhotoLibrary.enable_multi_library_mode()
    with pytest.raises(PhotoKitError):
        library = photokit.PhotoLibrary()


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


def test_photolibrary_multi_library_mode_asset():
    """Test PhotoLibrary().asset() method."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    assets = library.assets()
    asset = library.asset(assets[0].uuid)
    assert asset.uuid == assets[0].uuid


def test_photolibrary_multi_library_mode_asset_raises():
    """Test PhotoLibrary().asset() method raises error if UUID invalid."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    with pytest.raises(PhotoKitFetchFailed):
        library.asset("12345")


def test_photolibrary_multi_library_mode_create_library(tmp_path: pathlib.Path):
    """Test PhotoLibrary.create_library() method."""
    tmp_library = tmp_path / f"Test_{time.perf_counter_ns()}.photoslibrary"
    library = photokit.PhotoLibrary.create_library(tmp_library)
    assert library.library_path() == str(tmp_library)


def test_photolibrary_multi_library_mode_create_library_raises(tmp_path: pathlib.Path):
    """Test PhotoLibrary.create_library() method raises error if library exists."""
    tmp_library = tmp_path / f"Test_{time.perf_counter_ns()}.photoslibrary"
    library = photokit.PhotoLibrary.create_library(tmp_library)
    assert library.library_path() == str(tmp_library)
    with pytest.raises(FileExistsError):
        library = photokit.PhotoLibrary.create_library(tmp_library)


def test_photolibrary_multi_library_mode_add_delete_photo(asset_photo: str):
    """Test PhotoLibrary().add_photo() and delete_assets() methods in multi library mode."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    asset = library.add_photo(asset_photo)
    assert asset.uuid
    assert asset.original_filename == os.path.basename(asset_photo)

    # delete the asset
    library.delete_assets([asset])
    time.sleep(1)

    # make sure it's gone
    with pytest.raises(PhotoKitFetchFailed):
        library.assets(uuids=[asset.uuid])


def test_photolibrary_multi_library_mode_add_photo_raises_file_not_found():
    """Test PhotoLibrary().add_photo() raises error if photo doesn't exist."""
    # add a photo to the library
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    with pytest.raises(FileNotFoundError):
        library.add_photo("/foo/bar/baz.jpg")


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


def test_photolibrary_multi_library_mode_album_uuid_1():
    """Test PhotoLibrary().album() method with uuid."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    albums = library.albums()
    album = library.album(albums[0].uuid)
    assert album.uuid == albums[0].uuid


def test_photolibrary_multi_library_mode_album_uuid_2():
    """Test PhotoLibrary().album() method with uuid."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    albums = library.albums()
    album = library.album(uuid=albums[0].uuid)
    assert album.uuid == albums[0].uuid


def test_photolibrary_multi_library_mode_album_title():
    """Test PhotoLibrary().album() method with title."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    albums = library.albums()
    album = library.album(title=albums[0].title)
    assert album.title == albums[0].title


def test_photolibrary_multi_library_mode_album_raises():
    """Test PhotoLibrary().album() method with invalid UUID."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    with pytest.raises(PhotoKitFetchFailed):
        library.album("12345")


def test_photolibrary_multi_library_mode_album_raises_no_args():
    """Test PhotoLibrary().album() method with invalid args."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    with pytest.raises(ValueError):
        library.album()


def test_photolibrary_multi_library_mode_album_raises_uuid_and_title():
    """Test PhotoLibrary().album() method with invalid args."""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    with pytest.raises(ValueError):
        library.album(uuid="12345", title="foo")


def test_photolibrary_multi_library_mode_album_create_delete(
    photosdb: osxphotos.PhotosDB,
):
    """Test create_album, delete_album"""
    library = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    album_title = f"test_album_{time.perf_counter_ns()}"
    album = library.create_album(album_title)
    assert album.title == album_title

    # delete the album
    album_uuid = album.uuid
    library.delete_album(album)

    # in multi-library mode, fetching the album UUID after delete doesn't raise an error
    # as expected but the UUID won't appear in the database so use osxphotos to check
    assert album_uuid not in [a.uuid for a in photosdb.album_info]
