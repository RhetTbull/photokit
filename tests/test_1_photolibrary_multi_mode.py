"""Test PhotoLibrary class in multi library mode."""

from __future__ import annotations

import pytest

import photokit

SYSTEM_LIBRARY_PATH = photokit.PhotoLibrary.system_photo_library_path()


def test_photolibrary_multi_library_mode_enable_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property and enable_multi_library_mode() method."""
    assert not photokit.PhotoLibrary.multi_library_mode()
    photokit.PhotoLibrary.enable_multi_library_mode()
    assert photokit.PhotoLibrary.multi_library_mode()
