"""Access the Photos database directly."""

from __future__ import annotations

import logging
import os
import pathlib
import sqlite3

logger = logging.getLogger("photokit")

import datetime

# Time delta: add this to Photos times to get unix time
# Apple Epoch is Jan 1, 2001
TIME_DELTA = (
    datetime.datetime(2001, 1, 1, 0, 0) - datetime.datetime(1970, 1, 1, 0, 0)
).total_seconds()


class PhotosDB:
    """Access the Photos SQLite database directly."""

    def __init__(self, library_path: str | pathlib.Path | os.PathLike):
        """Initialize PhotosDB object with a library path."""
        self.library_path = pathlib.Path(library_path)
        self.db_path = self.library_path / "database" / "Photos.sqlite"
        self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return a connection to the Photos database."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def get_asset_uuids(
        self, hidden: bool = False, in_trash: bool = False, burst: bool = False
    ) -> list[str]:
        """Get a list of asset UUIDs from the Photos database.

        Args:
            hidden: (bool) if True, include hidden assets
            in_trash: (bool) if True, include assets in the trash
            burst: (bool) if True, include non-selected burst images

        Returns: list of asset UUIDs

        Note: Does not return UUIDs for non-selected burst images or shared images.
        """

        query = """
            SELECT ZASSET.ZUUID
            FROM ZASSET
            WHERE TRUE
            AND ZCLOUDBATCHPUBLISHDATE IS NULL -- not shared images
            """

        if not burst:
            query += "AND ( NOT ZAVALANCHEPICKTYPE & 2 AND NOT ZAVALANCHEPICKTYPE = 4 ) -- non=selected burst images\n"
        if not hidden:
            query += "AND ZHIDDEN = 0 \n"
        if not in_trash:
            query += "AND ZTRASHEDDATE IS NULL \n"
        query += ";"
        logger.debug(f"query = {query}")

        cursor = self.connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return [r[0] for r in results]

    def get_album_uuids(self, top_level=False) -> list[str]:
        """Get a list of album UUIDs for regular user albums from the Photos database.

        Args:
            top_level: (bool) if True, only return top-level albums

        Returns: list of album UUIDs
        """
        query = """
            SELECT ZUUID
            FROM ZGENERICALBUM
            WHERE ZKIND = 2 -- regular user albums
            AND ZTRASHEDDATE IS NULL
        """
        if top_level:
            # top-level albums have a parent folder of kind 3999
            # so need to find the Z_PK of the parent folder
            query += "AND ZPARENTFOLDER = (SELECT Z_PK FROM ZGENERICALBUM WHERE ZKIND = 3999)"
        query += ";"
        logger.debug(f"query = {query}")

        cursor = self.connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return [r[0] for r in results]

    def get_keyword_uuids_for_keywords(self, keywords: list[str]) -> list[str]:
        """Get UUIDs for keywords from the Photos database.

        Args:
            keywords: list of keyword names

        Returns: list of keyword UUIDs

        Note: the order of the returned UUIDs is not guaranteed to match the order of the input keywords
        """
        placeholders = ",".join(["?"] * len(keywords))
        query = f"""
            SELECT ZUUID
            FROM ZKEYWORD
            WHERE ZTITLE IN ({placeholders});
            """
        logger.debug(f"query = {query}")

        cursor = self.connection.cursor()
        cursor.execute(query, tuple(keywords))
        results = cursor.fetchall()
        cursor.close()
        return [r[0] for r in results]

    def get_date_added_for_uuid(self, uuid: str) -> datetime.datetime:
        """Get date added for an asset from the Photos database.

        Args:
            uuid: UUID of the asset

        Returns: datetime.datetime
        """
        query = """
            SELECT ZADDEDDATE
            FROM ZASSET
            WHERE ZUUID = ?;
            """
        logger.debug(f"query = {query}")

        cursor = self.connection.cursor()
        cursor.execute(query, (uuid,))
        results = cursor.fetchone()
        cursor.close()
        if not results:
            return datetime.datetime(1970, 1, 1, 0, 0, 0)
        try:
            return datetime.datetime.fromtimestamp(results[0] + TIME_DELTA)
        except (ValueError, TypeError):
            # I've seen corrupt values in the Photos database
            return datetime.datetime(1970, 1, 1, 0, 0, 0)
