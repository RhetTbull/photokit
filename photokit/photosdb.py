"""Access the Photos database directly."""

from __future__ import annotations

import logging
import os
import pathlib
import sqlite3

logger = logging.getLogger("photokit")


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
