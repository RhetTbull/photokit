"""Test Asset class."""

import pathlib

import osxphotos
import pytest

import photokit

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()


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
