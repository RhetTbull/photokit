"""Config for pytest """

from __future__ import annotations

import os

import osxphotos
import pytest
from osxphotos.utils import get_system_library_path

from photokit import PhotoLibrarySmartAlbumType


@pytest.fixture(scope="session")
def photosdb() -> osxphotos.PhotosDB:
    """osxphotos PhotosDB instance"""
    photosdb = osxphotos.PhotosDB(get_system_library_path())
    yield photosdb


@pytest.fixture(scope="session")
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


# @pytest.fixture(scope="session")
# def smart_album_count(pytestconfig) -> dict[PhotoLibrarySmartAlbumType, int]:
#     """Ask user for number of photos in Photos library smart albums"""
#     capmanager = pytestconfig.pluginmanager.getplugin("capturemanager")

#     smart_albums = {}
#     capmanager.suspend_global_capture(in_=True)
#     for smart_album in PhotoLibrarySmartAlbumType:
#         count = input(
#             f"\nEnter total number of photos in smart album {smart_album.name}: "
#         )
#         smart_albums[smart_album] = int(count.strip().replace(",", ""))
#     capmanager.resume_global_capture()

#     return smart_albums


@pytest.fixture(scope="session")
def user_smart_album(pytestconfig) -> tuple[int, int]:
    """Ask user for number of photos in Photos library"""
    capmanager = pytestconfig.pluginmanager.getplugin("capturemanager")

    capmanager.suspend_global_capture(in_=True)
    smart_album = input(
        "\nEnter the name of a user smart album (or press Enter if no user smart albums): "
    )
    capmanager.resume_global_capture()

    smart_album = smart_album.strip()
    return smart_album


@pytest.fixture(scope="session")
def asset_photo() -> str:
    """Return path to photo asset for import tests"""
    cwd = os.getcwd()
    return os.path.join(cwd, "tests", "assets", "test_photo.JPG")


@pytest.fixture(scope="session")
def asset_video() -> str:
    """Retur path to video asset for import tests"""
    cwd = os.getcwd()
    return os.path.join(cwd, "tests", "assets", "test_video.MOV")


@pytest.fixture(scope="session")
def asset_live_photo() -> tuple[str, str]:
    """Return path to photo/video assets for live photo for import tests"""
    cwd = os.getcwd()
    return (
        os.path.join(cwd, "tests", "assets", "test_live.HEIC"),
        os.path.join(cwd, "tests", "assets", "test_live.mov"),
    )


@pytest.fixture(scope="session")
def asset_raw_photo() -> tuple[str, str]:
    """Return path to raw+jpeg assets for import tests"""
    cwd = os.getcwd()
    return (
        os.path.join(cwd, "tests", "assets", "test_raw.cr2"),
        os.path.join(cwd, "tests", "assets", "test_raw.JPG"),
    )
