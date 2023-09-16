"""Test PhotoLibrary class in multi library mode."""

import pytest

import photokit

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()


def test_photolibrary_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property."""
    pl = photokit.PhotoLibrary(SYSTEM_LIBRARY_PATH)
    assert photokit.PhotoLibrary.multi_library_mode()
