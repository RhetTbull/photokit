"""Test AAE file parsing (does not require access to the Photos library)"""

import pathlib
import plistlib

import pytest

from photokit.aae import (
    PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER,
    PHOTOKIT_FORMAT_IDENTIFIER,
    adjustment_data_from_aae,
    create_minimal_adjustment_data,
)

EDIT_ASSETS = pathlib.Path(__file__).parent / "assets" / "edit"
AAE_FILES = sorted(EDIT_ASSETS.glob("*.AAE"))


@pytest.mark.parametrize("aae_path", AAE_FILES, ids=lambda p: p.name)
def test_adjustment_data_from_aae(aae_path: pathlib.Path):
    """Test adjustment_data_from_aae preserves AAE data and renames Apple's format identifier"""
    with open(aae_path, "rb") as fp:
        aae = plistlib.load(fp)
    assert aae["adjustmentFormatIdentifier"] == "com.apple.photo"

    adjustment_data = adjustment_data_from_aae(aae_path)
    assert adjustment_data.formatIdentifier() == PHOTOKIT_APPLE_PHOTOS_FORMAT_IDENTIFIER
    assert adjustment_data.formatVersion() == aae["adjustmentFormatVersion"]
    assert bytes(adjustment_data.data()) == aae["adjustmentData"]
    assert adjustment_data.adjustmentRenderTypes() == aae["adjustmentRenderTypes"]
    assert adjustment_data.baseVersion() == aae["adjustmentBaseVersion"]


def test_adjustment_data_from_aae_defaults(tmp_path: pathlib.Path):
    """Test adjustment_data_from_aae with AAE file missing optional keys"""
    aae_path = tmp_path / "test.AAE"
    with open(aae_path, "wb") as fp:
        plistlib.dump({"adjustmentData": b"test"}, fp)

    adjustment_data = adjustment_data_from_aae(aae_path)
    assert adjustment_data.formatIdentifier() == PHOTOKIT_FORMAT_IDENTIFIER
    assert adjustment_data.formatVersion() == "1.0"
    assert bytes(adjustment_data.data()) == b"test"
    assert adjustment_data.baseVersion() == 0


def test_adjustment_data_from_aae_custom_identifier(tmp_path: pathlib.Path):
    """Test adjustment_data_from_aae does not change a non-Apple format identifier"""
    aae_path = tmp_path / "test.AAE"
    with open(aae_path, "wb") as fp:
        plistlib.dump(
            {
                "adjustmentFormatIdentifier": "com.example.editor",
                "adjustmentFormatVersion": "2.0",
                "adjustmentData": b"test",
            },
            fp,
        )

    adjustment_data = adjustment_data_from_aae(aae_path)
    assert adjustment_data.formatIdentifier() == "com.example.editor"
    assert adjustment_data.formatVersion() == "2.0"


def test_adjustment_data_from_aae_invalid(tmp_path: pathlib.Path):
    """Test adjustment_data_from_aae returns None for file that is not a plist"""
    aae_path = tmp_path / "test.AAE"
    aae_path.write_text("not a plist")
    assert adjustment_data_from_aae(aae_path) is None


def test_adjustment_data_from_aae_missing(tmp_path: pathlib.Path):
    """Test adjustment_data_from_aae returns None for missing file or None path"""
    assert adjustment_data_from_aae(tmp_path / "missing.AAE") is None
    assert adjustment_data_from_aae(None) is None


def test_create_minimal_adjustment_data():
    """Test create_minimal_adjustment_data"""
    adjustment_data = create_minimal_adjustment_data()
    assert adjustment_data.formatIdentifier() == "com.photokit.edit"
    assert adjustment_data.formatVersion() == "1.0"
    assert bytes(adjustment_data.data()) == b"edited"
