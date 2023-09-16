"""Test PhotoLibrary class in single library mode."""

import pytest

import photokit


def test_photolibrary_multi_library_mode():
    """Test PhotoLibrary.multi_library_mode property."""
    assert not photokit.PhotoLibrary.multi_library_mode()
