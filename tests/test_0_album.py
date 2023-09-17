"""Test Album class."""

import osxphotos
import pytest
from osxphotos.datetime_utils import datetime_naive_to_local

import photokit


def test_album(photosdb: osxphotos.PhotosDB):
    """Test Album class."""

    library = photokit.PhotoLibrary()
    for expected_album in photosdb.album_info:
        album = library.album(expected_album.uuid)
        assert album.uuid == expected_album.uuid
        assert album.title == expected_album.title

        # Album start_date/end_date are naive datetimes
        # start_date and end_date can also be None
        if album.start_date:
            assert (
                datetime_naive_to_local(album.start_date) == expected_album.start_date
            )
        else:
            assert expected_album.start_date is None

        if album.end_date:
            assert datetime_naive_to_local(album.end_date) == expected_album.end_date
        else:
            assert expected_album.end_date is None

        expected_photos = [p for p in expected_album.photos if not p.hidden]
        assert len(album) == len(album.assets())

        # can't compare the assets directly as oxphotos will include
        # duplicate photos in an album whereas PhotoKit will not
        # so just test that every photokit UUID is in the expected list
        expected_uuids = [p.uuid for p in expected_photos]
        got_uuids = [p.uuid for p in album.assets()]
        for uuid in got_uuids:
            assert uuid in expected_uuids
