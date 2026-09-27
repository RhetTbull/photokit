"""Test editing assets: PhotoAsset.edit(), PhotoAsset.revert(), and PhotoLibrary.add_*_with_adjustments()

These tests add assets to the Photos library and delete them when done.
"""

from __future__ import annotations

import pathlib
from typing import Generator

import Foundation
import Photos
import pytest

import photokit
from photokit.aae import PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER

ASSETS = pathlib.Path(__file__).parent / "assets"
EDIT_ASSETS = ASSETS / "edit"

PHOTO = EDIT_ASSETS / "IMG_4682.HEIC"
PHOTO_EDITED_JPEG = EDIT_ASSETS / "IMG_4682_edited.jpeg"
PHOTO_EDITED_HEIC = EDIT_ASSETS / "IMG_4682_edited.heic"
PHOTO_AAE = EDIT_ASSETS / "IMG_4682.AAE"

VIDEO = EDIT_ASSETS / "IMG_5474.mov"
VIDEO_AAE = EDIT_ASSETS / "IMG_5474.AAE"

LIVE_PHOTO = EDIT_ASSETS / "IMG_5492.HEIC"
LIVE_VIDEO = EDIT_ASSETS / "IMG_5492.mov"
LIVE_PHOTO_EDITED = EDIT_ASSETS / "IMG_5492_edited.heic"
LIVE_VIDEO_EDITED = EDIT_ASSETS / "IMG_5492_edited.mov"
LIVE_AAE = EDIT_ASSETS / "IMG_5492.AAE"

RAW = ASSETS / "test_raw.cr2"
RAW_JPEG = ASSETS / "test_raw.JPG"
RAW_EDITED = EDIT_ASSETS / "IMG_1994_edited.jpeg"
RAW_AAE = EDIT_ASSETS / "IMG_1994.AAE"

TEST_FORMAT_IDENTIFIER = "com.rhettbull.photokit.test"


@pytest.fixture(scope="module")
def library() -> photokit.PhotoLibrary:
    return photokit.PhotoLibrary()


@pytest.fixture(scope="module")
def created(library: photokit.PhotoLibrary) -> Generator[list, None, None]:
    """List of assets created by tests; deleted in a single operation when module completes"""
    assets = []
    yield assets
    if assets:
        library.delete_assets(assets)


def make_adjustment_data(
    data: bytes = b"test", format_identifier: str = TEST_FORMAT_IDENTIFIER
) -> Photos.PHAdjustmentData:
    return Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
        format_identifier, "1.0", Foundation.NSData.dataWithBytes_length_(data, len(data))
    )


def current_adjustment_data(
    asset: photokit.PhotoAsset,
) -> Photos.PHAdjustmentData | None:
    """Return asset's current adjustment data by starting then cancelling an edit"""
    captured = []

    def callback(path, adjustment_data):
        captured.append(adjustment_data)
        return None

    asset.edit(callback, can_handle_adjustment_data=True)
    return captured[0]


def resource_types(asset: photokit.PhotoAsset) -> set[int]:
    resources = Photos.PHAssetResource.assetResourcesForAsset_(asset.phasset)
    return {resources.objectAtIndex_(idx).type() for idx in range(resources.count())}


@pytest.mark.parametrize(
    "edited_path", [PHOTO_EDITED_JPEG, PHOTO_EDITED_HEIC], ids=["jpeg", "heic"]
)
def test_edit_photo_and_revert(
    library: photokit.PhotoLibrary, created: list, edited_path: pathlib.Path
):
    """Test PhotoAsset.edit() on a newly added photo then PhotoAsset.revert()"""
    photo = library.add_photo(PHOTO)
    created.append(photo)
    assert not photo.hasadjustments

    original_paths = []

    def callback(path, adjustment_data):
        original_paths.append(path)
        return (str(edited_path), make_adjustment_data())

    photo.edit(callback)
    assert pathlib.Path(original_paths[0]).is_file()
    assert photo.hasadjustments
    adjustment_data = current_adjustment_data(photo)
    assert adjustment_data.formatIdentifier() == TEST_FORMAT_IDENTIFIER
    assert bytes(adjustment_data.data()) == b"test"

    photo.revert()
    assert not photo.hasadjustments


def test_edit_cancel(library: photokit.PhotoLibrary, created: list):
    """Test PhotoAsset.edit() makes no changes if callback returns None"""
    photo = library.add_photo(PHOTO)
    created.append(photo)
    photo.edit(lambda path, adjustment_data: None)
    assert not photo.hasadjustments


def test_edit_video(library: photokit.PhotoLibrary, created: list):
    """Test PhotoAsset.edit() on a video"""
    video = library.add_video(VIDEO)
    created.append(video)
    video.edit(lambda path, adjustment_data: (str(VIDEO), make_adjustment_data()))
    assert video.hasadjustments
    assert current_adjustment_data(video).formatIdentifier() == TEST_FORMAT_IDENTIFIER


def test_edit_photo_with_video_raises(library: photokit.PhotoLibrary, created: list):
    """Test PhotoAsset.edit() raises ValueError if callback returns a video for a non-Live Photo"""
    photo = library.add_photo(PHOTO)
    created.append(photo)
    with pytest.raises(ValueError):
        photo.edit(
            lambda path, adjustment_data: (
                str(PHOTO_EDITED_JPEG),
                make_adjustment_data(),
                str(VIDEO),
            )
        )
    assert not photo.hasadjustments


def test_revert_unedited(library: photokit.PhotoLibrary, created: list):
    """Test PhotoAsset.revert() does nothing for an asset without edits"""
    photo = library.add_photo(PHOTO)
    created.append(photo)
    photo.revert()
    assert not photo.hasadjustments


def test_add_photo_with_adjustments(library: photokit.PhotoLibrary, created: list):
    """Test PhotoLibrary.add_photo_with_adjustments() with AAE file"""
    photo = library.add_photo_with_adjustments(PHOTO, PHOTO_EDITED_JPEG, PHOTO_AAE)
    created.append(photo)
    assert photo.hasadjustments
    adjustment_data = current_adjustment_data(photo)
    assert adjustment_data.formatIdentifier() == PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
    assert adjustment_data.formatVersion() == "1.5"


def test_add_photo_with_adjustments_no_aae(
    library: photokit.PhotoLibrary, created: list
):
    """Test PhotoLibrary.add_photo_with_adjustments() without AAE file"""
    photo = library.add_photo_with_adjustments(PHOTO, PHOTO_EDITED_HEIC)
    created.append(photo)
    assert photo.hasadjustments
    assert current_adjustment_data(photo).formatIdentifier() == "com.photokit.edit"


def test_add_video_with_adjustments(library: photokit.PhotoLibrary, created: list):
    """Test PhotoLibrary.add_video_with_adjustments() without edited video"""
    video = library.add_video_with_adjustments(VIDEO, aae_path=VIDEO_AAE)
    created.append(video)
    assert video.hasadjustments
    assert (
        current_adjustment_data(video).formatIdentifier()
        == PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
    )


def test_add_live_photo_with_adjustments(
    library: photokit.PhotoLibrary, created: list
):
    """Test PhotoLibrary.add_live_photo_with_adjustments() with edited photo and video"""
    live = library.add_live_photo_with_adjustments(
        LIVE_PHOTO, LIVE_VIDEO, LIVE_PHOTO_EDITED, LIVE_VIDEO_EDITED, LIVE_AAE
    )
    created.append(live)
    assert live.live
    assert live.hasadjustments
    assert Photos.PHAssetResourceTypeFullSizePairedVideo in resource_types(live)
    assert (
        current_adjustment_data(live).formatIdentifier()
        == PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
    )


def test_add_live_photo_with_adjustments_photo_only(
    library: photokit.PhotoLibrary, created: list
):
    """Test PhotoLibrary.add_live_photo_with_adjustments() with only edited photo"""
    live = library.add_live_photo_with_adjustments(
        LIVE_PHOTO, LIVE_VIDEO, LIVE_PHOTO_EDITED, aae_path=LIVE_AAE
    )
    created.append(live)
    assert live.live
    assert live.hasadjustments


def test_add_raw_pair_photo_with_adjustments(
    library: photokit.PhotoLibrary, created: list
):
    """Test PhotoLibrary.add_raw_pair_photo_with_adjustments()"""
    photo = library.add_raw_pair_photo_with_adjustments(
        RAW, RAW_JPEG, RAW_EDITED, RAW_AAE
    )
    created.append(photo)
    assert photo.hasadjustments
    assert (
        current_adjustment_data(photo).formatIdentifier()
        == PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
    )


@pytest.mark.parametrize(
    "method, args",
    [
        ("add_photo_with_adjustments", (PHOTO, EDIT_ASSETS / "missing.jpeg")),
        ("add_video_with_adjustments", (EDIT_ASSETS / "missing.mov",)),
        (
            "add_live_photo_with_adjustments",
            (LIVE_PHOTO, LIVE_VIDEO, LIVE_PHOTO_EDITED, EDIT_ASSETS / "missing.mov"),
        ),
        (
            "add_raw_pair_photo_with_adjustments",
            (RAW, RAW_JPEG, EDIT_ASSETS / "missing.jpeg"),
        ),
    ],
)
def test_add_with_adjustments_file_not_found(
    library: photokit.PhotoLibrary, method: str, args: tuple
):
    """Test add_*_with_adjustments() raise FileNotFoundError before adding anything"""
    with pytest.raises(FileNotFoundError):
        getattr(library, method)(*args)
