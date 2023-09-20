"""Config for pytest """

from __future__ import annotations

import os

import osxphotos
import pytest
from osxphotos.utils import get_system_library_path


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


@pytest.fixture(scope="session")
def asset_photo() -> str:
    """Retur path to photo asset for import tests"""
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
