"""Test Asset class."""

import pytest

import photokit


@pytest.fixture(scope="module")
def library():
    return photokit.PhotoLibrary()


@pytest.fixture(scope="module")
def asset(library: photokit.PhotoLibrary, asset_photo: str) -> photokit.PhotoAsset:
    asset = library.add_photo(asset_photo)
    yield asset
    library.delete_assets([asset])


def test_asset_keywords(library: photokit.PhotoLibrary, asset: photokit.PhotoAsset):
    """Test Asset.keywords"""
    keywords = ["Test", "PhotoKit"]
    asset.keywords = keywords
    assert asset.keywords == keywords
