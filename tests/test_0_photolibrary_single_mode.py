"""Test PhotoLibrary class in single library mode."""

from __future__ import annotations

import osxphotos
import pytest
from osxphotos.utils import get_system_library_path

import photokit


@pytest.fixture(scope="module")
def photosdb() -> osxphotos.PhotosDB:
    """osxphotos PhotosDB instance"""
    photosdb = osxphotos.PhotosDB()
    yield photosdb


@pytest.fixture(scope="module")
def photo_count(pytestconfig) -> tuple[int, int]:
    """Ask user for number of photos in Photos library"""
    capmanager = pytestconfig.pluginmanager.getplugin("capturemanager")

    capmanager.suspend_global_capture(in_=True)
    photos = input(
        "\nEnter total number of photos Photos library (as shown in Library or Photos view): "
    )
    videos = input(
        "Enter total number of videos in Photos library (as shown in Libray or Photos view): "
    )
    capmanager.resume_global_capture()

    photos = int(photos.strip().replace(",", ""))
    videos = int(videos.strip().replace(",", ""))

    yield photos, videos


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


def test_photolibrary_assets(photo_count: tuple[int, int]):
    """Test PhotoLibrary().assets() method."""
    library = photokit.PhotoLibrary()
    assets = library.assets()
    assert len(assets) == sum(photo_count)


def test_photolibrary_len(photo_count: tuple[int, int]):
    """Test PhotoLibrary.__len__() method."""
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
