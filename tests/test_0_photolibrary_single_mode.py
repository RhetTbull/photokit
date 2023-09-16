"""Test PhotoLibrary class in single library mode."""

import pytest

import photokit
from osxphotos.utils import get_system_library_path


def test_photolibrary_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property."""
    assert not photokit.PhotoLibrary.multi_library_mode()


def test_photolibrary_system_photo_library_path():
    """Test PhotoLibrary.system_photo_library_path() method."""
    library_path = get_system_library_path()
    assert photokit.PhotoLibrary.system_photo_library_path() == library_path
