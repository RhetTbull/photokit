"""Test Asset class."""

import datetime
import pathlib

import osxphotos
import pytest
from osxphotos.datetime_utils import datetime_remove_tz

import photokit

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()

# test_video.MOV
VIDEO_DURATION = 10.341667


@pytest.fixture(scope="module")
def library():
    return photokit.PhotoLibrary()


@pytest.fixture(scope="module")
def asset(library: photokit.PhotoLibrary, asset_photo: str) -> photokit.PhotoAsset:
    asset = library.add_photo(asset_photo)
    yield asset
    library.delete_assets([asset])


@pytest.fixture(scope="module")
def video_asset(
    library: photokit.PhotoLibrary, asset_video: str
) -> photokit.PhotoAsset:
    asset = library.add_video(asset_video)
    yield asset
    library.delete_assets([asset])


@pytest.fixture(scope="module")
def raw_asset(
    library: photokit.PhotoLibrary, asset_raw_photo: tuple[str, str]
) -> photokit.PhotoAsset:
    asset = library.add_raw_pair_photo(*asset_raw_photo)
    yield asset
    library.delete_assets([asset])


@pytest.fixture(scope="module")
def live_asset(
    library: photokit.PhotoLibrary, asset_live_photo: tuple[str, str]
) -> photokit.PhotoAsset:
    asset = library.add_live_photo(*asset_live_photo)
    yield asset
    library.delete_assets([asset])


@pytest.fixture(scope="module")
def expected(asset) -> osxphotos.PhotoInfo:
    return osxphotos.PhotosDB(SYSTEM_LIBRARY_PATH).get_photo(asset.uuid)


@pytest.fixture(scope="module")
def expected_raw(raw_asset) -> osxphotos.PhotoInfo:
    return osxphotos.PhotosDB(SYSTEM_LIBRARY_PATH).get_photo(raw_asset.uuid)


def test_asset_keywords(asset: photokit.PhotoAsset):
    """Test Asset.keywords"""
    keywords = ["Test", "PhotoKit"]
    asset.keywords = keywords
    assert asset.keywords == keywords


def test_asset_isphoto_true(asset: photokit.PhotoAsset):
    """Test asset.isphoto"""
    assert asset.isphoto


def test_asset_ismovie_false(asset: photokit.PhotoAsset):
    """Test asset.ismovie"""
    assert not asset.ismovie


def test_asset_isphoto_false(video_asset: photokit.PhotoAsset):
    """Test asset.isphoto"""
    assert not video_asset.isphoto


def test_asset_ismovie_true(video_asset: photokit.PhotoAsset):
    """Test asset.ismovie"""
    assert video_asset.ismovie


def test_asset_isaudio(asset: photokit.PhotoAsset):
    """Test asset.isaudio"""
    assert not asset.isaudio


def test_asset_original_filename(
    asset: photokit.PhotoAsset, expected: osxphotos.PhotoInfo
):
    """Test asset.original_filename"""
    assert asset.original_filename == expected.original_filename


def test_asset_raw_filename(
    raw_asset: photokit.PhotoAsset, asset_raw_photo: tuple[str, str]
):
    """Test asset.raw_filename"""
    assert (
        raw_asset.raw_filename.lower() == pathlib.Path(asset_raw_photo[0]).name.lower()
    )


def test_asset_hasadjustments(
    asset: photokit.PhotoAsset, expected: osxphotos.PhotoInfo
):
    """Test asset.original_filename"""
    assert asset.hasadjustments == expected.hasadjustments


def test_asset_media_type(asset: photokit.PhotoAsset):
    """Test asset.media_type"""
    assert asset.media_type == 1


def test_asset_media_subtypes(asset: photokit.PhotoAsset):
    """Test asset.media_subtypes"""
    assert asset.media_subtypes == 0


def test_asset_panorama(asset: photokit.PhotoAsset):
    """Test asset.panorama"""
    assert not asset.panorama


def test_asset_hdr(asset: photokit.PhotoAsset):
    """Test asset.hdr"""
    assert not asset.hdr


def test_asset_screenshot(asset: photokit.PhotoAsset):
    """Test asset.screenshot"""
    assert not asset.screenshot


def test_asset_live_false(asset: photokit.PhotoAsset):
    """Test asset.live"""
    assert not asset.live


def test_asset_live_true(live_asset: photokit.PhotoAsset):
    """Test asset.live"""
    assert live_asset.live


def test_asset_streamed(asset: photokit.PhotoAsset):
    """Test asset.streamed"""
    assert not asset.streamed


def test_asset_slow_mo(asset: photokit.PhotoAsset):
    """Test asset.slow_mo"""
    assert not asset.slow_mo


def test_asset_time_lapse(asset: photokit.PhotoAsset):
    """Test asset.time_lapse"""
    assert not asset.time_lapse


def test_asset_portrait(asset: photokit.PhotoAsset):
    """Test asset.portrait"""
    assert not asset.portrait


def test_asset_burst(asset: photokit.PhotoAsset):
    """Test asset.burst"""
    assert not asset.burst


def test_asset_source_type(asset: photokit.PhotoAsset):
    """Test asset.source_type"""
    assert asset.source_type == 1


def test_asset_pixel_width_height(asset: photokit.PhotoAsset):
    """Test asset.pixel_width, asset.pixel_height"""
    assert asset.pixel_width == 3024
    assert asset.pixel_height == 4032


def test_asset_date(asset: photokit.PhotoAsset, expected: osxphotos.PhotoInfo):
    """Test asset.date getter and setter"""
    assert asset.date == datetime_remove_tz(expected.date)
    asset.date = datetime.datetime(2021, 1, 1, 0, 0, 0)
    assert asset.date == datetime.datetime(2021, 1, 1, 0, 0, 0)


def test_asset_date_modified(asset: photokit.PhotoAsset):
    """Test asset.date_modified getter and setter"""
    assert isinstance(asset.date_modified, datetime.datetime)
    asset.date_modified = datetime.datetime(2021, 1, 1, 0, 0, 0)
    assert asset.date_modified == datetime.datetime(2021, 1, 1, 0, 0, 0)


def test_asset_date_added(asset: photokit.PhotoAsset):
    """Test asset.date_added getter and setter"""
    assert isinstance(asset.date_added, datetime.datetime)
    asset.date_added = datetime.datetime(2021, 1, 1, 0, 0, 0)
    assert asset.date_added == datetime.datetime(2021, 1, 1, 0, 0, 0)


def test_timezone_offset(asset: photokit.PhotoAsset):
    """Test timezone setter/getter"""
    assert isinstance(asset.timezone_offset, int)
    asset.timezone_offset = 0
    assert asset.timezone_offset == 0


def test_timezone(asset: photokit.PhotoAsset):
    """Test timezone setter/getter"""
    assert isinstance(asset.timezone, str)
    asset.timezone = "America/Chicago"
    assert asset.timezone == "America/Chicago"


def test_timezone_bad_value(asset: photokit.PhotoAsset):
    """Test timezone setter with invalid value"""
    with pytest.raises(ValueError):
        asset.timezone = "Foo/Bar"


def test_asset_location(asset: photokit.PhotoAsset, expected: osxphotos.PhotoInfo):
    """Test asset.location setter & getter"""
    assert asset.location == expected.location
    asset.location = (-33.0, -117.0)
    assert asset.location == (-33.0, -117.0)


def test_asset_location_none(asset: photokit.PhotoAsset):
    """Test asset location can be set to None"""
    asset.location = None
    assert asset.location is None


def test_asset_duration_photo(asset: photokit.PhotoAsset):
    """Test asset.duration"""
    assert asset.duration == 0.0


def test_asset_duration_video(video_asset: photokit.PhotoAsset):
    """Test asset.duration"""
    assert video_asset.duration == pytest.approx(VIDEO_DURATION)


def test_asset_favorite(asset: photokit.PhotoAsset):
    """Test asset.favorite getter & setter"""
    asset.favorite = False
    assert not asset.favorite
    asset.favorite = True
    assert asset.favorite
