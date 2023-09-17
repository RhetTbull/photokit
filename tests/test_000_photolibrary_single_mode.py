"""Test PhotoLibrary class in single library mode."""

from __future__ import annotations

import os
import pathlib
import time

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


def test_photolibrary_asset():
    """Test PhotoLibrary().asset() method with."""
    library = photokit.PhotoLibrary()
    assets = library.assets()
    asset = library.asset(assets[0].uuid)
    assert asset.uuid == assets[0].uuid


def test_photolibrary_asset_raises():
    """Test PhotoLibrary().asset() method raises error if UUID invalid."""
    library = photokit.PhotoLibrary()
    with pytest.raises(PhotoKitFetchFailed):
        library.asset("12345")


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
    time.sleep(1)

    # make sure it's gone
    with pytest.raises(PhotoKitFetchFailed):
        library.assets(uuids=[asset.uuid])


def test_photolibrary_add_photo_raises_file_not_found():
    """Test PhotoLibrary().add_photo() raises error if photo doesn't exist."""
    # add a photo to the library
    library = photokit.PhotoLibrary()
    with pytest.raises(FileNotFoundError):
        library.add_photo("/foo/bar/baz.jpg")


def test_photolibrary_albums(photosdb: osxphotos.PhotosDB):
    """Test PhotoLibrary().albums() method."""
    library = photokit.PhotoLibrary()
    albums = library.albums()
    assert len(albums) == len(photosdb.album_info)


def test_photolibrary_albums_top_level(photosdb: osxphotos.PhotosDB):
    """Test PhotoLibrary().albums(top_level=True) method."""
    library = photokit.PhotoLibrary()
    albums = library.albums(top_level=True)
    assert len(albums) == len([a for a in photosdb.album_info if a.parent == None])


def test_photolibrary_album_uuid_1():
    """Test PhotoLibrary().album() method with uuid."""
    library = photokit.PhotoLibrary()
    albums = library.albums()
    album = library.album(albums[0].uuid)
    assert album.uuid == albums[0].uuid


def test_photolibrary_album_uuid_2():
    """Test PhotoLibrary().album() method with uuid."""
    library = photokit.PhotoLibrary()
    albums = library.albums()
    album = library.album(uuid=albums[0].uuid)
    assert album.uuid == albums[0].uuid


def test_photolibrary_album_title():
    """Test PhotoLibrary().album() method with title."""
    library = photokit.PhotoLibrary()
    albums = library.albums()
    album = library.album(title=albums[0].title)
    assert album.title == albums[0].title


def test_photolibrary_album_raises():
    """Test PhotoLibrary().album() method with invalid UUID."""
    library = photokit.PhotoLibrary()
    with pytest.raises(PhotoKitFetchFailed):
        library.album("12345")


def test_photolibray_album_raises_no_args():
    """Test PhotoLibrary().album() method with invalid args."""
    library = photokit.PhotoLibrary()
    with pytest.raises(ValueError):
        library.album()


def test_photolibray_album_raises_uuid_and_title():
    """Test PhotoLibrary().album() method with invalid args."""
    library = photokit.PhotoLibrary()
    with pytest.raises(ValueError):
        library.album(uuid="12345", title="foo")


def test_photolibrary_album_create_delete():
    """Test create_album, delete_album"""
    library = photokit.PhotoLibrary()
    album_title = f"test_album_{time.perf_counter_ns()}"
    album = library.create_album(album_title)
    assert album.title == album_title

    # delete the album
    album_uuid = album.uuid
    library.delete_album(album)
    time.sleep(1)
    with pytest.raises(PhotoKitFetchFailed):
        library.album(album_uuid)
